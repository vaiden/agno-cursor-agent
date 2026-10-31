"""Custom Agno Model adapter: Agno model API <-> Cursor ACP."""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional, Type, Union

from pydantic import BaseModel

from agno.models.base import Model
from agno.models.message import Message
from agno.models.response import ModelResponse
from agno.run.agent import RunOutput
from agno.run.team import TeamRunOutput

from agno_cursor.acp.cursor_blocked import (
    CursorBlockedTurn,
    format_blocked_envelope,
    parse_resume_payload,
    validate_resume_payload,
)
from agno_cursor.acp.registry import REGISTRY
from agno_cursor.acp.session import ACPSession, PromptOutcome
from agno_cursor.settings import AcpMode, HarnessSettings
from agno_cursor.trace import log_agent_meta

TOOL_CALL_INSTRUCTION = """
When tools are available you MUST respond with ONLY valid JSON (no markdown fences):
{{"tool_calls":[{{"name":"<tool_name>","arguments":{{...}}}}]}}
If no tool is needed respond with ONLY:
{{"content":"<your reply>"}}
Available tools (name and parameters):
{tools_json}
"""


@dataclass
class CursorACPChat(Model):
    id: str = "composer-2.5"
    agent_key: str = ""
    model: str = "composer-2.5"
    mode: AcpMode = "ask"
    settings: Any = field(default=None, repr=False)
    provider: str = "cursor"
    _first_turn: bool = field(default=True, init=False, repr=False)

    def __post_init__(self) -> None:
        self.id = self.model
        if not self.agent_key:
            self.agent_key = self.model
        if self.settings is None:
            self.settings = HarnessSettings()

    def _session(self) -> ACPSession:
        return REGISTRY.get_or_create(self.agent_key, self.model, self.mode, self.settings)

    def _tools_prompt_json(self, tools: Optional[List[Any]]) -> str:
        if not tools:
            return "[]"
        simplified = []
        for t in tools:
            if hasattr(t, "to_dict") and callable(t.to_dict):
                fn = t.to_dict()
                if "name" in fn:
                    simplified.append(
                        {
                            "name": fn.get("name"),
                            "description": fn.get("description"),
                            "parameters": fn.get("parameters"),
                        }
                    )
                    continue
            if isinstance(t, dict):
                fn = t.get("function", t)
                simplified.append(
                    {
                        "name": fn.get("name"),
                        "description": fn.get("description"),
                        "parameters": fn.get("parameters"),
                    }
                )
        return json.dumps(simplified, indent=2)

    def _build_prompt(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        parts: List[str] = []
        if self._first_turn:
            system_msgs = [
                m.get_content_string() for m in messages if m.role == "system" and m.get_content_string()
            ]
            if system_msgs:
                parts.append("System instructions:\n" + "\n".join(system_msgs))

        for m in reversed(messages):
            if m.role == "user" and m.get_content_string():
                parts.append(m.get_content_string())
                break
            if m.role == "tool" and m.get_content_string():
                parts.append("Tool result:\n" + m.get_content_string())
                break

        if not parts:
            parts.append(messages[-1].get_content_string() if messages else "")

        prompt = parts[-1] if len(parts) == 1 and not self._first_turn else "\n\n".join(parts)

        if tools:
            prompt += "\n\n" + TOOL_CALL_INSTRUCTION.format(tools_json=self._tools_prompt_json(tools))

        self._first_turn = False
        return prompt

    def _run_acp_turn(self, prompt: str) -> PromptOutcome:
        session = self._session()
        if session.is_parked():
            payload = parse_resume_payload(prompt)
            kind = session.parked_kind
            if payload and kind and validate_resume_payload(kind, payload) is None:
                return session.resume(payload)
            err = "Expected a single JSON resume object for the parked Cursor request."
            if payload and kind:
                validation_err = validate_resume_payload(kind, payload)
                if validation_err:
                    err = validation_err
            return session.invalid_resume(err)
        return session.prompt(prompt)

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        text = text.strip()
        if text.startswith("{") and text.endswith("}"):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return None
        return None

    def _parse_provider_response(self, response: Any, **kwargs) -> ModelResponse:
        text = response if isinstance(response, str) else str(response)
        parsed = self._extract_json(text)
        model_response = ModelResponse(role="assistant")

        if parsed and "tool_calls" in parsed:
            tool_calls = []
            for tc in parsed["tool_calls"]:
                name = tc.get("name")
                args = tc.get("arguments", {})
                tool_calls.append(
                    {
                        "id": f"call_{uuid.uuid4().hex[:12]}",
                        "type": "function",
                        "function": {
                            "name": name,
                            "arguments": json.dumps(args) if isinstance(args, dict) else str(args),
                        },
                    }
                )
            model_response.tool_calls = tool_calls
            return model_response

        if parsed and "content" in parsed:
            model_response.content = parsed["content"]
            return model_response

        model_response.content = text
        return model_response

    def _parse_provider_response_delta(self, response: Any) -> ModelResponse:
        return self._parse_provider_response(response)

    def invoke(
        self,
        messages: List[Message],
        assistant_message: Message,
        response_format: Optional[Union[Dict, Type[BaseModel]]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        run_response: Optional[Union[RunOutput, TeamRunOutput]] = None,
        compress_tool_results: bool = False,
    ) -> ModelResponse:
        prompt = self._build_prompt(messages, tools=tools)
        resolved = self.settings.resolve(self.agent_key, self.agent_key) if hasattr(self.settings, "resolve") else None
        role = resolved.role if resolved else self.agent_key
        mode = resolved.mode if resolved else self.mode

        if getattr(self.settings, "acp_trace", False):
            log_agent_meta(
                role=role,
                model=self.model,
                agent_key=self.agent_key,
                mode=mode,
                label="Agno → ACP (invoke)",
                detail=f"tools={'yes' if tools else 'no'}",
            )
        raw = self._run_acp_turn(prompt)
        if isinstance(raw, CursorBlockedTurn):
            model_response = ModelResponse(role="assistant")
            model_response.content = format_blocked_envelope(raw)
            if getattr(self.settings, "acp_trace", False):
                log_agent_meta(
                    role=role,
                    model=self.model,
                    agent_key=self.agent_key,
                    mode=mode,
                    label="Agno ← ACP (blocked)",
                    detail=f"kind={raw.kind}",
                )
            return model_response
        parsed = self._parse_provider_response(raw)
        if getattr(self.settings, "acp_trace", False):
            if parsed.tool_calls:
                names = [tc.get("function", {}).get("name") for tc in parsed.tool_calls]
                detail = f"tool_calls={names}"
            else:
                detail = f"content={(parsed.content or '')[:500]!r}"
            log_agent_meta(
                role=role,
                model=self.model,
                agent_key=self.agent_key,
                mode=mode,
                label="Agno ← ACP (parsed)",
                detail=detail,
            )
        return parsed

    async def ainvoke(
        self,
        messages: List[Message],
        assistant_message: Message,
        response_format: Optional[Union[Dict, Type[BaseModel]]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        run_response: Optional[Union[RunOutput, TeamRunOutput]] = None,
        compress_tool_results: bool = False,
    ) -> ModelResponse:
        return await asyncio.to_thread(
            self.invoke,
            messages,
            assistant_message,
            response_format,
            tools,
            tool_choice,
            run_response,
            compress_tool_results,
        )

    def invoke_stream(
        self,
        messages: List[Message],
        assistant_message: Message,
        response_format: Optional[Union[Dict, Type[BaseModel]]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        run_response: Optional[Union[RunOutput, TeamRunOutput]] = None,
        compress_tool_results: bool = False,
    ) -> Iterator[ModelResponse]:
        yield self.invoke(
            messages,
            assistant_message,
            response_format,
            tools,
            tool_choice,
            run_response,
            compress_tool_results,
        )

    async def ainvoke_stream(
        self,
        messages: List[Message],
        assistant_message: Message,
        response_format: Optional[Union[Dict, Type[BaseModel]]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        run_response: Optional[Union[RunOutput, TeamRunOutput]] = None,
        compress_tool_results: bool = False,
    ) -> AsyncIterator[ModelResponse]:
        result = await self.ainvoke(
            messages,
            assistant_message,
            response_format,
            tools,
            tool_choice,
            run_response,
            compress_tool_results,
        )
        yield result
