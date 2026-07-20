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
        className={`max-w-[75%] rounded-2xl px-4 py-2 text-sm leading-relaxed ${
          isUser
            ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
            : "bg-zinc-100 text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100"
        }`}
      >
        {isThinking ? (
          <span className="italic text-zinc-500 dark:text-zinc-400">Thinking...</span>
        ) : isUser ? (
          message.content
        ) : (
          <>
            <div className="[&_p]:my-1 [&_p:first-child]:mt-0 [&_p:last-child]:mb-0 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_code]:rounded [&_code]:bg-black/10 [&_code]:px-1 [&_code]:py-0.5 dark:[&_code]:bg-white/10">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>
            {!message.streaming && message.sources && <SourceList sources={message.sources} />}
          </>
        )}
      </div>
    </div>
  );
}
