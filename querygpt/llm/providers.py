"""
Concrete LLM provider implementations.

Adding a new provider (e.g. Google Gemini) means only adding a new class here.
No other module needs to change (Open/Closed Principle).
"""
from __future__ import annotations

import json
import logging

from querygpt.llm.base import LLMError, LLMMessage, LLMProvider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------

class AnthropicLLMProvider(LLMProvider):
    """Wrapper around the Anthropic Messages API."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-haiku-20241022",
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> None:
        try:
            import anthropic as _anthropic
        except ImportError as exc:
            raise ImportError("Install anthropic: pip install anthropic") from exc

        self._client = _anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._default_max_tokens = max_tokens
        self._default_temperature = temperature

    def complete(
        self,
        messages: list[LLMMessage],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        response_format: str = "text",
    ) -> str:
        system_msgs = [m for m in messages if m.role == "system"]
        user_msgs   = [m for m in messages if m.role != "system"]

        system_str = "\n\n".join(m.content for m in system_msgs)
        api_messages = [{"role": m.role, "content": m.content} for m in user_msgs]

        try:
            resp = self._client.messages.create(
                model=self._model,
                system=system_str or "You are a helpful SQL expert.",
                messages=api_messages,
                max_tokens=max_tokens or self._default_max_tokens,
                temperature=temperature if temperature is not None else self._default_temperature,
            )
            return resp.content[0].text
        except Exception as exc:
            logger.error("Anthropic API error: %s", exc)
            raise LLMError(str(exc)) from exc


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------

class OpenAILLMProvider(LLMProvider):
    """Wrapper around the OpenAI Chat Completions API."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        max_tokens: int = 4096,
        temperature: float = 0.0,
        base_url: str | None = None,
        supports_json_response_format: bool = True,
    ) -> None:
        try:
            import openai as _openai
        except ImportError as exc:
            raise ImportError("Install openai: pip install openai") from exc

        self._client = _openai.OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._default_max_tokens = max_tokens
        self._default_temperature = temperature
        self._supports_json_response_format = supports_json_response_format

    def complete(
        self,
        messages: list[LLMMessage],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        response_format: str = "text",
    ) -> str:
        api_messages = [{"role": m.role, "content": m.content} for m in messages]

        kwargs: dict = dict(
            model=self._model,
            messages=api_messages,
            max_tokens=max_tokens or self._default_max_tokens,
            temperature=temperature if temperature is not None else self._default_temperature,
        )
        if response_format == "json" and self._supports_json_response_format:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            resp = self._client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content
        except Exception as exc:
            logger.error("OpenAI API error: %s", exc)
            raise LLMError(str(exc)) from exc


# ---------------------------------------------------------------------------
# Google Gemini
# ---------------------------------------------------------------------------

class GeminiLLMProvider(LLMProvider):
    """Wrapper around Google Gemini API."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> None:
        try:
            import google.generativeai as _genai
        except ImportError as exc:
            raise ImportError(
                "Install google-generativeai: pip install google-generativeai"
            ) from exc

        _genai.configure(api_key=api_key)
        self._client = _genai
        self._model = model
        self._default_max_tokens = max_tokens
        self._default_temperature = temperature

    def complete(
        self,
        messages: list[LLMMessage],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        response_format: str = "text",
    ) -> str:
        # Separate system and user messages
        system_msgs = [m for m in messages if m.role == "system"]
        user_msgs = [m for m in messages if m.role != "system"]

        system_str = "\n\n".join(m.content for m in system_msgs)

        # Convert messages to Gemini format
        history = []
        for msg in user_msgs[:-1]:  # All but last
            history.append(
                {"role": "user" if msg.role == "user" else "model", "parts": msg.content}
            )

        # Last message
        user_content = user_msgs[-1].content if user_msgs else ""

        try:
            model = self._client.GenerativeModel(
                model_name=self._model,
                system_instruction=system_str or "You are a helpful SQL expert.",
                generation_config={
                    "temperature": temperature
                    if temperature is not None
                    else self._default_temperature,
                    "max_output_tokens": max_tokens or self._default_max_tokens,
                    "response_mime_type": "application/json"
                    if response_format == "json"
                    else "text/plain",
                },
            )
            chat = model.start_chat(history=history)
            response = chat.send_message(user_content)
            return response.text
        except Exception as exc:
            logger.error("Gemini API error: %s", exc)
            raise LLMError(str(exc)) from exc


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_llm_provider(provider: str, **kwargs) -> LLMProvider:
    """
    Factory function – decouples callers from concrete classes.
    Usage: build_llm_provider("anthropic", api_key="...", model="...")
    """
    provider = provider.lower()
    
    if provider == "lmstudio":
        # LM Studio exposes an OpenAI-compatible API, usually at http://localhost:1234/v1
        kwargs.setdefault("api_key", "lm-studio")
        kwargs.setdefault("base_url", "http://localhost:312/v1")
        kwargs.setdefault("supports_json_response_format", False)
        return OpenAILLMProvider(**kwargs)
        
    if provider == "ollama":
        # Ollama exposes an OpenAI-compatible API, usually at http://localhost:11434/v1
        kwargs.setdefault("api_key", "ollama")
        kwargs.setdefault("base_url", "http://localhost:11434/v1")
        kwargs.setdefault("supports_json_response_format", False)
        return OpenAILLMProvider(**kwargs)

    registry: dict[str, type[LLMProvider]] = {
        "anthropic": AnthropicLLMProvider,
        "openai":    OpenAILLMProvider,
        "gemini":    GeminiLLMProvider,
    }
    cls = registry.get(provider)
    if cls is None:
        raise ValueError(
            f"Unknown LLM provider '{provider}'. "
            f"Available: {list(registry.keys())} + ['lmstudio', 'ollama']"
        )
    return cls(**kwargs)