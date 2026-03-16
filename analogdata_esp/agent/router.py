"""AI Agent Router — reads the provider from user settings and dispatches to it.

This is the single function the rest of the app calls: ask_agent().
It figures out which provider the user configured (ollama / openai / anthropic /
gemini), constructs the right provider object, builds the full prompt, and
streams back response tokens one at a time.
"""
import os
from typing import Optional, AsyncIterator

from rich.console import Console

# load_settings reads ~/.config/analogdata-esp/config.toml
from analogdata_esp.core.settings import load_settings

# BaseProvider is the abstract base class all providers implement.
# ESP_IDF_SYSTEM_PROMPT is the big system prompt with all idf.py command knowledge.
from analogdata_esp.agent.providers.base import ESP_IDF_SYSTEM_PROMPT, BaseProvider

# Each provider class wraps a different LLM backend
from analogdata_esp.agent.providers.ollama import OllamaProvider
from analogdata_esp.agent.providers.openai_provider import OpenAIProvider
from analogdata_esp.agent.providers.anthropic_provider import AnthropicProvider
from analogdata_esp.agent.providers.gemini import GeminiProvider

console = Console()


def _get_provider() -> BaseProvider:
    """Read saved settings and return the configured AI provider instance.

    Priority for API keys: environment variable > saved config file.
    This lets CI/CD or dotenv files override the interactive config.
    """
    settings = load_settings()
    ai = settings.get("ai", {})

    # Which provider the user picked via `analogdata-esp config ai`
    provider = ai.get("provider", "ollama")
    model    = ai.get("model", "")

    # Environment variables take precedence over the saved key
    api_key = (
        os.environ.get("OPENAI_API_KEY")    or
        os.environ.get("ANTHROPIC_API_KEY") or
        os.environ.get("GEMINI_API_KEY")    or
        ai.get("api_key", "")               # fallback: saved in config.toml
    )
    base_url = ai.get("base_url", "")   # custom Ollama server URL if not localhost

    # Construct and return the matching provider object
    if provider == "openai":
        key = os.environ.get("OPENAI_API_KEY") or api_key
        return OpenAIProvider(api_key=key, model=model or "gpt-4o")
    elif provider == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY") or api_key
        return AnthropicProvider(api_key=key, model=model or "claude-3-5-sonnet-20241022")
    elif provider == "gemini":
        key = os.environ.get("GEMINI_API_KEY") or api_key
        return GeminiProvider(api_key=key, model=model or "gemini-2.0-flash")
    else:  # ollama (default)
        url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        return OllamaProvider(base_url=url, model=model or "gemma3")


async def ask_agent(
    question: str,
    build_error: Optional[str] = None,    # last build error lines (auto-attached to context)
    context: Optional[str] = None,         # project name, chip, IDF version text
    system_override: Optional[str] = None, # swap in agent-mode prompt (with tool schema) when needed
    history: Optional[list] = None,        # list of {"role": "user"|"assistant", "content": "..."}
) -> AsyncIterator[str]:
    """Stream response tokens for a user question.

    This is an async generator — callers iterate with `async for chunk in ask_agent(...)`.
    Each yielded value is a piece of text (word, sentence, or single character depending
    on the provider's streaming granularity).
    """
    provider = _get_provider()

    # build_prompt assembles: project context + build error + history + question → one string
    prompt = provider.build_prompt(question, build_error, context, history=history)

    # Use the override (e.g. agent-mode prompt with tool schema) or the standard Q&A prompt
    system = system_override or ESP_IDF_SYSTEM_PROMPT

    # Check the backend is reachable before we try to stream
    if not await provider.is_available():
        # Yield a single helpful error message rather than streaming nothing
        yield _no_backend_message(provider)
        return

    # Log which provider/model is being used (shown dimly so it doesn't clutter the output)
    model_display = getattr(provider, "model", provider.default_model)
    console.print(f"[dim]🤖 Using {provider.name} ({model_display})[/dim]")

    # Forward each text token from the provider's stream to our caller
    async for chunk in provider.stream(prompt, system=system):
        yield chunk


def _no_backend_message(provider: BaseProvider) -> str:
    """Return a helpful error string when the provider is unreachable.

    For Ollama: explains how to start the server and pull a model.
    For cloud providers: directs to `config ai` to set an API key.
    """
    name = provider.name
    if name == "ollama":
        return (
            "\n[bold red]❌ Ollama not running.[/bold red]\n\n"
            "Start Ollama:  [cyan]ollama serve[/cyan]\n"
            "Pull a model:  [cyan]ollama pull gemma3:4b[/cyan]\n"
            "Or switch provider:  [cyan]analogdata-esp config ai[/cyan]\n"
        )
    else:
        return (
            f"\n[bold red]❌ {name} not configured.[/bold red]\n\n"
            f"Set API key:  [cyan]analogdata-esp config ai[/cyan]\n"
        )
