"""
Abstract LLM provider.

Dependency Inversion  – agents call this interface, not Anthropic/OpenAI SDKs.
Open/Closed           – new providers (Gemini, local Ollama, etc.) are added
                        by subclassing, with zero changes to agents.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMMessage:
    role: str       # "system" | "user" | "assistant"
    content: str


class LLMProvider(ABC):
    """Minimal interface for text completion."""

    @abstractmethod
    def complete(
        self,
        messages: list[LLMMessage],
        *,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        response_format: str = "text",   # "text" | "json"
    ) -> str:
        """
        Send *messages* to the LLM and return the assistant reply as a string.
        Raises LLMError on failure.
        """

    def system_user(self, system: str, user: str, **kwargs) -> str:
        """Convenience wrapper for a two-message call."""
        msgs = [
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=user),
        ]
        return self.complete(msgs, **kwargs)


class LLMError(Exception):
    """Raised when LLM call fails."""