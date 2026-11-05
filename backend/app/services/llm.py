import base64
import logging
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Protocol

from openai import OpenAI

from app.config import settings

_logger = logging.getLogger("app.llm")

_OCR_PROMPT = (
    "Transcribe this document page image as GitHub-flavored markdown, top to bottom.\n"
    "- Copy all text as written, including text inside screenshots and diagrams. "
    "Do not summarize, translate, or add commentary.\n"
    "- Keep headings, lists and tables as markdown structure. Put code in fenced code blocks "
    "with the language, if known.\n"
    "- Where a diagram, chart, photo or UI screenshot shows something the text alone does not "
    "(flows, connections, trends, layout), add a short description in place, on its own line, "
    "starting with \"_Image:_\". Skip logos, icons and decoration.\n"
    "- If the page is blank, reply with nothing."
)


# OpenAI chat-completions shape: content is a string, or a list of
# {"type": "text", "text": ...} / {"type": "image_url", "image_url": {"url": ...}} parts.
ChatMessage = dict[str, Any]


def message_text(messages: list[ChatMessage]) -> str:
    """All text parts of a message list joined - for logs and test fakes."""
    parts: list[str] = []
    for message in messages:
        content = message["content"]
        if isinstance(content, str):
            parts.append(content)
        else:
            parts.extend(p["text"] for p in content if p.get("type") == "text")
    return "\n".join(parts)


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
    def generate_answer_stream(
        self, messages: list[ChatMessage], *, usage: TokenUsage | None = None
    ) -> Iterator[str]: ...

    @abstractmethod
    def transcribe_image(self, png: bytes) -> str: ...


class _OpenAIClientLike(Protocol):
    embeddings: Any
    chat: Any


class OpenAIProvider(LLMProvider):
    def __init__(
        self, client: _OpenAIClientLike | None = None, vision_client: _OpenAIClientLike | None = None
    ) -> None:
        self._client = client or OpenAI(api_key=settings.openai_api_key)
        # OCR may run on any OpenAI-compatible endpoint (e.g. OpenRouter); it only produces text,
        # so it is independent of the embedding model that the index depends on.
        self._vision_client = vision_client or (
            OpenAI(base_url=settings.vision_base_url, api_key=settings.vision_api_key)
            if settings.vision_base_url
            else self._client
        )

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(model=settings.embedding_model, input=texts)
        _log_llm_call(
            call_type="embedding",
            model=settings.embedding_model,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=None,
        )
        return [item.embedding for item in response.data]

    def generate_answer_stream(
        self, messages: list[ChatMessage], *, usage: TokenUsage | None = None
    ) -> Iterator[str]:
        stream = self._client.chat.completions.create(
            model=settings.chat_model,
            messages=messages,
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

    def transcribe_image(self, png: bytes) -> str:
        url = f"data:image/png;base64,{base64.b64encode(png).decode()}"
        response = self._vision_client.chat.completions.create(
            model=settings.vision_model,
            temperature=0,
            messages=[
                {"role": "system", "content": _OCR_PROMPT},
                {"role": "user", "content": [{"type": "image_url", "image_url": {"url": url, "detail": "high"}}]},
            ],
        )
        _log_llm_call(
            call_type="ocr",
            model=settings.vision_model,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
        )
        return response.choices[0].message.content or ""


def get_llm_provider() -> LLMProvider:
    if settings.llm_provider == "openai":
        return OpenAIProvider()
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")
