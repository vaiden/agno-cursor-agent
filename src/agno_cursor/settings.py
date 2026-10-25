"""Harness settings and Cursor CLI spawn helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

AcpMode = Literal["ask", "plan", "agent"]


def build_spawn_argv(base_spawn_cmd: str, model: str, mode: AcpMode) -> list[str]:
    cmd = base_spawn_cmd.split()
    argv = [*cmd, "--model", model]
    if mode in ("ask", "plan"):
        argv.extend(["--mode", mode])
    elif mode == "agent":
        argv.append("--force")
    argv.append("acp")
    return argv


class HarnessSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGNO_CURSOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    base_spawn_cmd: str = "cursor-agent"
    acp_trace: bool = False
    project_root: Path = Field(default_factory=Path.cwd)

    def spawn_argv(self, model: str, mode: AcpMode) -> list[str]:
        return build_spawn_argv(self.base_spawn_cmd, model, mode)


@runtime_checkable
class ACPSettings(Protocol):
    acp_trace: bool
    project_root: Path

    def spawn_argv(self, model: str, mode: AcpMode) -> list[str]: ...


def resolve_acp_role(settings: ACPSettings, agent_key: str) -> str:
    resolve = getattr(settings, "resolve", None)
    if callable(resolve):
        return resolve(agent_key, agent_key).role
    return agent_key


def check_cursor_login() -> None:
    cli = shutil.which("cursor-agent") or shutil.which("agent")
    if not cli:
        raise RuntimeError("cursor-agent CLI not found on PATH")
    result = subprocess.run([cli, "status"], capture_output=True, text=True, check=False)
    if result.returncode != 0 or "Logged in" not in (result.stdout + result.stderr):
        raise RuntimeError(
            "Cursor CLI is not logged in. Run: cursor-agent login\n"
            + (result.stdout or result.stderr)
        )
