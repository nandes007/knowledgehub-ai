"use client";

import { Markdown } from "./Markdown";
import { AuthImage } from "./AuthImage";
import { fetchProtectedFile, type Source } from "@/lib/api";

export type MessageAttachment = {
  filename: string;
  mime: string;
  truncated?: boolean;
  // API path for saved attachments; a local blob URL for one just sent.
  src: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
  status?: string;
  sources?: Source[];
  attachments?: MessageAttachment[];
};

function ThinkingDots() {
  return (
    <span className="inline-flex items-center gap-1.5 py-2" aria-label="Thinking">
      <span className="thinking-dot" />
      <span className="thinking-dot" />
      <span className="thinking-dot" />
    </span>
  );
}

async function openAttachment(attachment: MessageAttachment) {
  const url = attachment.src.startsWith("blob:") ? attachment.src : await fetchProtectedFile(attachment.src);
  const link = document.createElement("a");
  link.href = url;
  link.download = attachment.filename;
  link.click();
}

function Attachments({ attachments }: { attachments: MessageAttachment[] }) {
  return (
    <div className="mb-2 flex flex-wrap justify-end gap-2">
      {attachments.map((a, i) =>
        a.mime.startsWith("image/") ? (
          a.src.startsWith("blob:") ? (
            // eslint-disable-next-line @next/next/no-img-element -- local preview of a file being sent
            <img key={i} src={a.src} alt={a.filename} className="h-24 max-w-48 rounded-lg border border-border object-cover" />
          ) : (
            <AuthImage key={i} src={a.src} alt={a.filename} className="h-24 max-w-48 rounded-lg border border-border object-cover" />
          )
        ) : (
          <button
            key={i}
            type="button"
            onClick={() => openAttachment(a)}
            title={`Download ${a.filename}`}
            className="flex items-center gap-1.5 rounded-lg border border-border bg-surface-raised px-3 py-1.5 text-xs text-text-primary transition-colors duration-120 hover:border-gold/50"
          >
            <span aria-hidden>📄</span>
            <span className="max-w-48 truncate">{a.filename}</span>
            {a.truncated && <span className="text-text-tertiary">(partly read)</span>}
          </button>
        ),
      )}
    </div>
  );
}

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const isThinking = message.streaming && message.content === "";

  if (isUser) {
    return (
      <div className="flex flex-col items-end animate-fade-in">
        {message.attachments && message.attachments.length > 0 && <Attachments attachments={message.attachments} />}
        {message.content && (
          <div className="flex w-full justify-end">
            <div className="max-w-[80%] rounded-2xl rounded-br-md bg-user-bubble px-4 py-2.5 text-sm leading-relaxed text-text-primary">
              {message.content}
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      {isThinking ? (
        message.status ? (
          <p className="py-2 text-sm text-text-secondary" role="status">
            {message.status}
          </p>
        ) : (
          <ThinkingDots />
        )
      ) : (
        <Markdown>{message.content}</Markdown>
      )}
    </div>
  );
}
