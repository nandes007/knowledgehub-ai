import { afterEach, describe, expect, it, vi } from "vitest";
import {
  createConversation,
  deleteDocument,
  getConversationMessages,
  listConversations,
  listDocuments,
  sendChatMessage,
  uploadDocument,
} from "./api";

function sseResponse(body: string, init?: ResponseInit): Response {
  return new Response(body, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
    ...init,
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("sendChatMessage", () => {
  it("concatenates token events and returns the done event's sources", async () => {
    const body =
      'event: token\ndata: {"text": "Employees "}\n\n' +
      'event: token\ndata: {"text": "get 20 days."}\n\n' +
      'event: done\ndata: {"sources": [{"document_id": "doc-1", "filename": "policy.md", "chunk_preview": "..."}], "message_id": "m1", "conversation_id": "c1"}\n\n';
    const fetchMock = vi.fn().mockResolvedValue(sseResponse(body));
    vi.stubGlobal("fetch", fetchMock);

    const result = await sendChatMessage("How many vacation days?");

    expect(result.answer).toBe("Employees get 20 days.");
    expect(result.sources).toEqual([
      { document_id: "doc-1", filename: "policy.md", chunk_preview: "..." },
    ]);
    expect(result.conversationId).toBe("c1");
    expect(result.messageId).toBe("m1");
  });

  it("sends the message and optional conversationId as the POST body", async () => {
    const body = 'event: done\ndata: {"sources": [], "message_id": "m1", "conversation_id": "c1"}\n\n';
    const fetchMock = vi.fn().mockResolvedValue(sseResponse(body));
    vi.stubGlobal("fetch", fetchMock);

    await sendChatMessage("hello", "existing-conversation");

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/chat");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body)).toEqual({
      message: "hello",
      conversation_id: "existing-conversation",
    });
  });

  it("throws with the error event's message on a mid-stream failure", async () => {
    const body = 'event: token\ndata: {"text": "Emplo"}\n\nevent: error\ndata: {"message": "upstream LLM timed out"}\n\n';
    const fetchMock = vi.fn().mockResolvedValue(sseResponse(body));
    vi.stubGlobal("fetch", fetchMock);

    await expect(sendChatMessage("hi")).rejects.toThrow("upstream LLM timed out");
  });

  it("throws when the HTTP request itself fails", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("Not Found", { status: 404 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(sendChatMessage("hi")).rejects.toThrow("404");
  });

  it("throws a friendly error when the server is unreachable", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(sendChatMessage("hi")).rejects.toThrow(
      "Couldn't reach the server. Check your connection and try again.",
    );
  });

  it("invokes onToken for each token event as it streams in, before done resolves", async () => {
    const body =
      'event: token\ndata: {"text": "Employees "}\n\n' +
      'event: token\ndata: {"text": "get 20 days."}\n\n' +
      'event: done\ndata: {"sources": [], "message_id": "m1", "conversation_id": "c1"}\n\n';
    const fetchMock = vi.fn().mockResolvedValue(sseResponse(body));
    vi.stubGlobal("fetch", fetchMock);

    const chunks: string[] = [];
    const result = await sendChatMessage("How many vacation days?", undefined, (text) => chunks.push(text));

    expect(chunks).toEqual(["Employees ", "get 20 days."]);
    expect(result.answer).toBe("Employees get 20 days.");
  });

  it("throws a friendly error if the connection drops mid-stream", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('event: token\ndata: {"text": "Hel"}\n\n'));
      },
      pull() {
        return Promise.reject(new TypeError("network error"));
      },
    });
    const fetchMock = vi.fn().mockResolvedValue(new Response(stream));
    vi.stubGlobal("fetch", fetchMock);

    await expect(sendChatMessage("hi")).rejects.toThrow(
      "Couldn't reach the server. Check your connection and try again.",
    );
  });
});

describe("listConversations", () => {
  it("returns the parsed conversation list from GET /conversations", async () => {
    const body = [
      { id: "c1", title: "Vacation policy", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-02T00:00:00Z" },
      { id: "c2", title: "New chat", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
    ];
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await listConversations();

    expect(result).toEqual([
      { id: "c1", title: "Vacation policy" },
      { id: "c2", title: "New chat" },
    ]);
    expect(fetchMock.mock.calls[0][0]).toContain("/conversations");
  });

  it("throws when the request fails", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("error", { status: 500 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listConversations()).rejects.toThrow("500");
  });

  it("throws a friendly error when the server is unreachable", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listConversations()).rejects.toThrow(
      "Couldn't reach the server. Check your connection and try again.",
    );
  });
});

describe("createConversation", () => {
  it("POSTs to /conversations and returns the created conversation", async () => {
    const body = { id: "c3", title: "New chat", created_at: "2026-01-03T00:00:00Z", updated_at: "2026-01-03T00:00:00Z" };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await createConversation();

    expect(result).toEqual({ id: "c3", title: "New chat" });
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/conversations");
    expect(options.method).toBe("POST");
  });
});

describe("getConversationMessages", () => {
  it("returns the parsed message history from GET /conversations/{id}/messages", async () => {
    const body = [
      { id: "m1", role: "user", content: "What is the vacation policy?", sources: null, created_at: "2026-01-01T00:00:00Z" },
      {
        id: "m2",
        role: "assistant",
        content: "20 days per year.",
        sources: [{ document_id: "doc-1", filename: "policy.md", chunk_preview: "..." }],
        created_at: "2026-01-01T00:00:01Z",
      },
    ];
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await getConversationMessages("c1");

    expect(result).toEqual([
      { id: "m1", role: "user", content: "What is the vacation policy?", sources: [] },
      {
        id: "m2",
        role: "assistant",
        content: "20 days per year.",
        sources: [{ document_id: "doc-1", filename: "policy.md", chunk_preview: "..." }],
      },
    ]);
    expect(fetchMock.mock.calls[0][0]).toContain("/conversations/c1/messages");
  });

  it("throws a 404 when the conversation doesn't exist", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("not found", { status: 404 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getConversationMessages("missing")).rejects.toThrow("404");
  });
});

describe("listDocuments", () => {
  it("returns the parsed document list from GET /documents", async () => {
    const body = [
      {
        id: "d1",
        filename: "policy.md",
        status: "ready",
        chunk_count: 3,
        error_message: null,
        created_at: "2026-01-01T00:00:00Z",
      },
      {
        id: "d2",
        filename: "handbook.pdf",
        status: "failed",
        chunk_count: null,
        error_message: "unsupported format",
        created_at: "2026-01-02T00:00:00Z",
      },
    ];
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await listDocuments();

    expect(result).toEqual([
      {
        id: "d1",
        filename: "policy.md",
        status: "ready",
        chunkCount: 3,
        errorMessage: null,
        createdAt: "2026-01-01T00:00:00Z",
      },
      {
        id: "d2",
        filename: "handbook.pdf",
        status: "failed",
        chunkCount: null,
        errorMessage: "unsupported format",
        createdAt: "2026-01-02T00:00:00Z",
      },
    ]);
    expect(fetchMock.mock.calls[0][0]).toContain("/documents");
  });

  it("throws a friendly error when the server is unreachable", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listDocuments()).rejects.toThrow(
      "Couldn't reach the server. Check your connection and try again.",
    );
  });
});

describe("uploadDocument", () => {
  it("POSTs the file as multipart form data and returns the created document", async () => {
    const body = { id: "d3", filename: "handbook.pdf", status: "processing" };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 202 }));
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["contents"], "handbook.pdf", { type: "application/pdf" });

    const result = await uploadDocument(file);

    expect(result).toEqual({ id: "d3", filename: "handbook.pdf", status: "processing" });
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/documents");
    expect(options.method).toBe("POST");
    expect(options.body).toBeInstanceOf(FormData);
    expect((options.body as FormData).get("file")).toBe(file);
  });

  it("throws when the upload is rejected", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("too big", { status: 413 }));
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["contents"], "big.pdf", { type: "application/pdf" });

    await expect(uploadDocument(file)).rejects.toThrow("413");
  });
});

describe("deleteDocument", () => {
  it("DELETEs /documents/{id}", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await deleteDocument("d1");

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/documents/d1");
    expect(options.method).toBe("DELETE");
  });

  it("throws a 404 when the document doesn't exist", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("not found", { status: 404 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(deleteDocument("missing")).rejects.toThrow("404");
  });
});
