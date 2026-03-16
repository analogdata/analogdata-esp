"""Tests for AI provider implementations."""

import json
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from typing import AsyncIterator

import pytest
import httpx

from analogdata_esp.agent.providers.base import BaseProvider, ESP_IDF_SYSTEM_PROMPT
from analogdata_esp.agent.providers.ollama import OllamaProvider
from analogdata_esp.agent.providers.openai_provider import OpenAIProvider
from analogdata_esp.agent.providers.anthropic_provider import AnthropicProvider
from analogdata_esp.agent.providers.gemini import GeminiProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _collect_stream(agen) -> list[str]:
    """Collect all chunks from an async generator into a list."""
    chunks = []
    async for chunk in agen:
        chunks.append(chunk)
    return chunks


async def _make_mock_stream_response(lines: list[str]):
    """
    Return a mock that behaves like an httpx streaming response context manager,
    yielding the given lines from aiter_lines().
    """
    async def _aiter_lines():
        for line in lines:
            yield line

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.aiter_lines = _aiter_lines

    # Make it work as async context manager
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)
    return mock_response


# ---------------------------------------------------------------------------
# BaseProvider.build_prompt
# ---------------------------------------------------------------------------

class TestBuildPrompt:
    """Test BaseProvider.build_prompt via a concrete subclass."""

    class _ConcreteProvider(BaseProvider):
        name = "test"
        default_model = "test-model"

        async def stream(self, prompt, system=ESP_IDF_SYSTEM_PROMPT):
            yield ""

        async def is_available(self):
            return True

    def setup_method(self):
        self.provider = self._ConcreteProvider()

    def test_question_only(self):
        prompt = self.provider.build_prompt("What is GPIO?", None, None)
        assert "User: What is GPIO?" in prompt
        assert "Build error" not in prompt
        assert "Project context" not in prompt

    def test_with_context(self):
        prompt = self.provider.build_prompt("Help me", None, "Project: blink\nTarget: esp32")
        assert "Project context:" in prompt
        assert "blink" in prompt
        assert "User: Help me" in prompt

    def test_with_build_error(self):
        prompt = self.provider.build_prompt("Fix this", "error: undeclared", None)
        assert "Build error output:" in prompt
        assert "error: undeclared" in prompt
        assert "```" in prompt

    def test_with_both_context_and_error(self):
        prompt = self.provider.build_prompt(
            "Why?",
            "error: something",
            "Project: demo",
        )
        assert "Project context:" in prompt
        assert "Build error output:" in prompt
        assert "User: Why?" in prompt

    def test_sections_separated_by_double_newline(self):
        prompt = self.provider.build_prompt(
            "Q",
            "error: x",
            "ctx",
        )
        assert "\n\n" in prompt

    def test_empty_context_not_included(self):
        prompt = self.provider.build_prompt("Q", None, "")
        assert "Project context:" not in prompt

    def test_empty_build_error_not_included(self):
        prompt = self.provider.build_prompt("Q", "", None)
        assert "Build error" not in prompt


# ---------------------------------------------------------------------------
# OllamaProvider
# ---------------------------------------------------------------------------

class TestOllamaProvider:
    def test_default_values(self):
        provider = OllamaProvider()
        assert provider.name == "ollama"
        assert provider.base_url == "http://localhost:11434"
        assert provider.model == "gemma3"

    def test_custom_base_url_strips_trailing_slash(self):
        provider = OllamaProvider(base_url="http://localhost:11434/")
        assert provider.base_url == "http://localhost:11434"

    def test_custom_model(self):
        provider = OllamaProvider(model="llama3:8b")
        assert provider.model == "llama3:8b"

    @pytest.mark.asyncio
    async def test_is_available_true_when_model_in_list(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "models": [{"name": "gemma3:4b"}, {"name": "llama3:8b"}]
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            provider = OllamaProvider(model="gemma3:4b")
            result = await provider.is_available()

        assert result is True

    @pytest.mark.asyncio
    async def test_is_available_false_when_model_not_in_list(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"name": "llama3:8b"}]}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            provider = OllamaProvider(model="gemma3:4b")
            result = await provider.is_available()

        assert result is False

    @pytest.mark.asyncio
    async def test_is_available_false_when_non_200(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 503

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            provider = OllamaProvider()
            result = await provider.is_available()

        assert result is False

    @pytest.mark.asyncio
    async def test_is_available_false_on_connection_refused(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            provider = OllamaProvider()
            result = await provider.is_available()

        assert result is False

    @pytest.mark.asyncio
    async def test_is_available_true_wildcard_model(self):
        """Wildcard '*' picks the first available model when list is non-empty."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"name": "llama3:latest"}]}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            provider = OllamaProvider(model="*")
            result = await provider.is_available()

        assert result is True
        assert provider.model == "llama3:latest"   # model updated to actual name

    @pytest.mark.asyncio
    async def test_is_available_prefix_match(self):
        """gemma3:latest should match when model prefix is gemma3."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"name": "gemma3:latest"}]}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            provider = OllamaProvider(model="gemma3:4b")
            result = await provider.is_available()

        assert result is True

    @pytest.mark.asyncio
    async def test_stream_yields_tokens(self):
        lines = [
            json.dumps({"response": "Hello", "done": False}),
            json.dumps({"response": " world", "done": False}),
            json.dumps({"response": "", "done": True}),
        ]
        mock_response = await _make_mock_stream_response(lines)
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            provider = OllamaProvider()
            chunks = await _collect_stream(provider.stream("test prompt"))

        assert "Hello" in chunks
        assert " world" in chunks

    @pytest.mark.asyncio
    async def test_stream_stops_at_done(self):
        lines = [
            json.dumps({"response": "token1", "done": False}),
            json.dumps({"response": "token2", "done": True}),
            # This line should NOT be yielded because done=True above
            json.dumps({"response": "token3", "done": False}),
        ]
        mock_response = await _make_mock_stream_response(lines)
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            provider = OllamaProvider()
            chunks = await _collect_stream(provider.stream("prompt"))

        assert "token3" not in chunks

    @pytest.mark.asyncio
    async def test_stream_skips_empty_lines(self):
        lines = [
            "",
            "   ",
            json.dumps({"response": "valid", "done": True}),
        ]
        mock_response = await _make_mock_stream_response(lines)
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            provider = OllamaProvider()
            chunks = await _collect_stream(provider.stream("prompt"))

        assert chunks == ["valid"]

    @pytest.mark.asyncio
    async def test_stream_yields_error_on_http_error(self):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "500", request=MagicMock(), response=MagicMock(status_code=500)
            )
        )
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            provider = OllamaProvider()
            chunks = await _collect_stream(provider.stream("prompt"))

        assert any("[Error]" in c for c in chunks)


# ---------------------------------------------------------------------------
# OpenAIProvider
# ---------------------------------------------------------------------------

class TestOpenAIProvider:
    def test_name_and_default_model(self):
        provider = OpenAIProvider(api_key="sk-test")
        assert provider.name == "openai"
        assert provider.default_model == "gpt-4o"

    def test_custom_model(self):
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini")
        assert provider.model == "gpt-4o-mini"

    def test_base_url_strips_trailing_slash(self):
        provider = OpenAIProvider(api_key="sk-test", base_url="https://api.openai.com/v1/")
        assert provider.base_url == "https://api.openai.com/v1"

    @pytest.mark.asyncio
    async def test_is_available_true_with_api_key(self):
        provider = OpenAIProvider(api_key="sk-abc123")
        assert await provider.is_available() is True

    @pytest.mark.asyncio
    async def test_is_available_false_when_empty_key(self):
        provider = OpenAIProvider(api_key="")
        assert await provider.is_available() is False

    @pytest.mark.asyncio
    async def test_is_available_false_when_whitespace_key(self):
        provider = OpenAIProvider(api_key="   ")
        assert await provider.is_available() is False

    @pytest.mark.asyncio
    async def test_stream_yields_tokens_from_sse(self):
        lines = [
            'data: ' + json.dumps({"choices": [{"delta": {"content": "Hello"}}]}),
            'data: ' + json.dumps({"choices": [{"delta": {"content": " ESP"}}]}),
            "data: [DONE]",
        ]
        mock_response = await _make_mock_stream_response(lines)
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            provider = OpenAIProvider(api_key="sk-test")
            chunks = await _collect_stream(provider.stream("test"))

        assert "Hello" in chunks
        assert " ESP" in chunks

    @pytest.mark.asyncio
    async def test_stream_stops_at_done_marker(self):
        lines = [
            'data: ' + json.dumps({"choices": [{"delta": {"content": "token1"}}]}),
            "data: [DONE]",
            'data: ' + json.dumps({"choices": [{"delta": {"content": "token2"}}]}),
        ]
        mock_response = await _make_mock_stream_response(lines)
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            provider = OpenAIProvider(api_key="sk-test")
            chunks = await _collect_stream(provider.stream("test"))

        assert "token1" in chunks
        assert "token2" not in chunks

    @pytest.mark.asyncio
    async def test_stream_skips_empty_lines(self):
        lines = [
            "",
            'data: ' + json.dumps({"choices": [{"delta": {"content": "ok"}}]}),
            "data: [DONE]",
        ]
        mock_response = await _make_mock_stream_response(lines)
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            provider = OpenAIProvider(api_key="sk-test")
            chunks = await _collect_stream(provider.stream("test"))

        assert "ok" in chunks

    @pytest.mark.asyncio
    async def test_stream_skips_lines_without_data_prefix(self):
        lines = [
            "event: message",
            'data: ' + json.dumps({"choices": [{"delta": {"content": "data"}}]}),
            "data: [DONE]",
        ]
        mock_response = await _make_mock_stream_response(lines)
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            provider = OpenAIProvider(api_key="sk-test")
            chunks = await _collect_stream(provider.stream("test"))

        assert chunks == ["data"]

    @pytest.mark.asyncio
    async def test_stream_yields_error_on_http_error(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "401",
                request=MagicMock(),
                response=MagicMock(status_code=401, text="Unauthorized"),
            )
        )
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            provider = OpenAIProvider(api_key="sk-test")
            chunks = await _collect_stream(provider.stream("test"))

        assert any("[Error]" in c for c in chunks)


# ---------------------------------------------------------------------------
# AnthropicProvider
# ---------------------------------------------------------------------------

class TestAnthropicProvider:
    def test_name_and_default_model(self):
        provider = AnthropicProvider(api_key="sk-ant-test")
        assert provider.name == "anthropic"
        assert "claude" in provider.default_model.lower()

    def test_custom_model(self):
        provider = AnthropicProvider(api_key="sk-ant", model="claude-3-haiku-20240307")
        assert provider.model == "claude-3-haiku-20240307"

    @pytest.mark.asyncio
    async def test_is_available_true_with_key(self):
        provider = AnthropicProvider(api_key="sk-ant-abc")
        assert await provider.is_available() is True

    @pytest.mark.asyncio
    async def test_is_available_false_when_empty(self):
        provider = AnthropicProvider(api_key="")
        assert await provider.is_available() is False

    @pytest.mark.asyncio
    async def test_is_available_false_when_whitespace(self):
        provider = AnthropicProvider(api_key="  ")
        assert await provider.is_available() is False

    @pytest.mark.asyncio
    async def test_stream_yields_text_delta_tokens(self):
        lines = [
            'data: ' + json.dumps({
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": "Hello"},
            }),
            'data: ' + json.dumps({
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": " Claude"},
            }),
            'data: ' + json.dumps({"type": "message_stop"}),
        ]
        mock_response = await _make_mock_stream_response(lines)
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            provider = AnthropicProvider(api_key="sk-ant-test")
            chunks = await _collect_stream(provider.stream("test"))

        assert "Hello" in chunks
        assert " Claude" in chunks

    @pytest.mark.asyncio
    async def test_stream_stops_at_message_stop(self):
        lines = [
            'data: ' + json.dumps({
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": "before_stop"},
            }),
            'data: ' + json.dumps({"type": "message_stop"}),
            'data: ' + json.dumps({
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": "after_stop"},
            }),
        ]
        mock_response = await _make_mock_stream_response(lines)
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            provider = AnthropicProvider(api_key="sk-ant-test")
            chunks = await _collect_stream(provider.stream("test"))

        assert "before_stop" in chunks
        assert "after_stop" not in chunks

    @pytest.mark.asyncio
    async def test_stream_ignores_non_text_delta_events(self):
        lines = [
            'data: ' + json.dumps({"type": "message_start", "message": {}}),
            'data: ' + json.dumps({"type": "content_block_start", "index": 0}),
            'data: ' + json.dumps({
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": "actual_text"},
            }),
            'data: ' + json.dumps({"type": "message_stop"}),
        ]
        mock_response = await _make_mock_stream_response(lines)
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            provider = AnthropicProvider(api_key="sk-ant-test")
            chunks = await _collect_stream(provider.stream("test"))

        assert chunks == ["actual_text"]

    @pytest.mark.asyncio
    async def test_stream_yields_error_on_http_error(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "403",
                request=MagicMock(),
                response=MagicMock(status_code=403, text="Forbidden"),
            )
        )
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            provider = AnthropicProvider(api_key="sk-ant-test")
            chunks = await _collect_stream(provider.stream("test"))

        assert any("[Error]" in c for c in chunks)


# ---------------------------------------------------------------------------
# GeminiProvider
# ---------------------------------------------------------------------------

class TestGeminiProvider:
    def test_name_and_default_model(self):
        provider = GeminiProvider(api_key="AIza-test")
        assert provider.name == "gemini"
        assert "gemini" in provider.default_model.lower()

    def test_custom_model(self):
        provider = GeminiProvider(api_key="AIza-test", model="gemini-1.5-pro")
        assert provider.model == "gemini-1.5-pro"

    @pytest.mark.asyncio
    async def test_is_available_true_with_key(self):
        provider = GeminiProvider(api_key="AIza-abc123")
        assert await provider.is_available() is True

    @pytest.mark.asyncio
    async def test_is_available_false_when_empty(self):
        provider = GeminiProvider(api_key="")
        assert await provider.is_available() is False

    @pytest.mark.asyncio
    async def test_is_available_false_when_whitespace(self):
        provider = GeminiProvider(api_key="   ")
        assert await provider.is_available() is False

    @pytest.mark.asyncio
    async def test_stream_yields_text_from_candidates(self):
        lines = [
            'data: ' + json.dumps({
                "candidates": [{
                    "content": {
                        "parts": [{"text": "Hello"}]
                    }
                }]
            }),
            'data: ' + json.dumps({
                "candidates": [{
                    "content": {
                        "parts": [{"text": " Gemini"}]
                    }
                }]
            }),
        ]
        mock_response = await _make_mock_stream_response(lines)
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            provider = GeminiProvider(api_key="AIza-test")
            chunks = await _collect_stream(provider.stream("test"))

        assert "Hello" in chunks
        assert " Gemini" in chunks

    @pytest.mark.asyncio
    async def test_stream_handles_multiple_parts(self):
        lines = [
            'data: ' + json.dumps({
                "candidates": [{
                    "content": {
                        "parts": [{"text": "part1"}, {"text": "part2"}]
                    }
                }]
            }),
        ]
        mock_response = await _make_mock_stream_response(lines)
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            provider = GeminiProvider(api_key="AIza-test")
            chunks = await _collect_stream(provider.stream("test"))

        assert "part1" in chunks
        assert "part2" in chunks

    @pytest.mark.asyncio
    async def test_stream_skips_empty_lines(self):
        lines = [
            "",
            'data: ' + json.dumps({
                "candidates": [{"content": {"parts": [{"text": "ok"}]}}]
            }),
        ]
        mock_response = await _make_mock_stream_response(lines)
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            provider = GeminiProvider(api_key="AIza-test")
            chunks = await _collect_stream(provider.stream("test"))

        assert "ok" in chunks

    @pytest.mark.asyncio
    async def test_stream_yields_error_on_http_error(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "400",
                request=MagicMock(),
                response=MagicMock(status_code=400, text="Bad Request"),
            )
        )
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            provider = GeminiProvider(api_key="AIza-test")
            chunks = await _collect_stream(provider.stream("test"))

        assert any("[Error]" in c for c in chunks)

    @pytest.mark.asyncio
    async def test_stream_yields_error_on_exception(self):
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(side_effect=Exception("network failure"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            provider = GeminiProvider(api_key="AIza-test")
            chunks = await _collect_stream(provider.stream("test"))

        assert any("[Error]" in c for c in chunks)
