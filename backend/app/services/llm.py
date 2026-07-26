import logging
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Protocol

from openai import OpenAI

from app.config import settings

_logger = logging.getLogger("app.llm")


@dataclass
class TokenUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


def _log_llm_call(
    *, call_type: str, model: str, prompt_tokens: int | None, completion_tokens: int | None
) -> None:
    _logger.info(
        "llm_call",
        extra={
            "call_type": call_type,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        },
    )


class LLMProvider(ABC):
    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    def generate_answer_stream(self, prompt: str, *, usage: TokenUsage | None = None) -> Iterator[str]: ...


class _OpenAIClientLike(Protocol):
    embeddings: Any
    chat: Any


class OpenAIProvider(LLMProvider):
    def __init__(self, client: _OpenAIClientLike | None = None) -> None:
        self._client = client or OpenAI(api_key=settings.openai_api_key)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(model=settings.embedding_model, input=texts)
        _log_llm_call(
            call_type="embedding",
            model=settings.embedding_model,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=None,
        )
        return [item.embedding for item in response.data]

    def generate_answer_stream(self, prompt: str, *, usage: TokenUsage | None = None) -> Iterator[str]:
        stream = self._client.chat.completions.create(
            model=settings.chat_model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            stream_options={"include_usage": True},
        )
        for chunk in stream:
            if chunk.usage is not None and usage is not None:
                usage.prompt_tokens = chunk.usage.prompt_tokens
                usage.completion_tokens = chunk.usage.completion_tokens
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
        _log_llm_call(
            call_type="chat",
            model=settings.chat_model,
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
        )


def get_llm_provider() -> LLMProvider:
    if settings.llm_provider == "openai":
        return OpenAIProvider()
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")
