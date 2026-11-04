"""AC01 配置与启动：默认值可跑、环境变量可覆盖、缺配置时报错能指名。"""

from __future__ import annotations

import pytest

from app.config import ConfigError, load_config


def test_defaults_run_without_env():
    config = load_config(env={})
    assert config.provider == "scripted"
    assert config.model == "gpt-4o-mini"
    assert config.max_steps == 6
    assert config.token_budget == 6000
    assert config.wall_clock_s == 30.0
    assert config.db_path == "runs.db"
    assert config.api_key is None


def test_env_overrides_are_read():
    env = {
        "PROVIDER": "scripted",
        "MODEL": "mock-model",
        "MAX_STEPS": "3",
        "TOKEN_BUDGET": "1200",
        "WALL_CLOCK_S": "2.5",
        "DB_PATH": "custom/runs.db",
        "REFUND_AUTO_LIMIT": "199.5",
    }
    config = load_config(env=env)
    assert (config.model, config.max_steps, config.token_budget) == ("mock-model", 3, 1200)
    assert config.wall_clock_s == 2.5
    assert config.db_path == "custom/runs.db"
    assert config.refund_auto_limit_cents == 19950


def test_missing_required_config_names_the_env_var():
    with pytest.raises(ConfigError) as excinfo:
        load_config(env={"PROVIDER": "openai"})
    assert "OPENAI_API_KEY" in str(excinfo.value)
    assert excinfo.value.field == "OPENAI_API_KEY"


def test_invalid_value_reports_field():
    with pytest.raises(ConfigError) as excinfo:
        load_config(env={"MAX_STEPS": "0"})
    assert excinfo.value.field == "MAX_STEPS"
    assert "MAX_STEPS" in str(excinfo.value)


def test_as_mapping_never_exposes_secret():
    config = load_config(env={"OPENAI_API_KEY": "sk-test", "PROVIDER": "openai"})
    mapping = config.as_mapping()
    assert "api_key" not in mapping
    assert mapping["api_key_configured"] is True
    assert "sk-test" not in repr(mapping)
