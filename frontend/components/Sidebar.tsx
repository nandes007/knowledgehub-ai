"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, usePathname, useRouter } from "next/navigation";
import { useAuth } from "./AuthProvider";
import { useConversations } from "./ConversationsProvider";
import { Wordmark } from "./ui";

/* ── Inline SVG icons (no icon library dependency) ── */

function IconPlus({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <path d="M9 3v12M3 9h12" />
    </svg>
  );
}

function IconFolder({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 5.5V14a1.5 1.5 0 0 0 1.5 1.5h11A1.5 1.5 0 0 0 16 14V7a1.5 1.5 0 0 0-1.5-1.5H9L7.5 3.5H3.5A1.5 1.5 0 0 0 2 5v.5Z" />
    </svg>
  );
}

function IconChart({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 15V9M7.5 15V5M12 15V8M16.5 15V3" />
    </svg>
  );
}

function IconChat({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 3h12a1.5 1.5 0 0 1 1.5 1.5v7A1.5 1.5 0 0 1 15 13H6l-3 3V4.5A1.5 1.5 0 0 1 3 3Z" />
    </svg>
  );
}

function IconChevron({ collapsed }: { collapsed: boolean }) {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`transition-transform duration-200 ${collapsed ? "rotate-180" : ""}`}
    >
      <path d="M10 4 6 8l4 4" />
    </svg>
  );
}

function IconLogout({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6.5 15.5H3.5a1 1 0 0 1-1-1v-11a1 1 0 0 1 1-1h3M12 12.5l3.5-3.5L12 5.5M15.5 9H6.5" />
    </svg>
  );
}

export function Sidebar() {
  const { conversations, loadError, createAndAdd } = useConversations();
  const { isAdmin, logout } = useAuth();
  const params = useParams<{ conversationId?: string }>();
  const pathname = usePathname();
  const router = useRouter();
  const activeId = params?.conversationId;
  const [isOpen, setIsOpen] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);
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

  const sidebarWidth = isCollapsed ? "w-14" : "w-[260px]";

  return (
    <>
      {/* Mobile hamburger */}
      <button
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        aria-label="Toggle conversation list"
        className="fixed left-3 top-3 z-50 rounded-lg border border-border bg-surface-raised p-2 text-text-primary md:hidden"
      >
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M3 5h14M3 10h14M3 15h14" strokeLinecap="round" />
        </svg>
      </button>

      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/60 backdrop-blur-sm md:hidden"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex shrink-0 -translate-x-full flex-col bg-surface-overlay text-text-primary transition-all duration-200 ease-in-out md:static md:translate-x-0 ${sidebarWidth} ${
          isOpen ? "translate-x-0" : ""
        }`}
      >
        {/* Header with wordmark + collapse toggle */}
        <div className="flex items-center justify-between border-b border-border px-3 py-4 pt-16 md:pt-4">
          <Wordmark collapsed={isCollapsed} />
          <button
            type="button"
            onClick={() => setIsCollapsed((c) => !c)}
            className="hidden rounded-md p-1 text-text-secondary hover:bg-border hover:text-text-primary md:block"
            aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            <IconChevron collapsed={isCollapsed} />
          </button>
        </div>

        {/* Nav actions */}
        <div className="space-y-1 p-2">
          <button
            type="button"
            onClick={handleNewChat}
            className={`flex w-full items-center gap-2.5 rounded-lg bg-gold px-3 py-2 text-sm font-medium text-surface-primary transition-colors duration-120 hover:bg-gold-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-2 focus-visible:ring-offset-surface-overlay ${
              isCollapsed ? "justify-center px-0" : ""
            }`}
            title="New chat"
            aria-label="New chat"
          >
            <IconPlus size={16} />
            {!isCollapsed && <span>New chat</span>}
          </button>
          {createError && !isCollapsed && <p className="px-1 text-xs text-status-void">{createError}</p>}

          <Link
            href="/knowledge"
            onClick={() => setIsOpen(false)}
            className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors duration-120 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-2 focus-visible:ring-offset-surface-overlay ${
              pathname === "/knowledge"
                ? "bg-gold-muted text-gold"
                : "text-text-secondary hover:bg-border hover:text-text-primary"
            } ${isCollapsed ? "justify-center px-0" : ""}`}
            title="Knowledge base"
            aria-label="Knowledge base"
          >
            <IconFolder size={16} />
            {!isCollapsed && <span>Knowledge base</span>}
          </Link>

          {isAdmin && (
            <Link
              href="/admin"
              onClick={() => setIsOpen(false)}
              className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors duration-120 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-2 focus-visible:ring-offset-surface-overlay ${
                pathname === "/admin"
                  ? "bg-gold-muted text-gold"
                  : "text-text-secondary hover:bg-border hover:text-text-primary"
              } ${isCollapsed ? "justify-center px-0" : ""}`}
              title="Admin"
              aria-label="Admin"
            >
              <IconChart size={16} />
              {!isCollapsed && <span>Admin</span>}
            </Link>
          )}
        </div>

        {/* Conversation list */}
        <nav className="flex-1 overflow-y-auto px-2 pb-2">
          {!isCollapsed && (
            <>
              {loadError ? (
                <p className="px-3 py-2 text-sm text-status-void">{loadError}</p>
              ) : conversations.length === 0 ? (
                <p className="px-3 py-2 text-sm text-text-tertiary">No conversations yet. Start one above.</p>
              ) : (
                <ul className="space-y-0.5">
                  {conversations.map((conversation) => (
                    <li key={conversation.id}>
                      <Link
                        href={`/chat/${conversation.id}`}
                        onClick={() => setIsOpen(false)}
                        className={`group flex items-center gap-2.5 truncate rounded-lg px-3 py-2 text-sm transition-colors duration-120 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-2 focus-visible:ring-offset-surface-overlay ${
                          conversation.id === activeId
                            ? "border-l-[3px] border-l-gold bg-gold-muted/50 pl-[9px] font-medium text-text-primary"
                            : "text-text-secondary hover:bg-border hover:text-text-primary"
                        }`}
                      >
                        <IconChat size={14} />
                        <span className="truncate">{conversation.title}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </nav>

        {/* Footer */}
        <div className="border-t border-border p-2">
          <button
            type="button"
            onClick={handleLogout}
            className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-text-secondary transition-colors duration-120 hover:bg-border hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-2 focus-visible:ring-offset-surface-overlay ${
              isCollapsed ? "justify-center px-0" : ""
            }`}
            title="Log out"
            aria-label="Log out"
          >
            <IconLogout size={16} />
            {!isCollapsed && <span>Log out</span>}
          </button>
        </div>
      </aside>
    </>
  );
}
