from __future__ import annotations

import pytest

from src.core.mms.config_yaml_validation import YamlConfigValidationError, parse_yaml_config_mapping


def test_parse_yaml_config_mapping_accepts_standard_yaml_mapping():
    payload = parse_yaml_config_mapping(
        """
        account:
          writeback_enabled: false
          filter_statuses:
            - normal
        captcha:
          poll_interval_seconds: 0.5
        """
    )

    assert payload == {
        "account": {
            "writeback_enabled": False,
            "filter_statuses": ["normal"],
        },
        "captcha": {"poll_interval_seconds": 0.5},
    }


def test_parse_yaml_config_mapping_accepts_empty_content_as_empty_mapping():
    assert parse_yaml_config_mapping("") == {}
    assert parse_yaml_config_mapping("   \n") == {}


def test_parse_yaml_config_mapping_rejects_invalid_yaml_with_context():
    with pytest.raises(YamlConfigValidationError) as exc_info:
        parse_yaml_config_mapping("account: [")

    assert "YAML 格式错误" in str(exc_info.value)


def test_parse_yaml_config_mapping_rejects_non_mapping_root():
    with pytest.raises(YamlConfigValidationError) as exc_info:
        parse_yaml_config_mapping("- normal\n- paused\n", scope_name="模块配置")

    assert str(exc_info.value) == "模块配置必须是 YAML 映射对象"


def test_parse_yaml_config_mapping_rejects_duplicate_keys():
    with pytest.raises(YamlConfigValidationError) as exc_info:
        parse_yaml_config_mapping(
            """
            account:
              enabled: true
              enabled: false
            """
        )

    assert "YAML 中存在重复键: enabled" in str(exc_info.value)
