"""Google Gemini provider.

Uses the Generative Language API streamGenerateContent endpoint with SSE.
Set your API key with:  analogdata-esp config ai  → select Gemini
Get an API key at: https://aistudio.google.com/app/apikey
"""
import json
from typing import AsyncIterator

import httpx

from analogdata_esp.agent.providers.base import BaseProvider, ESP_IDF_SYSTEM_PROMPT

# Base URL for all Gemini model endpoints
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider(BaseProvider):
    name = "gemini"
    default_model = "gemini-2.0-flash"

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model   = model or self.default_model

    async def is_available(self) -> bool:
        """Return True if an API key is configured."""
        return bool(self.api_key and self.api_key.strip())

    async def stream(self, prompt: str, system: str = ESP_IDF_SYSTEM_PROMPT) -> AsyncIterator[str]:
        """Stream response tokens via Gemini streamGenerateContent.

        The URL includes the model name and the API key as a query parameter.
        alt=sse requests Server-Sent Events format.

        Gemini SSE response structure:
          data: {"candidates": [{"content": {"parts": [{"text": "..."}]}}]}
        """
        # Build the full URL: base/model:streamGenerateContent?key=...&alt=sse
        url = f"{GEMINI_BASE_URL}/{self.model}:streamGenerateContent?key={self.api_key}&alt=sse"

        payload = {
            # Gemini uses a separate "system_instruction" field (like Anthropic's "system")
            "system_instruction": {
                "parts": [{"text": system}]   # ESP-IDF expert system prompt
            },
            # The actual conversation turns
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],  # assembled question + context
                }
            ],
            "generationConfig": {
                "temperature": 0.7,   # moderate creativity (0=deterministic, 1=creative)
            },
        }
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream(
                    "POST",
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                ) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue

                        # Gemini SSE lines: "data: {...json...}"
                        if line.startswith("data: "):
                            data_str = line[len("data: "):]
                            try:
                                data       = json.loads(data_str)
                                candidates = data.get("candidates", [])

                                # Gemini can return multiple candidates — we use all of them
                                for candidate in candidates:
                                    content = candidate.get("content", {})
                                    parts   = content.get("parts", [])
                                    # Each "part" has a "text" field with the next token(s)
                                    for part in parts:
                                        text = part.get("text", "")
                                        if text:
                                            yield text

                            except json.JSONDecodeError:
                                continue   # malformed SSE line — skip

        except httpx.HTTPStatusError as e:
            yield f"\n[Error] Gemini HTTP error: {e.response.status_code} — {e.response.text}\n"
        except Exception as e:
            yield f"\n[Error] Gemini stream failed: {e}\n"
