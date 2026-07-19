import { parseSseStream } from "./sse";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// fetch() rejects (rather than resolving with a bad status) when the server is
// unreachable, e.g. it's down or the network drops. That raw rejection reads as a
// blank/broken UI, so surface it as a message a user can act on.
async function apiFetch(input: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(input, init);
  } catch {
    throw new Error("Couldn't reach the server. Check your connection and try again.");
  }
}

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
  const response = await apiFetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });

  if (!response.ok) {
    throw new Error(`Chat request failed: ${response.status}`);
  }

  let answer = "";
  try {
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
  } catch (err) {
    // A dropped connection mid-stream surfaces as a TypeError from the reader, distinct
    // from the `error` SSE event above (a plain Error we threw ourselves with a message
    // already meant for display).
    if (err instanceof TypeError) {
      throw new Error("Couldn't reach the server. Check your connection and try again.");
    }
    throw err;
  }

  throw new Error("Chat stream ended without a done event");
}

export type Conversation = {
  id: string;
  title: string;
};

export async function listConversations(): Promise<Conversation[]> {
  const response = await apiFetch(`${API_URL}/conversations`);
  if (!response.ok) {
    throw new Error(`Failed to load conversations: ${response.status}`);
  }
  const data = (await response.json()) as { id: string; title: string }[];
  return data.map(({ id, title }) => ({ id, title }));
}

export async function createConversation(): Promise<Conversation> {
  const response = await apiFetch(`${API_URL}/conversations`, { method: "POST" });
  if (!response.ok) {
    throw new Error(`Failed to create conversation: ${response.status}`);
  }
  const { id, title } = (await response.json()) as { id: string; title: string };
  return { id, title };
}

export type ConversationMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: Source[];
};

export async function getConversationMessages(conversationId: string): Promise<ConversationMessage[]> {
  const response = await apiFetch(`${API_URL}/conversations/${conversationId}/messages`);
  if (!response.ok) {
    throw new Error(`Failed to load conversation messages: ${response.status}`);
  }
  const data = (await response.json()) as {
    id: string;
    role: "user" | "assistant";
    content: string;
    sources: Source[] | null;
  }[];
  return data.map(({ id, role, content, sources }) => ({ id, role, content, sources: sources ?? [] }));
}
