"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { sendChatMessage } from "@/lib/api";
import { MessageBubble, type ChatMessage } from "./MessageBubble";
import { useConversations } from "./ConversationsProvider";
import { Wordmark } from "./ui";

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
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const router = useRouter();
  const { addOrRename } = useConversations();

  useEffect(() => {
    scrollAnchorRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  // Auto-resize textarea based on content, clamped to 5 rows
  const resizeTextarea = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    const lineHeight = 24; // ~1.5rem
    const maxHeight = lineHeight * 5;
    textarea.style.height = `${Math.min(textarea.scrollHeight, maxHeight)}px`;
  }, []);

  useEffect(() => {
    resizeTextarea();
  }, [draft, resizeTextarea]);

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

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSubmit(event);
    }
  }

  return (
    <div className="flex min-w-0 flex-1 flex-col">
      {/* Message area */}
      <div className="flex-1 overflow-y-auto px-4 pb-6 pt-16 md:px-6 md:pt-6">
        <div className="mx-auto max-w-3xl space-y-5">
          {messages.length === 0 && (
            <div className="flex h-[60vh] flex-col items-center justify-center text-center">
              <Wordmark className="text-2xl" />
              <p className="mt-3 max-w-sm text-sm text-text-secondary">
                Ask a question about your company&rsquo;s knowledge base to get started.
              </p>
            </div>
          )}
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
          {error && <p className="text-sm text-status-void">{error}</p>}
          <div ref={scrollAnchorRef} />
        </div>
      </div>

      {/* Floating input area */}
      <div className="border-t border-border bg-surface-primary/80 px-4 py-3 backdrop-blur-sm">
        <form
          className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-border bg-surface-raised p-2 shadow-[0_2px_16px_-4px_rgba(0,0,0,0.4)] transition-colors duration-120 focus-within:border-accent/50"
          onSubmit={handleSubmit}
        >
          <textarea
            ref={textareaRef}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isSending}
            placeholder="Ask something about your company's knowledge base..."
            rows={1}
            className="flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-text-primary placeholder:text-text-tertiary focus:outline-none disabled:opacity-50"
            style={{ maxHeight: `${24 * 5}px` }}
          />
          <button
            type="submit"
            disabled={isSending || !draft.trim()}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent text-surface-primary transition-colors duration-120 hover:bg-accent-hover disabled:opacity-40"
            aria-label="Send message"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <path d="M1.724 1.053a.5.5 0 0 1 .54-.067l12 6a.5.5 0 0 1 0 .894l-12 6A.5.5 0 0 1 1.5 13.5V9.236a.5.5 0 0 1 .447-.497L8.5 8 1.947 7.261A.5.5 0 0 1 1.5 6.764V2.5a.5.5 0 0 1 .224-.447Z" />
            </svg>
          </button>
        </form>
      </div>
    </div>
  );
}
