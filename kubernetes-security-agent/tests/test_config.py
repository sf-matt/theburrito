from pathlib import Path

import pytest

from agent.config import Settings


def test_requires_explicit_kubeconfig(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("KUBECONFIG", raising=False)
    monkeypatch.setenv("DRY_RUN", "true")

    with pytest.raises(ValueError, match="dedicated ai-investigator kubeconfig"):
        Settings.from_environment(dotenv_path=tmp_path / "missing.env")


def test_rejects_missing_kubeconfig_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KUBECONFIG", str(tmp_path / "missing.kubeconfig"))
    monkeypatch.setenv("DRY_RUN", "true")

    with pytest.raises(ValueError, match="existing file"):
        Settings.from_environment(dotenv_path=tmp_path / "missing.env")


def test_accepts_existing_dedicated_kubeconfig(monkeypatch, tmp_path: Path) -> None:
    kubeconfig = tmp_path / "ai-investigator.kubeconfig"
    kubeconfig.write_text("apiVersion: v1\n", encoding="utf-8")
    monkeypatch.setenv("KUBECONFIG", str(kubeconfig))
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.delenv("MAX_TOOL_CALLS", raising=False)

    settings = Settings.from_environment(dotenv_path=tmp_path / "missing.env")

    assert settings.kubeconfig == str(kubeconfig)
    assert settings.max_tool_calls == 2


def test_inventory_configuration_does_not_require_kubeconfig(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("KUBECONFIG", raising=False)
    monkeypatch.setenv("AGENT_STATE_FILE", str(tmp_path / "assessments.json"))

    settings = Settings.from_environment(
        dotenv_path=tmp_path / "missing.env",
        require_kubeconfig=False,
    )

    assert settings.kubeconfig == ""
    assert settings.agent_state_file == str(tmp_path / "assessments.json")


def test_enabled_investigation_requires_generic_model(monkeypatch, tmp_path: Path) -> None:
    kubeconfig = tmp_path / "ai-investigator.kubeconfig"
    kubeconfig.write_text("apiVersion: v1\n", encoding="utf-8")
    monkeypatch.setenv("KUBECONFIG", str(kubeconfig))
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    with pytest.raises(ValueError, match="LLM_MODEL"):
        Settings.from_environment(dotenv_path=tmp_path / "missing.env")


def test_openai_adapter_requires_its_provider_key(monkeypatch, tmp_path: Path) -> None:
    kubeconfig = tmp_path / "ai-investigator.kubeconfig"
    kubeconfig.write_text("apiVersion: v1\n", encoding="utf-8")
    monkeypatch.setenv("KUBECONFIG", str(kubeconfig))
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        Settings.from_environment(dotenv_path=tmp_path / "missing.env")


def test_rejects_unimplemented_provider(monkeypatch, tmp_path: Path) -> None:
    kubeconfig = tmp_path / "ai-investigator.kubeconfig"
    kubeconfig.write_text("apiVersion: v1\n", encoding="utf-8")
    monkeypatch.setenv("KUBECONFIG", str(kubeconfig))
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("LLM_PROVIDER", "unimplemented")
    monkeypatch.setenv("LLM_MODEL", "test-model")

    with pytest.raises(ValueError, match="Unsupported LLM_PROVIDER"):
        Settings.from_environment(dotenv_path=tmp_path / "missing.env")


def test_reads_bounded_llm_settings(monkeypatch, tmp_path: Path) -> None:
    kubeconfig = tmp_path / "ai-investigator.kubeconfig"
    kubeconfig.write_text("apiVersion: v1\n", encoding="utf-8")
    monkeypatch.setenv("KUBECONFIG", str(kubeconfig))
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_REASONING_EFFORT", "low")
    monkeypatch.setenv("LLM_MAX_OUTPUT_TOKENS", "2048")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    settings = Settings.from_environment(dotenv_path=tmp_path / "missing.env")

    assert settings.llm_reasoning_effort == "low"
    assert settings.llm_max_output_tokens == 2048


def test_rejects_too_small_output_limit(monkeypatch, tmp_path: Path) -> None:
    kubeconfig = tmp_path / "ai-investigator.kubeconfig"
    kubeconfig.write_text("apiVersion: v1\n", encoding="utf-8")
    monkeypatch.setenv("KUBECONFIG", str(kubeconfig))
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_MAX_OUTPUT_TOKENS", "15")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    with pytest.raises(ValueError, match="at least 16"):
        Settings.from_environment(dotenv_path=tmp_path / "missing.env")
