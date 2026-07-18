import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatRequest
from app.services.llm import LLMProvider, get_llm_provider
from app.services.rag import stream_answer
from ingestion.index import VectorStore, get_vector_store

router = APIRouter()

# Task 16 adds real auth; every request is scoped to this seed user until then.
_HARDCODED_USER_ID = "seed-user"


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _event_stream(tokens: Iterator[str], sources: list[dict]) -> Iterator[str]:
    try:
        for token in tokens:
            yield _sse("token", {"text": token})
    except Exception as exc:
        # Last-resort boundary: headers are already sent, so a mid-stream LLM
        # failure has to surface as an SSE event rather than an HTTP error.
        yield _sse("error", {"message": str(exc)})
        return
    yield _sse("done", {"sources": sources})


@router.post("/chat")
def chat(
    request: ChatRequest,
    llm: LLMProvider = Depends(get_llm_provider),
    vector_store: VectorStore = Depends(get_vector_store),
) -> StreamingResponse:
    tokens, sources = stream_answer(
        request.message,
        user_id=_HARDCODED_USER_ID,
        llm=llm,
        vector_store=vector_store,
    )
    return StreamingResponse(_event_stream(tokens, sources), media_type="text/event-stream")
