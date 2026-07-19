import { parseSseStream } from "./sse";

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

export async function sendChatMessage(
  message: string,
  conversationId?: string,
  onToken?: (text: string) => void,
): Promise<ChatResult> {
  const response = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });

  if (!response.ok) {
    throw new Error(`Chat request failed: ${response.status}`);
  }

  let answer = "";
  for await (const { event, data } of parseSseStream(response)) {
    if (event === "token") {
      const text = (JSON.parse(data) as { text: string }).text;
      answer += text;
      onToken?.(text);
    } else if (event === "error") {
      throw new Error((JSON.parse(data) as { message: string }).message);
    } else if (event === "done") {
      const doneData = JSON.parse(data) as {
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
  }

  throw new Error("Chat stream ended without a done event");
}
