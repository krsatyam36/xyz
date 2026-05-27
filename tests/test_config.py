"""Tests for XYZ configuration."""
from xyz.config import XYZConfig


def test_config_defaults():
    config = XYZConfig()
    assert config.api_key_set is False
    assert config.default_model == "meta/llama-3.3-70b-instruct"
    assert config.theme == "claude"
    assert config.trust_mode is False
    assert config.gateway_port == 0


def test_config_custom_values():
    config = XYZConfig(
        api_key_set=True,
        default_model="custom/model",
        theme="midnight",
        trust_mode=True,
    )
    assert config.api_key_set is True
    assert config.default_model == "custom/model"
    assert config.theme == "midnight"
    assert config.trust_mode is True
