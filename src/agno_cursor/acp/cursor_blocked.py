"""Cursor ACP blocking extensions (ask_question, create_plan) and leader envelopes."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

MAX_INVALID_RESUME_ATTEMPTS = 3

BLOCKING_METHODS = frozenset({"cursor/ask_question", "cursor/create_plan"})


@dataclass
class CursorBlockedTurn:
    """Member turn suspended until the coordinator sends a resume JSON payload."""

    kind: str
    agent_key: str
    params: Dict[str, Any]
    plans: Dict[str, Any] = field(default_factory=dict)
    parse_error: Optional[str] = None

    @property
    def method(self) -> str:
        return "cursor/ask_question" if self.kind == "ask_question" else "cursor/create_plan"


def parse_resume_payload(text: str) -> Optional[Dict[str, Any]]:
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


def validate_resume_payload(kind: str, payload: Dict[str, Any]) -> Optional[str]:
    if payload.get("kind") != kind:
        return f"Expected kind {kind!r}, got {payload.get('kind')!r}."
    outcome = payload.get("outcome")
    if kind == "ask_question":
        if outcome == "answered":
            answers = payload.get("answers")
            if not isinstance(answers, list) or not answers:
                return "ask_question with outcome answered requires a non-empty answers array."
            return None
        if outcome in ("skipped", "cancelled"):
            return None
        return f"Invalid ask_question outcome: {outcome!r}."
    if kind == "create_plan":
        if outcome == "accepted":
            return None
        if outcome == "rejected":
            if not payload.get("reason"):
                return "create_plan rejected requires a reason."
            return None
        if outcome == "cancelled":
            return None
        return f"Invalid create_plan outcome: {outcome!r}."
    return f"Unknown blocked kind: {kind!r}."


def build_extension_rpc_result(kind: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build the value for JSON-RPC result.outcome (nested outcome object)."""
    outcome = payload.get("outcome")
    if kind == "ask_question":
        if outcome == "answered":
            return {"outcome": "answered", "answers": payload.get("answers", [])}
        if outcome == "skipped":
            result: Dict[str, Any] = {"outcome": "skipped"}
            if payload.get("reason"):
                result["reason"] = payload["reason"]
            return result
        return {"outcome": "cancelled"}
    if outcome == "accepted":
        result = {"outcome": "accepted"}
        if payload.get("planUri"):
            result["planUri"] = payload["planUri"]
        return result
    if outcome == "rejected":
        return {"outcome": "rejected", "reason": payload.get("reason", "")}
    return {"outcome": "cancelled"}


def cancelled_rpc_result(kind: str) -> Dict[str, Any]:
    if kind == "ask_question":
        return {"outcome": "cancelled"}
    return {"outcome": "cancelled"}


def format_blocked_envelope(turn: CursorBlockedTurn) -> str:
    lines = [
        "[cursor_blocked]",
        f"member: {turn.agent_key}",
        f"kind: {turn.kind}",
        "status: This member is paused inside an open Cursor turn; this is not finished work.",
    ]
    if turn.parse_error:
        lines.append(f"parse_error: {turn.parse_error}")
    if turn.plans:
        lines.append("plan_snapshot:")
        lines.append(json.dumps(turn.plans, indent=2))
    lines.append("cursor_request:")
    lines.append(json.dumps(turn.params, indent=2))
    if turn.kind == "ask_question":
        lines.append(
            'reply_with_json_only: {"kind":"ask_question","outcome":"answered",'
            '"answers":[{"questionId":"<id>","selectedOptionIds":["<option_id>"]}]}'
        )
        lines.append(
            'Or: {"kind":"ask_question","outcome":"skipped","reason":"..."} or '
            '{"kind":"ask_question","outcome":"cancelled"}'
        )
    else:
        lines.append('reply_with_json_only: {"kind":"create_plan","outcome":"accepted"}')
        lines.append(
            'Or: {"kind":"create_plan","outcome":"rejected","reason":"..."} or '
            '{"kind":"create_plan","outcome":"cancelled"}'
        )
    return "\n".join(lines)


def append_plan_snapshot(reply: str, plans: Dict[str, Any]) -> str:
    if not plans:
        return reply
    block = "[cursor_plan_snapshot]\n" + json.dumps(plans, indent=2)
    if reply.strip():
        return f"{reply.rstrip()}\n\n{block}"
    return block
