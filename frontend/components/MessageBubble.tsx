import ReactMarkdown from "react-markdown";
import { SourceList } from "./SourceList";
import type { Source } from "@/lib/api";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
  sources?: Source[];
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

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const isThinking = message.streaming && message.content === "";

  if (isUser) {
    return (
      <div className="flex justify-end animate-fade-in">
        <div className="max-w-[80%] rounded-2xl rounded-br-md bg-user-bubble px-4 py-2.5 text-sm leading-relaxed text-text-primary">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      {isThinking ? (
        <ThinkingDots />
      ) : (
        <>
          <div className="prose-dark text-sm leading-relaxed text-text-primary [&_p]:my-2 [&_p:first-child]:mt-0 [&_p:last-child]:mb-0 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_code]:rounded-md [&_code]:bg-border [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-gold [&_pre]:rounded-lg [&_pre]:bg-surface-raised [&_pre]:p-3 [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_a]:text-gold [&_a]:underline [&_strong]:text-text-primary [&_h1]:mt-4 [&_h1]:mb-2 [&_h1]:text-lg [&_h1]:font-semibold [&_h2]:mt-3 [&_h2]:mb-1.5 [&_h2]:text-base [&_h2]:font-semibold [&_h3]:mt-2 [&_h3]:mb-1 [&_h3]:text-sm [&_h3]:font-semibold [&_blockquote]:border-l-2 [&_blockquote]:border-gold/30 [&_blockquote]:pl-3 [&_blockquote]:text-text-secondary">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
          {!message.streaming && message.sources && <SourceList sources={message.sources} />}
        </>
      )}
    </div>
  );
}
