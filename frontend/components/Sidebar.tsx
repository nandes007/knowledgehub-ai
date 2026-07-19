"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useConversations } from "./ConversationsProvider";

export function Sidebar() {
  const { conversations, createAndAdd } = useConversations();
  const params = useParams<{ conversationId?: string }>();
  const router = useRouter();
  const activeId = params?.conversationId;

  async function handleNewChat() {
    const conversation = await createAndAdd();
    router.push(`/chat/${conversation.id}`);
  }

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="p-3">
        <button
          type="button"
          onClick={handleNewChat}
          className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-left text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-900"
        >
          + New chat
        </button>
      </div>
      <nav className="flex-1 overflow-y-auto px-2 pb-3">
        <ul className="space-y-1">
          {conversations.map((conversation) => (
            <li key={conversation.id}>
              <Link
                href={`/chat/${conversation.id}`}
                className={`block truncate rounded-lg px-3 py-2 text-sm ${
                  conversation.id === activeId
                    ? "bg-zinc-200 font-medium text-zinc-900 dark:bg-zinc-800 dark:text-zinc-50"
                    : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-900"
                }`}
              >
                {conversation.title}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  );
}
