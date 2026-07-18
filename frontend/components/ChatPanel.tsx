"use client";

import { useState } from "react";
import { MessageBubble, type ChatMessage } from "./MessageBubble";

// Task 07 replaces this with real messages sent to/received from POST /chat.
const DUMMY_MESSAGES: ChatMessage[] = [
  { id: "1", role: "user", content: "How many vacation days do I get per year?" },
  {
    id: "2",
    role: "assistant",
    content:
      "Employees get 20 days of PTO per year, accrued monthly. You can find the full policy in the Vacation Policy document.",
  },
  { id: "3", role: "user", content: "Does that include public holidays?" },
  {
    id: "4",
    role: "assistant",
    content: "No, public holidays are separate and don't count against your 20 PTO days.",
  },
];

export function ChatPanel() {
  const [draft, setDraft] = useState("");

  return (
    <div className="flex flex-1 flex-col">
      <div className="flex-1 space-y-4 overflow-y-auto px-6 py-6">
        {DUMMY_MESSAGES.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
      </div>
      <form
        className="flex gap-2 border-t border-zinc-200 p-4 dark:border-zinc-800"
        onSubmit={(event) => event.preventDefault()}
      >
        <input
          type="text"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Ask something about your company's knowledge base..."
          className="flex-1 rounded-lg border border-zinc-300 px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
        />
        <button
          type="submit"
          className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          Send
        </button>
      </form>
    </div>
  );
}
