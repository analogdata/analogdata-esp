"""OpenAI provider (and compatible APIs such as Together, Groq, etc.).

Uses the /chat/completions endpoint with Server-Sent Events (SSE) streaming.
Set your API key with:  analogdata-esp config ai  → select OpenAI
"""
import json
from typing import AsyncIterator

import httpx

from analogdata_esp.agent.providers.base import BaseProvider, ESP_IDF_SYSTEM_PROMPT


class OpenAIProvider(BaseProvider):
    name = "openai"
    default_model = "gpt-4o"

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        # base_url can be changed to point at any OpenAI-compatible API
        base_url: str = "https://api.openai.com/v1",
    ):
        self.api_key  = api_key
        self.model    = model or self.default_model
        self.base_url = base_url.rstrip("/")   # strip trailing slash for clean URL joining

    async def is_available(self) -> bool:
        """Return True if an API key is configured (we can't test without a real call)."""
        return bool(self.api_key and self.api_key.strip())

    async def stream(self, prompt: str, system: str = ESP_IDF_SYSTEM_PROMPT) -> AsyncIterator[str]:
        """Stream response tokens via OpenAI /chat/completions SSE.

        The request uses the chat format with a system message and a user message.
        The response is Server-Sent Events (SSE) — lines prefixed with "data: ".
        Each data line contains a JSON delta with a partial content string.
        The stream ends when a "data: [DONE]" line arrives.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",  # API key in Bearer token format
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},   # ESP-IDF expert instructions
                {"role": "user",   "content": prompt},   # assembled user question + context
            ],
            "stream": True,   # enables SSE streaming response
        }
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                ) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue   # blank lines are SSE comment separators

                        # OpenAI SSE lines look like: "data: {...json...}"
                        if line.startswith("data: "):
                            data_str = line[len("data: "):]   # strip the "data: " prefix

                            if data_str == "[DONE]":
                                break   # stream finished

                            try:
                                data    = json.loads(data_str)
                                choices = data.get("choices", [])
                                if choices:
                                    # "delta" contains the incremental text for this chunk
                                    delta   = choices[0].get("delta", {})
                                    content = delta.get("content")
                                    if content:
                                        yield content   # yield this token to the caller
                            except json.JSONDecodeError:
                                continue   # malformed SSE line — skip

        except httpx.HTTPStatusError as e:
            yield f"\n[Error] OpenAI HTTP error: {e.response.status_code} — {e.response.text}\n"
        except Exception as e:
            yield f"\n[Error] OpenAI stream failed: {e}\n"
