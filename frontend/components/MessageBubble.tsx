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

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const isThinking = message.streaming && message.content === "";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[75%] rounded-sm px-4 py-2 text-sm leading-relaxed ${
          isUser
            ? "bg-ledger text-ledger-ink"
            : "border border-rule bg-paper-raised text-ink shadow-[0_2px_8px_-2px_rgba(36,31,26,0.12)]"
        }`}
      >
        {isThinking ? (
          <span className="italic text-ink-muted">Thinking...</span>
        ) : isUser ? (
          message.content
        ) : (
          <>
            <div className="[&_p]:my-1 [&_p:first-child]:mt-0 [&_p:last-child]:mb-0 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_code]:rounded-[2px] [&_code]:bg-ink/10 [&_code]:px-1 [&_code]:py-0.5 [&_code]:font-mono">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>
            {!message.streaming && message.sources && <SourceList sources={message.sources} />}
          </>
        )}
      </div>
    </div>
  );
}
