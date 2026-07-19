import { afterEach, describe, expect, it, vi } from "vitest";
import { sendChatMessage } from "./api";

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
});
