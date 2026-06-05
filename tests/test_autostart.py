"""Tests for boot autostart runtime helpers."""

from pathlib import Path

import pytest

from openbiliclaw.config import Config, save_config


def test_active_env_managed_inputs_detects_known_external_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from openbiliclaw.runtime.autostart.guards import active_env_managed_inputs

    cfg = Config()
    cfg.sources.douyin.cookie_env = "CUSTOM_DOUYIN_COOKIE"
    monkeypatch.setenv("OPENBILICLAW_PROJECT_ROOT", "/tmp/openbiliclaw")
    monkeypatch.setenv("OPENBILICLAW_LLM_DEFAULT_PROVIDER", "ollama")
    monkeypatch.setenv("OPENBILICLAW_API_AUTH_PASSWORD", "secret")
    monkeypatch.setenv("GOOGLE_API_KEY", "gemini-key")
    monkeypatch.setenv("CUSTOM_DOUYIN_COOKIE", "sid=1")

    assert active_env_managed_inputs(cfg) == [
        "CUSTOM_DOUYIN_COOKIE",
        "GOOGLE_API_KEY",
        "OPENBILICLAW_API_AUTH_PASSWORD",
        "OPENBILICLAW_LLM_DEFAULT_PROVIDER",
    ]


def test_active_env_managed_inputs_ignores_empty_or_project_root_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from openbiliclaw.runtime.autostart.guards import active_env_managed_inputs

    cfg = Config()
    monkeypatch.setenv("OPENBILICLAW_PROJECT_ROOT", "/tmp/openbiliclaw")
    monkeypatch.setenv("GEMINI_API_KEY", "")

    assert active_env_managed_inputs(cfg) == []


def test_autostart_shadowed_detects_config_local_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from openbiliclaw.runtime.autostart.guards import autostart_shadowed

    monkeypatch.setenv("OPENBILICLAW_PROJECT_ROOT", str(tmp_path))
    cfg = Config()
    cfg.autostart.enabled = False
    save_config(cfg, autostart_authoritative=True)
    (tmp_path / "config.local.toml").write_text(
        "[autostart]\nenabled = true\n",
        encoding="utf-8",
    )

    assert autostart_shadowed(False) is True


def test_autostart_shadowed_false_when_effective_matches_intent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from openbiliclaw.runtime.autostart.guards import autostart_shadowed

    monkeypatch.setenv("OPENBILICLAW_PROJECT_ROOT", str(tmp_path))
    cfg = Config()
    cfg.autostart.enabled = True
    save_config(cfg, autostart_authoritative=True)

    assert autostart_shadowed(True) is False
