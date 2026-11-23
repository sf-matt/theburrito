from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _read_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


def _read_positive_int(name: str, default: int, *, allow_zero: bool = False) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    minimum = 0 if allow_zero else 1
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    llm_model: str | None
    llm_reasoning_effort: str
    llm_max_output_tokens: int
    openai_api_key: str | None
    kubeconfig: str
    watch_label_selector: str | None
    dry_run: bool
    investigation_cooldown_seconds: int
    max_tool_calls: int
    agent_state_file: str
    state_observation_flush_seconds: int

    @classmethod
    def from_environment(
        cls,
        dotenv_path: Path | None = None,
        *,
        require_kubeconfig: bool = True,
        require_llm: bool = True,
    ) -> "Settings":
        load_dotenv(dotenv_path=dotenv_path, override=False)
        raw_kubeconfig = os.getenv("KUBECONFIG", "").strip()
        settings = cls(
            llm_provider=os.getenv("LLM_PROVIDER", "openai").strip().lower(),
            llm_model=os.getenv("LLM_MODEL") or None,
            llm_reasoning_effort=os.getenv(
                "LLM_REASONING_EFFORT", "low"
            ).strip().lower(),
            llm_max_output_tokens=_read_positive_int(
                "LLM_MAX_OUTPUT_TOKENS", 2048
            ),
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            kubeconfig=str(Path(raw_kubeconfig).expanduser()) if raw_kubeconfig else "",
            watch_label_selector=os.getenv("WATCH_LABEL_SELECTOR") or None,
            dry_run=_read_bool("DRY_RUN", True),
            investigation_cooldown_seconds=_read_positive_int(
                "INVESTIGATION_COOLDOWN_SECONDS", 300, allow_zero=True
            ),
            max_tool_calls=_read_positive_int("MAX_TOOL_CALLS", 2),
            agent_state_file=str(
                Path(
                    os.getenv("AGENT_STATE_FILE", "state/assessments.json")
                ).expanduser().resolve()
            ),
            state_observation_flush_seconds=_read_positive_int(
                "STATE_OBSERVATION_FLUSH_SECONDS", 60, allow_zero=True
            ),
        )
        settings.validate(
            require_kubeconfig=require_kubeconfig,
            require_llm=require_llm,
        )
        return settings

    def validate(
        self,
        *,
        require_kubeconfig: bool = True,
        require_llm: bool = True,
    ) -> None:
        if require_kubeconfig and not self.kubeconfig:
            raise ValueError(
                "KUBECONFIG must point to the dedicated ai-investigator kubeconfig"
            )
        if require_kubeconfig and not Path(self.kubeconfig).is_file():
            raise ValueError("KUBECONFIG must point to an existing file")
        if require_llm and not self.dry_run:
            if not self.llm_model:
                raise ValueError("LLM_MODEL is required when DRY_RUN is false")
            if self.llm_reasoning_effort not in {
                "none",
                "minimal",
                "low",
                "medium",
                "high",
                "xhigh",
                "max",
            }:
                raise ValueError("LLM_REASONING_EFFORT is not supported")
            if self.llm_max_output_tokens < 16:
                raise ValueError("LLM_MAX_OUTPUT_TOKENS must be at least 16")
            if self.llm_provider == "openai":
                if not self.openai_api_key:
                    raise ValueError(
                        "OPENAI_API_KEY is required when LLM_PROVIDER=openai"
                    )
            else:
                raise ValueError(f"Unsupported LLM_PROVIDER: {self.llm_provider}")
