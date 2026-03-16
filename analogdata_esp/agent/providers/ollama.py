"""Ollama local AI provider.

Ollama runs LLMs entirely on your machine — no API key required.
It exposes a REST API on localhost:11434 by default.

Install: https://ollama.com
Pull a model: ollama pull gemma3:4b
"""
import json
from typing import AsyncIterator

import httpx   # async HTTP client (faster than requests for streaming)

from analogdata_esp.agent.providers.base import BaseProvider, ESP_IDF_SYSTEM_PROMPT


class OllamaProvider(BaseProvider):
    name = "ollama"
    default_model = "gemma3"

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "gemma3"):
        # Strip trailing slash so we can safely append paths like /api/tags
        self.base_url = base_url.rstrip("/")
        # Fall back to default_model if an empty string was passed
        self.model = model or self.default_model

    async def is_available(self) -> bool:
        """Check if Ollama is running and a usable model exists.

        Tries exact match first, then falls back to any model sharing
        the same base name (e.g. configured 'gemma3:4b' → uses 'gemma3:1b'
        if that's all that's installed). Updates self.model in place so
        stream() always uses the real installed name.
        """
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # GET /api/tags returns the list of locally-pulled models
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code != 200:
                    return False   # Ollama is running but returned an error

                data = resp.json()
                # Extract just the model name strings from the response objects
                installed = [m.get("name", "") for m in data.get("models", [])]
                if not installed:
                    return False   # Ollama is running but no models are pulled

                # Special wildcard: use whatever model is installed first
                if self.model == "*":
                    self.model = installed[0]
                    return True

                # 1. Exact match — e.g. "gemma3:4b" is in the list
                if self.model in installed:
                    return True

                # 2. Base name match — "gemma3" matches "gemma3:1b", "gemma3:4b" etc.
                base = self.model.split(":")[0]   # "gemma3:4b" → "gemma3"
                for m in installed:
                    if m.startswith(base):
                        self.model = m   # update so stream() uses the real installed name
                        return True

                return False   # no variant of the requested model is installed

        except Exception:
            return False   # Ollama not running, connection refused, etc.

    async def stream(self, prompt: str, system: str = ESP_IDF_SYSTEM_PROMPT) -> AsyncIterator[str]:
        """Stream response tokens from Ollama /api/generate.

        Ollama streams NDJSON (newline-delimited JSON), one object per line.
        Each object has a "response" field with the next token text.
        """
        payload = {
            "model": self.model,
            "prompt": prompt,    # the user question + context assembled by build_prompt()
            "system": system,    # the ESP-IDF system prompt
            "stream": True,      # request streaming (line-by-line JSON)
        }
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                # client.stream() sends the request and reads the response body lazily
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/generate",
                    json=payload,
                ) as response:
                    response.raise_for_status()   # raise on 4xx/5xx

                    # aiter_lines() yields one line at a time as they arrive
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue   # skip empty lines (keep-alive pings)
                        try:
                            data  = json.loads(line)          # parse the NDJSON line
                            token = data.get("response", "")   # the text token
                            if token:
                                yield token                    # stream it to the caller
                            if data.get("done", False):
                                break                          # Ollama signals completion
                        except json.JSONDecodeError:
                            continue   # malformed line — skip it

        except httpx.HTTPStatusError as e:
            yield f"\n[Error] Ollama HTTP error: {e.response.status_code}\n"
        except Exception as e:
            yield f"\n[Error] Ollama stream failed: {e}\n"
