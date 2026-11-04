import { Markdown } from "./Markdown";
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
          <Markdown>{message.content}</Markdown>
        </>
      )}
    </div>
  );
}
