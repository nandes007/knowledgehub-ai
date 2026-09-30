from app.services.rag import stream_answer


class ChangingStore:
    def __init__(self):
        self.matches = []

    def query(self, embedding, *, top_k, where):
        return self.matches[:top_k]

    def keyword_query(self, question, *, top_k, where):
        return self.matches[:top_k]


class HistoryAnchoringLLM:
    def __init__(self):
        self.prompts = []

    def embed_texts(self, texts):
        return [[1.0] for _ in texts]

    def generate_answer_stream(self, prompt, *, usage=None):
        self.prompts.append(prompt)
        if "assistant: I don't have that in the knowledge base yet." in prompt:
            yield "I don't have that in the knowledge base yet."
        elif "Employees get 20 days of PTO per year." in prompt:
            yield "Employees get 20 days of PTO per year."
        else:
            yield "I don't have that in the knowledge base yet."


def test_new_knowledge_replaces_stale_refusal_in_same_conversation():
    store = ChangingStore()
    llm = HistoryAnchoringLLM()
    question = "How many vacation days do I get?"

    first_tokens, first_sources, _ = stream_answer(question, llm=llm, vector_store=store)
    first_answer = "".join(first_tokens)
    assert first_sources == []
    assert first_answer == "I don't have that in the knowledge base yet."

    store.matches = [{
        "id": "new-chunk",
        "text": "Employees get 20 days of PTO per year.",
        "document_id": "new-document",
        "filename": "policy.md",
    }]
    history = [
        {"role": "user", "content": question, "has_sources": False},
        {"role": "assistant", "content": first_answer, "has_sources": False},
    ]
    second_tokens, second_sources, _ = stream_answer(
        question, llm=llm, vector_store=store, history=history
    )

    assert second_sources[0]["filename"] == "policy.md"
    assert "".join(second_tokens) == "Employees get 20 days of PTO per year."
    assert f"assistant: {first_answer}" not in llm.prompts[-1]


def test_grounded_previous_answer_remains_available_for_follow_up():
    store = ChangingStore()
    store.matches = [{
        "id": "policy-chunk",
        "text": "Employees get 20 days of PTO per year.",
        "document_id": "policy",
        "filename": "policy.md",
    }]
    llm = HistoryAnchoringLLM()
    tokens, _, _ = stream_answer(
        "Does that include sick leave?",
        llm=llm,
        vector_store=store,
        history=[
            {"role": "user", "content": "How many vacation days?", "has_sources": False},
            {"role": "assistant", "content": "20 vacation days.", "has_sources": True},
        ],
    )

    list(tokens)
    assert "assistant: 20 vacation days." in llm.prompts[-1]
