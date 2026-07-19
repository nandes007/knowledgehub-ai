import { describe, expect, it } from "vitest";
import { parseSseStream } from "./sse";

function streamResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return new Response(stream);
}

describe("parseSseStream", () => {
  it("yields events as complete blocks arrive, even when split across chunk boundaries", async () => {
    const chunks = [
      'event: token\ndata: {"text": "Hel',
      'lo "}\n\n',
      'event: token\ndata: {"text": "world"}\n\ne',
      'vent: done\ndata: {"sources": [], "message_id": "m1", "conversation_id": "c1"}\n\n',
    ];

    const events = [];
    for await (const event of parseSseStream(streamResponse(chunks))) {
      events.push(event);
    }

    expect(events).toEqual([
      { event: "token", data: '{"text": "Hello "}' },
      { event: "token", data: '{"text": "world"}' },
      { event: "done", data: '{"sources": [], "message_id": "m1", "conversation_id": "c1"}' },
    ]);
  });

  it("throws if the response has no readable body", async () => {
    const response = new Response(null);

    const drain = async () => {
      const results = [];
      for await (const event of parseSseStream(response)) results.push(event);
      return results;
    };

    await expect(drain()).rejects.toThrow();
  });
});
