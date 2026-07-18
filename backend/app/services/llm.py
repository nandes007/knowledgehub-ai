from abc import ABC, abstractmethod
from typing import Any, Protocol

from openai import OpenAI

from app.config import settings


class LLMProvider(ABC):
    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    def generate_answer(self, prompt: str) -> str: ...


class _OpenAIClientLike(Protocol):
    embeddings: Any
    chat: Any


class OpenAIProvider(LLMProvider):
    def __init__(self, client: _OpenAIClientLike | None = None) -> None:
        self._client = client or OpenAI(api_key=settings.openai_api_key)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(model=settings.embedding_model, input=texts)
        return [item.embedding for item in response.data]

    def generate_answer(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=settings.chat_model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""


def get_llm_provider() -> LLMProvider:
    if settings.llm_provider == "openai":
        return OpenAIProvider()
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")
