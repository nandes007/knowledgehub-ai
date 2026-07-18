from types import SimpleNamespace

import pytest

from app.config import settings
from app.services import llm as llm_module
from app.services.llm import OpenAIProvider, get_llm_provider


class _FakeEmbeddingsAPI:
    def create(self, model: str, input: list[str]):
        return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2]) for _ in input])


class _FakeChatCompletionsAPI:
    def create(self, model: str, messages: list[dict]):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="42"))])


class _FakeOpenAIClient:
    def __init__(self) -> None:
        self.embeddings = _FakeEmbeddingsAPI()
        self.chat = SimpleNamespace(completions=_FakeChatCompletionsAPI())


def test_embed_texts_parses_openai_response():
    provider = OpenAIProvider(client=_FakeOpenAIClient())

    result = provider.embed_texts(["hello", "world"])

    assert result == [[0.1, 0.2], [0.1, 0.2]]


def test_generate_answer_parses_openai_response():
    provider = OpenAIProvider(client=_FakeOpenAIClient())

    assert provider.generate_answer("What is the answer?") == "42"


def test_get_llm_provider_defaults_to_openai(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    provider = get_llm_provider()

    assert isinstance(provider, OpenAIProvider)


def test_get_llm_provider_rejects_unknown_provider(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "unknown-provider")

    with pytest.raises(ValueError, match="Unsupported LLM_PROVIDER"):
        llm_module.get_llm_provider()
