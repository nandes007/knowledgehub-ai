from fastapi import APIRouter, Depends

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.llm import LLMProvider, get_llm_provider
from app.services.rag import answer_question
from ingestion.index import VectorStore, get_vector_store

router = APIRouter()

# Task 16 adds real auth; every request is scoped to this seed user until then.
_HARDCODED_USER_ID = "seed-user"


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    llm: LLMProvider = Depends(get_llm_provider),
    vector_store: VectorStore = Depends(get_vector_store),
) -> ChatResponse:
    answer, sources = answer_question(
        request.message,
        user_id=_HARDCODED_USER_ID,
        llm=llm,
        vector_store=vector_store,
    )
    return ChatResponse(answer=answer, sources=sources)
