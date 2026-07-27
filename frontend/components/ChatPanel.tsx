"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { sendChatMessage } from "@/lib/api";
import { MessageBubble, type ChatMessage } from "./MessageBubble";
import { useConversations } from "./ConversationsProvider";
import { Button, Input } from "./ui";

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
          m.id === assistantId
            ? { ...m, id: result.messageId, content: result.answer, sources: result.sources, streaming: false }
            : m,
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
    <div className="flex min-w-0 flex-1 flex-col">
      <div className="flex-1 space-y-4 overflow-y-auto px-4 pb-6 pt-16 md:px-6 md:pt-6">
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center text-center text-sm text-ink-muted">
            <p className="font-serif text-base text-ink">The vault is open.</p>
            <p className="mt-1 max-w-xs">Ask a question about your company&rsquo;s documents to open a new ledger entry.</p>
          </div>
        )}
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        {error && <p className="text-sm text-stamp-void">{error}</p>}
        <div ref={scrollAnchorRef} />
      </div>
      <form className="flex gap-2 border-t border-rule bg-paper-raised p-4" onSubmit={handleSubmit}>
        <Input
          type="text"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          disabled={isSending}
          placeholder="Ask something about your company's knowledge base..."
          className="rounded-t-sm"
        />
        <Button type="submit" disabled={isSending}>
          {isSending ? "Sending..." : "Send"}
        </Button>
      </form>
    </div>
  );
}
