import logging
from types import SimpleNamespace

import pytest

from app.config import settings
from app.services import llm as llm_module
from app.services.llm import OpenAIProvider, TokenUsage, get_llm_provider


class _FakeEmbeddingsAPI:
    def create(self, model: str, input: list[str]):
        return SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.1, 0.2]) for _ in input],
            usage=SimpleNamespace(prompt_tokens=7, total_tokens=7),
        )


def _fake_stream_chunk(content: str | None):
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=content))],
        usage=None,
    )


def _fake_usage_chunk(prompt_tokens: int, completion_tokens: int):
    return SimpleNamespace(
        choices=[],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


class _FakeChatCompletionsAPI:
    def create(self, model: str, messages: list[dict], stream: bool = False, stream_options=None):
        assert stream is True
        assert stream_options == {"include_usage": True}
        return iter(
            [
                _fake_stream_chunk("4"),
                _fake_stream_chunk("2"),
                _fake_stream_chunk(None),
                _fake_usage_chunk(prompt_tokens=15, completion_tokens=2),
            ]
        )


class _FakeOpenAIClient:
    def __init__(self) -> None:
        self.embeddings = _FakeEmbeddingsAPI()
        self.chat = SimpleNamespace(completions=_FakeChatCompletionsAPI())


def test_embed_texts_parses_openai_response():
    provider = OpenAIProvider(client=_FakeOpenAIClient())

    result = provider.embed_texts(["hello", "world"])

    assert result == [[0.1, 0.2], [0.1, 0.2]]


def test_generate_answer_stream_yields_token_deltas_and_skips_empty_chunks():
    provider = OpenAIProvider(client=_FakeOpenAIClient())

    tokens = list(provider.generate_answer_stream("What is the answer?"))

    assert tokens == ["4", "2"]


def test_generate_answer_stream_populates_usage_from_final_chunk():
    provider = OpenAIProvider(client=_FakeOpenAIClient())
    usage = TokenUsage()

    list(provider.generate_answer_stream("What is the answer?", usage=usage))

    assert usage.prompt_tokens == 15
    assert usage.completion_tokens == 2


def test_embed_texts_logs_model_and_token_usage(caplog):
    provider = OpenAIProvider(client=_FakeOpenAIClient())

    with caplog.at_level(logging.INFO, logger="app.llm"):
        provider.embed_texts(["hello"])

    record = next(r for r in caplog.records if r.name == "app.llm")
    assert record.call_type == "embedding"
    assert record.model == settings.embedding_model
    assert record.prompt_tokens == 7


def test_generate_answer_stream_logs_model_and_token_usage(caplog):
    provider = OpenAIProvider(client=_FakeOpenAIClient())

    with caplog.at_level(logging.INFO, logger="app.llm"):
        list(provider.generate_answer_stream("What is the answer?", usage=TokenUsage()))

    record = next(r for r in caplog.records if r.name == "app.llm")
    assert record.call_type == "chat"
    assert record.model == settings.chat_model
    assert record.prompt_tokens == 15
    assert record.completion_tokens == 2


def test_get_llm_provider_defaults_to_openai(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    provider = get_llm_provider()

    assert isinstance(provider, OpenAIProvider)


def test_get_llm_provider_rejects_unknown_provider(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "unknown-provider")

    with pytest.raises(ValueError, match="Unsupported LLM_PROVIDER"):
        llm_module.get_llm_provider()
