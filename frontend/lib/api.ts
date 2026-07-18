const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Source = {
  document_id: string;
  filename: string;
  chunk_preview: string;
};

export type ChatResult = {
  answer: string;
  sources: Source[];
  conversationId: string;
  messageId: string;
};

type SseEvent = { event: string; data: string };

function parseSseEvents(raw: string): SseEvent[] {
  return raw
    .trim()
    .split("\n\n")
    .filter(Boolean)
    .map((block) => {
      const lines = block.split("\n");
      const eventLine = lines.find((line) => line.startsWith("event: "));
      const dataLine = lines.find((line) => line.startsWith("data: "));
      return {
        event: eventLine?.slice("event: ".length) ?? "",
        data: dataLine?.slice("data: ".length) ?? "",
      };
    });
}

// Task 08 replaces this with progressive reading via a ReadableStream
// reader; for now the fetch buffers the whole SSE body and we parse it
// once it's complete, rendering the final answer in one shot.
export async function sendChatMessage(
  message: string,
  conversationId?: string,
): Promise<ChatResult> {
  const response = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });

  if (!response.ok) {
    throw new Error(`Chat request failed: ${response.status}`);
  }

  const events = parseSseEvents(await response.text());

  let answer = "";
  for (const { event, data } of events) {
    if (event === "token") {
      answer += (JSON.parse(data) as { text: string }).text;
    } else if (event === "error") {
      throw new Error((JSON.parse(data) as { message: string }).message);
    }
  }

  const doneEvent = events.find((e) => e.event === "done");
  if (!doneEvent) {
    throw new Error("Chat stream ended without a done event");
  }
  const doneData = JSON.parse(doneEvent.data) as {
    sources: Source[];
    message_id: string;
    conversation_id: string;
  };

  return {
    answer,
    sources: doneData.sources,
    conversationId: doneData.conversation_id,
    messageId: doneData.message_id,
  };
}
