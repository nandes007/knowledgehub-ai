"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { sendChatMessage } from "@/lib/api";
import { MessageBubble, type ChatMessage } from "./MessageBubble";
import { useConversations } from "./ConversationsProvider";

type ChatPanelProps = {
  conversationId?: string;
  initialMessages?: ChatMessage[];
};

export function ChatPanel({ conversationId: initialConversationId, initialMessages = [] }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [draft, setDraft] = useState("");
  const [conversationId, setConversationId] = useState(initialConversationId);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollAnchorRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const { addOrRename } = useConversations();

  useEffect(() => {
    scrollAnchorRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const question = draft.trim();
    if (!question || isSending) return;

    const isNewConversation = !conversationId;
    setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: "user", content: question }]);
    setDraft("");
    setError(null);
    setIsSending(true);

    const assistantId = crypto.randomUUID();
    setMessages((prev) => [...prev, { id: assistantId, role: "assistant", content: "", streaming: true }]);

    try {
      const result = await sendChatMessage(question, conversationId, (text) => {
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? { ...m, content: m.content + text } : m)),
        );
      });
      setConversationId(result.conversationId);
      addOrRename(result.conversationId, question);
      if (isNewConversation) {
        router.replace(`/chat/${result.conversationId}`);
      }
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, id: result.messageId, content: result.answer, streaming: false } : m,
        ),
      );
    } catch (err) {
      setMessages((prev) => prev.filter((m) => m.id !== assistantId));
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setIsSending(false);
    }
  }

  return (
    <div className="flex flex-1 flex-col">
      <div className="flex-1 space-y-4 overflow-y-auto px-6 py-6">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
        <div ref={scrollAnchorRef} />
      </div>
      <form
        className="flex gap-2 border-t border-zinc-200 p-4 dark:border-zinc-800"
        onSubmit={handleSubmit}
      >
        <input
          type="text"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          disabled={isSending}
          placeholder="Ask something about your company's knowledge base..."
          className="flex-1 rounded-lg border border-zinc-300 px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-400 disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
        />
        <button
          type="submit"
          disabled={isSending}
          className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          {isSending ? "Sending..." : "Send"}
        </button>
      </form>
    </div>
  );
}
