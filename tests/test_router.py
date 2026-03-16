"""Tests for analogdata_esp.agent.router."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from analogdata_esp.agent.router import (
    _get_provider,
    ask_agent,
    _no_backend_message,
)
from analogdata_esp.agent.providers.ollama import OllamaProvider
from analogdata_esp.agent.providers.openai_provider import OpenAIProvider
from analogdata_esp.agent.providers.anthropic_provider import AnthropicProvider
from analogdata_esp.agent.providers.gemini import GeminiProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings(
    provider: str = "ollama",
    model: str = "",
    api_key: str = "",
    base_url: str = "",
) -> dict:
    return {
        "ai": {
            "provider": provider,
            "model": model,
            "api_key": api_key,
            "base_url": base_url,
        }
    }


async def _collect_stream(agen) -> list[str]:
    chunks = []
    async for chunk in agen:
        chunks.append(chunk)
    return chunks


# ---------------------------------------------------------------------------
# _get_provider
# ---------------------------------------------------------------------------

class TestGetProvider:
    def test_returns_ollama_by_default(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)

        with patch("analogdata_esp.agent.router.load_settings", return_value=_make_settings("ollama")):
            provider = _get_provider()

        assert isinstance(provider, OllamaProvider)

    def test_returns_openai_when_configured(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        with patch(
            "analogdata_esp.agent.router.load_settings",
            return_value=_make_settings("openai", api_key="sk-test"),
        ):
            provider = _get_provider()

        assert isinstance(provider, OpenAIProvider)

    def test_returns_anthropic_when_configured(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        with patch(
            "analogdata_esp.agent.router.load_settings",
            return_value=_make_settings("anthropic", api_key="sk-ant-test"),
        ):
            provider = _get_provider()

        assert isinstance(provider, AnthropicProvider)

    def test_returns_gemini_when_configured(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        with patch(
            "analogdata_esp.agent.router.load_settings",
            return_value=_make_settings("gemini", api_key="AIza-test"),
        ):
            provider = _get_provider()

        assert isinstance(provider, GeminiProvider)

    def test_uses_openai_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        with patch(
            "analogdata_esp.agent.router.load_settings",
            return_value=_make_settings("openai"),
        ):
            provider = _get_provider()

        assert isinstance(provider, OpenAIProvider)
        assert provider.api_key == "sk-from-env"

    def test_env_var_takes_precedence_over_saved_key(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env-key")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        with patch(
            "analogdata_esp.agent.router.load_settings",
            return_value=_make_settings("openai", api_key="sk-saved-key"),
        ):
            provider = _get_provider()

        assert provider.api_key == "sk-env-key"

    def test_uses_anthropic_api_key_from_env(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-env")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        with patch(
            "analogdata_esp.agent.router.load_settings",
            return_value=_make_settings("anthropic"),
        ):
            provider = _get_provider()

        assert isinstance(provider, AnthropicProvider)
        assert provider.api_key == "sk-ant-env"

    def test_uses_gemini_api_key_from_env(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("GEMINI_API_KEY", "AIza-env")

        with patch(
            "analogdata_esp.agent.router.load_settings",
            return_value=_make_settings("gemini"),
        ):
            provider = _get_provider()

        assert isinstance(provider, GeminiProvider)
        assert provider.api_key == "AIza-env"

    def test_ollama_uses_custom_base_url_from_settings(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)

        with patch(
            "analogdata_esp.agent.router.load_settings",
            return_value=_make_settings("ollama", base_url="http://remote:11434"),
        ):
            provider = _get_provider()

        assert isinstance(provider, OllamaProvider)
        assert provider.base_url == "http://remote:11434"

    def test_ollama_uses_env_base_url(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://192.168.1.5:11434")

        with patch(
            "analogdata_esp.agent.router.load_settings",
            return_value=_make_settings("ollama"),
        ):
            provider = _get_provider()

        assert isinstance(provider, OllamaProvider)
        assert provider.base_url == "http://192.168.1.5:11434"

    def test_openai_uses_custom_model(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        with patch(
            "analogdata_esp.agent.router.load_settings",
            return_value=_make_settings("openai", model="gpt-4o-mini", api_key="sk-t"),
        ):
            provider = _get_provider()

        assert provider.model == "gpt-4o-mini"

    def test_unknown_provider_falls_back_to_ollama(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)

        with patch(
            "analogdata_esp.agent.router.load_settings",
            return_value=_make_settings("unknown_provider"),
        ):
            provider = _get_provider()

        assert isinstance(provider, OllamaProvider)


# ---------------------------------------------------------------------------
# _no_backend_message
# ---------------------------------------------------------------------------

class TestNoBackendMessage:
    def test_ollama_message_mentions_ollama(self):
        provider = OllamaProvider()
        msg = _no_backend_message(provider)
        assert "Ollama" in msg or "ollama" in msg

    def test_ollama_message_suggests_serve(self):
        provider = OllamaProvider()
        msg = _no_backend_message(provider)
        assert "ollama serve" in msg

    def test_openai_message_mentions_name(self):
        provider = OpenAIProvider(api_key="")
        msg = _no_backend_message(provider)
        assert "openai" in msg.lower()

    def test_anthropic_message_mentions_name(self):
        provider = AnthropicProvider(api_key="")
        msg = _no_backend_message(provider)
        assert "anthropic" in msg.lower()

    def test_gemini_message_mentions_name(self):
        provider = GeminiProvider(api_key="")
        msg = _no_backend_message(provider)
        assert "gemini" in msg.lower()

    def test_non_ollama_mentions_api_key(self):
        provider = OpenAIProvider(api_key="")
        msg = _no_backend_message(provider)
        assert "api key" in msg.lower() or "API key" in msg


# ---------------------------------------------------------------------------
# ask_agent
# ---------------------------------------------------------------------------

class TestAskAgent:
    @pytest.mark.asyncio
    async def test_yields_no_backend_message_when_not_available(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        mock_provider = MagicMock()
        mock_provider.name = "ollama"
        mock_provider.default_model = "gemma3:4b"
        mock_provider.is_available = AsyncMock(return_value=False)
        mock_provider.build_prompt = MagicMock(return_value="prompt text")

        with patch("analogdata_esp.agent.router._get_provider", return_value=mock_provider):
            chunks = await _collect_stream(ask_agent("How do I blink an LED?"))

        assert len(chunks) == 1
        # The no-backend message should be the only yield
        assert len(chunks[0]) > 0

    @pytest.mark.asyncio
    async def test_streams_response_when_available(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        async def _fake_stream(prompt, system=None):
            yield "token1"
            yield " token2"

        mock_provider = MagicMock()
        mock_provider.name = "ollama"
        mock_provider.default_model = "gemma3:4b"
        mock_provider.model = "gemma3:4b"
        mock_provider.is_available = AsyncMock(return_value=True)
        mock_provider.build_prompt = MagicMock(return_value="prompt text")
        mock_provider.stream = _fake_stream

        with patch("analogdata_esp.agent.router._get_provider", return_value=mock_provider):
            chunks = await _collect_stream(ask_agent("How do I configure GPIO?"))

        assert "token1" in chunks
        assert " token2" in chunks

    @pytest.mark.asyncio
    async def test_build_prompt_called_with_correct_args(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        async def _fake_stream(prompt, system=None):
            yield "ok"

        mock_provider = MagicMock()
        mock_provider.name = "ollama"
        mock_provider.default_model = "gemma3:4b"
        mock_provider.model = "gemma3:4b"
        mock_provider.is_available = AsyncMock(return_value=True)
        mock_provider.build_prompt = MagicMock(return_value="built prompt")
        mock_provider.stream = _fake_stream

        with patch("analogdata_esp.agent.router._get_provider", return_value=mock_provider):
            await _collect_stream(
                ask_agent(
                    "Fix this error",
                    build_error="error: undeclared",
                    context="Project: blink",
                )
            )

        mock_provider.build_prompt.assert_called_once_with(
            "Fix this error", "error: undeclared", "Project: blink", history=None
        )

    @pytest.mark.asyncio
    async def test_no_chunks_yielded_after_error_message(self, monkeypatch):
        """When provider is unavailable, only one message is yielded (no stream)."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        async def _should_not_be_called(*args, **kwargs):
            yield "should not appear"

        mock_provider = MagicMock()
        mock_provider.name = "openai"
        mock_provider.default_model = "gpt-4o"
        mock_provider.is_available = AsyncMock(return_value=False)
        mock_provider.build_prompt = MagicMock(return_value="prompt")
        mock_provider.stream = _should_not_be_called

        with patch("analogdata_esp.agent.router._get_provider", return_value=mock_provider):
            chunks = await _collect_stream(ask_agent("question"))

        assert "should not appear" not in chunks

    @pytest.mark.asyncio
    async def test_ask_agent_with_no_optional_args(self, monkeypatch):
        """ask_agent works when called with only a question."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        async def _fake_stream(prompt, system=None):
            yield "response"

        mock_provider = MagicMock()
        mock_provider.name = "ollama"
        mock_provider.default_model = "gemma3:4b"
        mock_provider.model = "gemma3:4b"
        mock_provider.is_available = AsyncMock(return_value=True)
        mock_provider.build_prompt = MagicMock(return_value="prompt")
        mock_provider.stream = _fake_stream

        with patch("analogdata_esp.agent.router._get_provider", return_value=mock_provider):
            chunks = await _collect_stream(ask_agent("What is ESP-IDF?"))

        assert "response" in chunks
