"""CLI tests for configuration guidance behavior."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from openbiliclaw import config as config_module
from openbiliclaw.cli import app


def _write_example_config(project_root: Path) -> None:
    (project_root / "config.example.toml").write_text(
        """
[general]
language = "zh"
data_dir = "data"

[llm]
default_provider = "openai"

[llm.openai]
api_key = ""
model = "gpt-4o"
base_url = ""

[llm.claude]
api_key = ""
model = "claude-sonnet-4-20250514"

[llm.deepseek]
api_key = ""
model = "deepseek-chat"
base_url = "https://api.deepseek.com"

[llm.ollama]
model = "llama3"
base_url = "http://localhost:11434"

[bilibili]
auth_method = "cookie"
cookie = ""

[bilibili.browser]
executable = ""
headed = false

[scheduler]
enabled = true
discovery_cron = "0 */4 * * *"

[storage]
db_path = "data/openbiliclaw.db"
""".strip(),
        encoding="utf-8",
    )


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_config_show_generates_template_and_prints_guidance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
    monkeypatch.setattr(config_module, "_PROJECT_ROOT", tmp_path)
    _write_example_config(tmp_path)

    result = runner.invoke(app, ["config-show"])

    assert result.exit_code == 0
    assert (tmp_path / "config.toml").exists()
    assert "当前配置" in result.stdout
    assert "已自动生成" in result.stdout
    assert "llm.openai.api_key" in result.stdout


def test_recommend_reports_clear_config_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
    monkeypatch.setattr(config_module, "_PROJECT_ROOT", tmp_path)
    _write_example_config(tmp_path)

    result = runner.invoke(app, ["recommend"])

    assert result.exit_code == 1
    assert "配置错误" in result.stdout
    assert "llm.openai.api_key" in result.stdout
