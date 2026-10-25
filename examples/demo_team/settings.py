"""Convention-over-configuration settings for the demo Cursor ACP Agno team."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Literal, Optional

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from agno_cursor.settings import AcpMode, build_spawn_argv

PROJECT_ROOT = Path(__file__).resolve().parent

DEFAULT_ROLE_MODELS: Dict[str, str] = {
    "leader": "auto",
    "coder": "composer-2.5",
    "writer": "claude-sonnet-5-5-medium",
    "product_owner": "claude-sonnet-5-5-medium",
}


class AgentConfig(BaseModel):
    model: Optional[str] = None
    mode: Optional[AcpMode] = None
    worker_url: Optional[str] = None
    role: Optional[str] = None


class ResolvedAgent(BaseModel):
    agent_id: str
    role: str
    model: str
    mode: AcpMode
    worker_url: Optional[str] = None


def _load_yaml_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data if isinstance(data, dict) else {}


class TeamSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CURSOR_TEAM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    port: int = 7777
    team_id: str = "cursor_team"
    base_spawn_cmd: str = "cursor-agent"
    default_model: str = "composer-2.5"
    default_mode: AcpMode = "ask"
    worker_fallback_local: bool = False
    agent_id: Optional[str] = None
    acp_trace: bool = False

    role_models: Dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_ROLE_MODELS))
    agents: Dict[str, AgentConfig] = Field(default_factory=dict)

    workers: Dict[str, str] = Field(default_factory=dict)
    models: Dict[str, str] = Field(default_factory=dict)
    modes: Dict[str, str] = Field(default_factory=dict)

    project_root: Path = Field(default_factory=lambda: PROJECT_ROOT)

    @field_validator("role_models", "agents", "workers", "models", "modes", mode="before")
    @classmethod
    def _coerce_json(cls, value: Any) -> Any:
        if isinstance(value, str) and value.strip():
            return json.loads(value)
        return value

    @model_validator(mode="after")
    def _merge_config(self) -> "TeamSettings":
        yaml_cfg = _load_yaml_config(self.project_root / "config.yaml")
        if yaml_cfg.get("role_models"):
            merged = dict(self.role_models)
            merged.update(yaml_cfg["role_models"])
            self.role_models = merged
        for key in ("port", "team_id", "base_spawn_cmd", "default_model", "default_mode", "worker_fallback_local"):
            if key in yaml_cfg and yaml_cfg[key] is not None:
                setattr(self, key, yaml_cfg[key])
        if yaml_cfg.get("agents"):
            agents = dict(self.agents)
            for aid, cfg in yaml_cfg["agents"].items():
                base = agents.get(aid, AgentConfig())
                agents[aid] = AgentConfig(**{**base.model_dump(), **cfg})
            self.agents = agents

        agents = dict(self.agents)
        for agent_id, url in self.workers.items():
            base = agents.get(agent_id, AgentConfig())
            agents[agent_id] = AgentConfig(**{**base.model_dump(), "worker_url": url})
        for agent_id, model in self.models.items():
            base = agents.get(agent_id, AgentConfig())
            agents[agent_id] = AgentConfig(**{**base.model_dump(), "model": model})
        for agent_id, mode in self.modes.items():
            base = agents.get(agent_id, AgentConfig())
            agents[agent_id] = AgentConfig(**{**base.model_dump(), "mode": mode})  # type: ignore[arg-type]
        self.agents = agents
        return self

    def resolve(self, agent_id: str, role: str) -> ResolvedAgent:
        override = self.agents.get(agent_id) or AgentConfig()
        effective_role = override.role or role
        model = override.model or self.role_models.get(effective_role) or self.default_model
        mode: AcpMode = override.mode or self.default_mode  # type: ignore[assignment]
        return ResolvedAgent(
            agent_id=agent_id,
            role=effective_role,
            model=model,
            mode=mode,
            worker_url=override.worker_url,
        )

    def spawn_argv(self, model: str, mode: AcpMode) -> list[str]:
        return build_spawn_argv(self.base_spawn_cmd, model, mode)


def team_base_url() -> str:
    return os.environ.get("TEAM_BASE_URL", "http://localhost:7777")
