"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, usePathname, useRouter } from "next/navigation";
import { useAuth } from "./AuthProvider";
import { useConversations } from "./ConversationsProvider";
import { SealMark } from "./ui";

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
        className="fixed left-3 top-3 z-50 rounded-sm border border-rule bg-paper-raised p-2 text-ink md:hidden"
      >
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M3 5h14M3 10h14M3 15h14" strokeLinecap="round" />
        </svg>
      </button>
      {isOpen && (
        <div
          className="fixed inset-0 z-30 bg-ink/40 md:hidden"
          onClick={() => setIsOpen(false)}
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 shrink-0 -translate-x-full flex-col bg-ledger text-ledger-ink transition-transform duration-200 md:static md:translate-x-0 ${
          isOpen ? "translate-x-0" : ""
        }`}
      >
        <div className="flex items-center gap-2 border-b border-rule-dark px-4 py-4 pt-16 md:pt-4">
          <SealMark className="h-6 w-6 text-brass" />
          <span className="font-serif text-sm font-semibold">KnowledgeHub</span>
        </div>
        <div className="space-y-2 p-3">
          <button
            type="button"
            onClick={handleNewChat}
            className="w-full rounded-sm bg-brass px-3 py-2 text-left text-sm font-medium text-ink hover:bg-brass-strong hover:text-paper focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ledger-ink focus-visible:ring-offset-2 focus-visible:ring-offset-ledger"
          >
            + New chat
          </button>
          {createError && <p className="text-xs text-stamp-void-on-dark">{createError}</p>}
          <Link
            href="/knowledge"
            onClick={() => setIsOpen(false)}
            className={`block rounded-sm px-3 py-2 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass focus-visible:ring-offset-2 focus-visible:ring-offset-ledger ${
              pathname === "/knowledge"
                ? "bg-rule-dark text-ledger-ink"
                : "text-ledger-ink-muted hover:bg-rule-dark hover:text-ledger-ink"
            }`}
          >
            Knowledge base
          </Link>
        </div>
        <nav className="flex-1 overflow-y-auto px-2 pb-3">
          {loadError ? (
            <p className="px-3 py-2 text-sm text-stamp-void-on-dark">{loadError}</p>
          ) : conversations.length === 0 ? (
            <p className="px-3 py-2 text-sm text-ledger-ink-muted">No conversations yet. Start one above.</p>
          ) : (
            <ul className="space-y-1">
              {conversations.map((conversation) => (
                <li key={conversation.id}>
                  <Link
                    href={`/chat/${conversation.id}`}
                    onClick={() => setIsOpen(false)}
                    className={`block truncate rounded-sm px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass focus-visible:ring-offset-2 focus-visible:ring-offset-ledger ${
                      conversation.id === activeId
                        ? "bg-rule-dark font-medium text-ledger-ink"
                        : "text-ledger-ink-muted hover:bg-rule-dark hover:text-ledger-ink"
                    }`}
                  >
                    {conversation.title}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </nav>
        <div className="border-t border-rule-dark p-3">
          <button
            type="button"
            onClick={handleLogout}
            className="w-full rounded-sm px-3 py-2 text-left text-sm text-ledger-ink-muted hover:bg-rule-dark hover:text-ledger-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass focus-visible:ring-offset-2 focus-visible:ring-offset-ledger"
          >
            Log out
          </button>
        </div>
      </aside>
    </>
  );
}
