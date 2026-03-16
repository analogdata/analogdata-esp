"""Anthropic (Claude) provider.

Uses the Anthropic Messages API with SSE streaming.
Set your API key with:  analogdata-esp config ai  → select Anthropic
"""
import json
from typing import AsyncIterator

import httpx

from analogdata_esp.agent.providers.base import BaseProvider, ESP_IDF_SYSTEM_PROMPT

# Anthropic Messages API endpoint — all requests go here
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

# API version header required by Anthropic — must match a supported version string
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider(BaseProvider):
    name = "anthropic"
    default_model = "claude-3-5-sonnet-20241022"

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        self.api_key = api_key
        self.model   = model or self.default_model

    async def is_available(self) -> bool:
        """Return True if an API key is configured."""
        return bool(self.api_key and self.api_key.strip())

    async def stream(self, prompt: str, system: str = ESP_IDF_SYSTEM_PROMPT) -> AsyncIterator[str]:
        """Stream response tokens via Anthropic Messages SSE.

        Anthropic uses a different SSE event format than OpenAI:
        - Events have a "type" field (e.g. "content_block_delta", "message_stop")
        - Text deltas are inside: data.delta.text  (when type == "content_block_delta")
        - Stream ends when type == "message_stop"
        """
        headers = {
            "x-api-key":         self.api_key,      # Anthropic uses x-api-key, not Bearer
            "anthropic-version": ANTHROPIC_VERSION,  # required version header
            "content-type":      "application/json",
            "accept":            "text/event-stream",  # request SSE response format
        }
        payload = {
            "model":      self.model,
            "max_tokens": 4096,    # Anthropic requires explicit max_tokens
            "system":     system,  # the ESP-IDF system prompt (separate field in Anthropic API)
            "messages": [
                {"role": "user", "content": prompt},  # assembled question + context
            ],
            "stream": True,
        }
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream(
                    "POST",
                    ANTHROPIC_API_URL,
                    headers=headers,
                    json=payload,
                ) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue

                        # Anthropic SSE lines: "data: {...json...}"
                        if line.startswith("data: "):
                            data_str = line[len("data: "):]
                            try:
                                data       = json.loads(data_str)
                                event_type = data.get("type", "")

                                # content_block_delta carries the actual text tokens
                                if event_type == "content_block_delta":
                                    delta = data.get("delta", {})
                                    # type == "text_delta" means the delta.text field has content
                                    if delta.get("type") == "text_delta":
                                        text = delta.get("text", "")
                                        if text:
                                            yield text

                                # message_stop = stream is complete
                                elif event_type == "message_stop":
                                    break

                            except json.JSONDecodeError:
                                continue   # malformed event — skip

        except httpx.HTTPStatusError as e:
            yield f"\n[Error] Anthropic HTTP error: {e.response.status_code} — {e.response.text}\n"
        except Exception as e:
            yield f"\n[Error] Anthropic stream failed: {e}\n"
