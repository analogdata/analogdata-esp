"""Tests for analogdata_esp.core.settings."""

import pytest
from pathlib import Path

import analogdata_esp.core.settings as settings_module
from analogdata_esp.core.settings import (
    load_settings,
    save_settings,
    get_ai_setting,
    set_ai_setting,
    get_idf_setting,
    set_idf_setting,
    _DEFAULT_SETTINGS,
    _deep_merge,
    _write_toml,
    _toml_value,
)


# ---------------------------------------------------------------------------
# _deep_merge unit tests
# ---------------------------------------------------------------------------

class TestDeepMerge:
    def test_empty_override_returns_base(self):
        base = {"a": 1, "b": {"c": 2}}
        result = _deep_merge(base, {})
        assert result == base

    def test_nested_dict_merged_recursively(self):
        base = {"ai": {"provider": "ollama", "model": ""}}
        override = {"ai": {"model": "gemma3:4b"}}
        result = _deep_merge(base, override)
        assert result["ai"]["provider"] == "ollama"
        assert result["ai"]["model"] == "gemma3:4b"

    def test_scalar_override_replaces_value(self):
        base = {"key": "old"}
        override = {"key": "new"}
        result = _deep_merge(base, override)
        assert result["key"] == "new"

    def test_new_keys_added(self):
        base = {"a": 1}
        override = {"b": 2}
        result = _deep_merge(base, override)
        assert result["a"] == 1
        assert result["b"] == 2

    def test_original_dict_not_mutated(self):
        base = {"ai": {"provider": "ollama"}}
        override = {"ai": {"model": "gpt-4o"}}
        _deep_merge(base, override)
        assert "model" not in base["ai"]


# ---------------------------------------------------------------------------
# _toml_value serialization
# ---------------------------------------------------------------------------

class TestTomlValue:
    def test_string(self):
        assert _toml_value("hello") == '"hello"'

    def test_string_with_quotes(self):
        assert _toml_value('say "hi"') == '"say \\"hi\\""'

    def test_string_with_backslash(self):
        assert _toml_value("C:\\path") == '"C:\\\\path"'

    def test_bool_true(self):
        assert _toml_value(True) == "true"

    def test_bool_false(self):
        assert _toml_value(False) == "false"

    def test_int(self):
        assert _toml_value(42) == "42"

    def test_float(self):
        assert _toml_value(3.14) == "3.14"

    def test_list(self):
        result = _toml_value(["a", "b"])
        assert result == '["a", "b"]'

    def test_empty_string(self):
        assert _toml_value("") == '""'


# ---------------------------------------------------------------------------
# load_settings — defaults when no file exists
# ---------------------------------------------------------------------------

class TestLoadSettings:
    def test_returns_defaults_when_no_file(self, tmp_config_dir):
        settings = load_settings()
        assert settings["idf"]["path"] == ""
        assert settings["idf"]["tools_path"] == ""
        assert settings["ai"]["provider"] == "ollama"
        assert settings["ai"]["model"] == ""
        assert settings["ai"]["api_key"] == ""
        assert settings["ai"]["base_url"] == ""

    def test_has_all_expected_sections(self, tmp_config_dir):
        settings = load_settings()
        assert "idf" in settings
        assert "ai" in settings

    def test_default_provider_is_ollama(self, tmp_config_dir):
        settings = load_settings()
        assert settings["ai"]["provider"] == "ollama"

    def test_corrupted_config_falls_back_to_defaults(self, tmp_config_dir):
        # Write invalid TOML
        tmp_config_dir["file"].write_text("this is [not valid toml ][[\n", encoding="utf-8")
        settings = load_settings()
        assert settings["ai"]["provider"] == "ollama"
        assert settings["idf"]["path"] == ""

    def test_partial_config_merges_with_defaults(self, tmp_config_dir):
        # Only write ai.provider; idf section should still have defaults
        tmp_config_dir["file"].write_text(
            '[ai]\nprovider = "openai"\n', encoding="utf-8"
        )
        settings = load_settings()
        assert settings["ai"]["provider"] == "openai"
        # idf defaults still present
        assert settings["idf"]["path"] == ""

    def test_partial_ai_section_merges(self, tmp_config_dir):
        # Only override model; provider should retain default "ollama"
        tmp_config_dir["file"].write_text(
            '[ai]\nmodel = "gpt-4o"\n', encoding="utf-8"
        )
        settings = load_settings()
        assert settings["ai"]["model"] == "gpt-4o"
        assert settings["ai"]["provider"] == "ollama"


# ---------------------------------------------------------------------------
# save_settings / round-trip
# ---------------------------------------------------------------------------

class TestSaveSettings:
    def test_creates_file(self, tmp_config_dir):
        settings = load_settings()
        save_settings(settings)
        assert tmp_config_dir["file"].exists()

    def test_roundtrip_ai_provider(self, tmp_config_dir):
        settings = load_settings()
        settings["ai"]["provider"] = "anthropic"
        save_settings(settings)

        loaded = load_settings()
        assert loaded["ai"]["provider"] == "anthropic"

    def test_roundtrip_idf_path(self, tmp_config_dir):
        settings = load_settings()
        settings["idf"]["path"] = "/opt/esp/esp-idf"
        save_settings(settings)

        loaded = load_settings()
        assert loaded["idf"]["path"] == "/opt/esp/esp-idf"

    def test_roundtrip_api_key(self, tmp_config_dir):
        settings = load_settings()
        settings["ai"]["api_key"] = "sk-test-key-12345"
        save_settings(settings)

        loaded = load_settings()
        assert loaded["ai"]["api_key"] == "sk-test-key-12345"

    def test_creates_parent_directories(self, tmp_path, monkeypatch):
        deep_dir = tmp_path / "deep" / "nested" / "analogdata-esp"
        deep_file = deep_dir / "config.toml"
        monkeypatch.setattr(settings_module, "CONFIG_DIR", deep_dir)
        monkeypatch.setattr(settings_module, "CONFIG_FILE", deep_file)

        settings = load_settings()
        save_settings(settings)
        assert deep_file.exists()

    def test_file_is_valid_toml(self, tmp_config_dir):
        """Saved file should be parseable by tomllib."""
        import tomllib
        settings = load_settings()
        settings["ai"]["provider"] = "gemini"
        settings["ai"]["api_key"] = "AIza-test"
        save_settings(settings)

        content = tmp_config_dir["file"].read_bytes()
        parsed = tomllib.loads(content.decode())
        assert parsed["ai"]["provider"] == "gemini"


# ---------------------------------------------------------------------------
# get/set AI settings
# ---------------------------------------------------------------------------

class TestAISettings:
    def test_get_default_provider(self, tmp_config_dir):
        assert get_ai_setting("provider") == "ollama"

    def test_set_then_get_provider(self, tmp_config_dir):
        set_ai_setting("provider", "openai")
        assert get_ai_setting("provider") == "openai"

    def test_set_then_get_api_key(self, tmp_config_dir):
        set_ai_setting("api_key", "sk-abc123")
        assert get_ai_setting("api_key") == "sk-abc123"

    def test_set_then_get_model(self, tmp_config_dir):
        set_ai_setting("model", "gpt-4o-mini")
        assert get_ai_setting("model") == "gpt-4o-mini"

    def test_set_then_get_base_url(self, tmp_config_dir):
        set_ai_setting("base_url", "http://localhost:8000/v1")
        assert get_ai_setting("base_url") == "http://localhost:8000/v1"

    def test_get_missing_key_returns_empty_string(self, tmp_config_dir):
        assert get_ai_setting("nonexistent_key") == ""

    def test_multiple_set_operations_persist_all(self, tmp_config_dir):
        set_ai_setting("provider", "anthropic")
        set_ai_setting("model", "claude-3-5-sonnet-20241022")
        assert get_ai_setting("provider") == "anthropic"
        assert get_ai_setting("model") == "claude-3-5-sonnet-20241022"

    def test_overwrite_existing_key(self, tmp_config_dir):
        set_ai_setting("provider", "openai")
        set_ai_setting("provider", "gemini")
        assert get_ai_setting("provider") == "gemini"


# ---------------------------------------------------------------------------
# get/set IDF settings
# ---------------------------------------------------------------------------

class TestIDFSettings:
    def test_get_default_path(self, tmp_config_dir):
        assert get_idf_setting("path") == ""

    def test_set_then_get_path(self, tmp_config_dir):
        set_idf_setting("path", "/home/user/esp/esp-idf")
        assert get_idf_setting("path") == "/home/user/esp/esp-idf"

    def test_set_then_get_tools_path(self, tmp_config_dir):
        set_idf_setting("tools_path", "/home/user/.espressif/tools")
        assert get_idf_setting("tools_path") == "/home/user/.espressif/tools"

    def test_get_missing_idf_key_returns_empty(self, tmp_config_dir):
        assert get_idf_setting("nonexistent") == ""

    def test_idf_and_ai_settings_independent(self, tmp_config_dir):
        set_idf_setting("path", "/opt/esp")
        set_ai_setting("provider", "openai")
        assert get_idf_setting("path") == "/opt/esp"
        assert get_ai_setting("provider") == "openai"

    def test_overwrite_idf_path(self, tmp_config_dir):
        set_idf_setting("path", "/first/path")
        set_idf_setting("path", "/second/path")
        assert get_idf_setting("path") == "/second/path"
