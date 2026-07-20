"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, usePathname, useRouter } from "next/navigation";
import { useAuth } from "./AuthProvider";
import { useConversations } from "./ConversationsProvider";

export function Sidebar() {
  const { conversations, loadError, createAndAdd } = useConversations();
  const { logout } = useAuth();
  const params = useParams<{ conversationId?: string }>();
  const pathname = usePathname();
  const router = useRouter();
  const activeId = params?.conversationId;
  const [isOpen, setIsOpen] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  async function handleNewChat() {
    setCreateError(null);
    try {
      const conversation = await createAndAdd();
      setIsOpen(false);
      router.push(`/chat/${conversation.id}`);
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Couldn't start a new chat.");
    }
  }

  function handleLogout() {
    logout();
    setIsOpen(false);
    router.replace("/login");
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        aria-label="Toggle conversation list"
        className="fixed left-3 top-3 z-50 rounded-lg border border-zinc-300 bg-white p-2 text-zinc-700 md:hidden dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200"
      >
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M3 5h14M3 10h14M3 15h14" strokeLinecap="round" />
        </svg>
      </button>
      {isOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/40 md:hidden"
          onClick={() => setIsOpen(false)}
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 shrink-0 -translate-x-full flex-col border-r border-zinc-200 bg-zinc-50 transition-transform duration-200 md:static md:translate-x-0 dark:border-zinc-800 dark:bg-zinc-950 ${
          isOpen ? "translate-x-0" : ""
        }`}
      >
        <div className="space-y-2 p-3 pt-16 md:pt-3">
          <button
            type="button"
            onClick={handleNewChat}
            className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-left text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-900"
          >
            + New chat
          </button>
          {createError && <p className="text-xs text-red-600 dark:text-red-400">{createError}</p>}
          <Link
            href="/knowledge"
            onClick={() => setIsOpen(false)}
            className={`block rounded-lg px-3 py-2 text-sm ${
              pathname === "/knowledge"
                ? "bg-zinc-200 font-medium text-zinc-900 dark:bg-zinc-800 dark:text-zinc-50"
                : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-900"
            }`}
          >
            Knowledge base
          </Link>
        </div>
        <nav className="flex-1 overflow-y-auto px-2 pb-3">
          {loadError ? (
            <p className="px-3 py-2 text-sm text-red-600 dark:text-red-400">{loadError}</p>
          ) : conversations.length === 0 ? (
            <p className="px-3 py-2 text-sm text-zinc-500 dark:text-zinc-400">
              No conversations yet. Start one above.
            </p>
          ) : (
            <ul className="space-y-1">
              {conversations.map((conversation) => (
                <li key={conversation.id}>
                  <Link
                    href={`/chat/${conversation.id}`}
                    onClick={() => setIsOpen(false)}
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
          )}
        </nav>
        <div className="border-t border-zinc-200 p-3 dark:border-zinc-800">
          <button
            type="button"
            onClick={handleLogout}
            className="w-full rounded-lg px-3 py-2 text-left text-sm text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-900"
          >
            Log out
          </button>
        </div>
      </aside>
    </>
  );
}
