"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { sendChatMessage } from "../lib/api";
import { addAttachments, ATTACHMENT_ACCEPT, imagesFromClipboard, isImageFile } from "../lib/attachments";
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
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const scrollAnchorRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();
  const { addOrRename, setActiveId, registerFocusHandler } = useConversations();

  // Focus textarea on initial load and when conversation changes
  useEffect(() => {
    textareaRef.current?.focus();
  }, [conversationId]);

  // Register focus trigger (e.g. when "New chat" is clicked in sidebar)
  useEffect(() => {
    return registerFocusHandler?.(() => {
      textareaRef.current?.focus();
    });
  }, [registerFocusHandler]);

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

  function attach(incoming: File[]) {
    if (incoming.length === 0) return;
    setPendingFiles((prev) => {
      const { files, error: attachError } = addAttachments(prev, incoming);
      setError(attachError);
      return files;
    });
  }

  function handlePaste(event: React.ClipboardEvent<HTMLTextAreaElement>) {
    const images = imagesFromClipboard(event.clipboardData.items);
    if (images.length > 0) {
      event.preventDefault(); // pasted text still pastes as text
      attach(images);
    }
  }

  function handleDrop(event: React.DragEvent) {
    event.preventDefault();
    setIsDragging(false);
    attach(Array.from(event.dataTransfer.files));
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const question = draft.trim();
    const files = pendingFiles;
    if ((!question && files.length === 0) || isSending) return;

    const isNewConversation = !conversationId;
    setMessages((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        role: "user",
        content: question,
        // ponytail: preview blob URLs live until the page unloads; revoke them if long
        // attachment-heavy sessions show memory growth.
        attachments: files.map((f) => ({
          filename: f.name,
          mime: isImageFile(f.name) ? f.type || "image/png" : f.type || "application/octet-stream",
          src: URL.createObjectURL(f),
        })),
      },
    ]);
    setDraft("");
    setPendingFiles([]);
    setError(null);
    setIsSending(true);

    const assistantId = crypto.randomUUID();
    setMessages((prev) => [...prev, { id: assistantId, role: "assistant", content: "", streaming: true }]);

    try {
      const result = await sendChatMessage(
        question,
        conversationId,
        (text) => {
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, content: m.content + text } : m)),
          );
        },
        files,
        (status) => {
          setMessages((prev) => prev.map((m) => (m.id === assistantId ? { ...m, status } : m)));
        },
      );
      setConversationId(result.conversationId);
      addOrRename(result.conversationId, question || files[0]?.name || "New chat");
      setActiveId?.(result.conversationId);
      if (isNewConversation && typeof window !== "undefined") {
        window.history.replaceState(null, "", `/chat/${result.conversationId}`);
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
    <div
      className="relative flex min-w-0 flex-1 flex-col"
      onDragOver={(event) => {
        if (!event.dataTransfer.types.includes("Files")) return;
        event.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setIsDragging(false);
      }}
      onDrop={handleDrop}
    >
      {isDragging && (
        <div className="pointer-events-none absolute inset-2 z-10 flex items-center justify-center rounded-2xl border-2 border-dashed border-gold/60 bg-surface-primary/80 text-sm text-text-secondary">
          Drop files to attach
        </div>
      )}
      {/* Message area */}
      <div className="flex-1 overflow-y-auto px-4 pb-6 pt-16 md:px-6 md:pt-6">
        <div className="mx-auto max-w-3xl space-y-6">
          {messages.length === 0 && (
            <div className="flex h-[60vh] flex-col items-center justify-center text-center">
              <Wordmark className="text-2xl" />
              <p className="mt-3 max-w-sm text-sm text-text-secondary">
                Ask anything about your company&rsquo;s knowledge base.
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
      <div className="px-4 pb-4 md:px-6 md:pb-6">
        <form
          className="mx-auto flex max-w-3xl flex-wrap items-end gap-2 rounded-2xl border border-border bg-surface-raised p-2 shadow-[0_4px_20px_-4px_rgba(0,0,0,0.5)] transition-colors duration-120 focus-within:border-gold/50 focus-within:ring-1 focus-within:ring-gold/30"
          onSubmit={handleSubmit}
        >
          {pendingFiles.length > 0 && (
            <ul className="flex w-full flex-wrap gap-2 px-1 pt-1" aria-label="Attachments to send">
              {pendingFiles.map((file, index) => (
                <li
                  key={`${file.name}-${index}`}
                  className="flex items-center gap-1.5 rounded-lg border border-border bg-surface-primary px-2.5 py-1 text-xs text-text-primary"
                >
                  <span className="max-w-40 truncate">{file.name}</span>
                  <button
                    type="button"
                    onClick={() => setPendingFiles((prev) => prev.filter((_, i) => i !== index))}
                    aria-label={`Remove ${file.name}`}
                    className="text-text-tertiary hover:text-text-primary"
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
          <input
            ref={fileInputRef}
            id="chat-attachments"
            type="file"
            multiple
            accept={ATTACHMENT_ACCEPT}
            className="sr-only"
            onChange={(event) => {
              attach(Array.from(event.target.files ?? []));
              event.target.value = ""; // allow picking the same file again
            }}
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isSending}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-text-secondary transition-colors duration-120 hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold disabled:opacity-40"
            aria-label="Attach files"
            title="Attach files"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M13.5 7.5l-5.6 5.6a3.5 3.5 0 01-5-5l6-6a2.3 2.3 0 013.3 3.3l-6 6a1.2 1.2 0 01-1.7-1.7l5.5-5.5" />
            </svg>
          </button>
          <textarea
            ref={textareaRef}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleKeyDown}
            onPaste={handlePaste}
            disabled={isSending}
            autoFocus
            placeholder="Ask anything about your company's knowledge base..."
            rows={1}
            className="flex-1 resize-none bg-transparent px-3 py-1.5 text-base text-text-primary md:text-sm placeholder:text-text-tertiary focus:outline-none disabled:opacity-50"
            style={{ maxHeight: `${24 * 5}px` }}
          />
          <button
            type="submit"
            disabled={isSending || (!draft.trim() && pendingFiles.length === 0)}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gold text-surface-primary transition-colors duration-120 hover:bg-gold-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-2 focus-visible:ring-offset-surface-raised disabled:opacity-40"
            aria-label="Send message"
            title="Send message"
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 16 16"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M8 12V4M4 8l4-4 4 4" />
            </svg>
          </button>
        </form>
      </div>
    </div>
  );
}
