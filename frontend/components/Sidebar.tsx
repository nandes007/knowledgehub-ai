"use client";

import { useEffect, useRef, useState } from "react";
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

function IconDots({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="currentColor">
      <circle cx="8" cy="3" r="1.5" />
      <circle cx="8" cy="8" r="1.5" />
      <circle cx="8" cy="13" r="1.5" />
    </svg>
  );
}

function IconPencil({ size = 13 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M11.5 2.5a1.414 1.414 0 0 1 2 2L5 13H2.5v-2.5l8.5-8.5Z" />
    </svg>
  );
}

function IconTrash({ size = 13 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2.5 4.5h11M5.5 4.5V3a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v1.5M6 7.5v4.5M10 7.5v4.5M3.5 4.5l.8 9.2A1.5 1.5 0 0 0 5.8 15h4.4a1.5 1.5 0 0 0 1.5-1.3l.8-9.2" />
    </svg>
  );
}

export function Sidebar() {
  const {
    conversations,
    activeId: providerActiveId,
    setActiveId,
    isLoading,
    loadError,
    focusChatInput,
    renameConversation,
    deleteConversation,
  } = useConversations();
  const { isAdmin, logout } = useAuth();
  const params = useParams<{ conversationId?: string }>();
  const pathname = usePathname();
  const router = useRouter();
  const isChatRoute = pathname === "/" || pathname === "/chat" || (pathname?.startsWith("/chat/") ?? false);
  const activeId = isChatRoute ? (params?.conversationId ?? providerActiveId) : null;
  const [isOpen, setIsOpen] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);

  // Rename and Delete state
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [deletingConversation, setDeletingConversation] = useState<{ id: string; title: string } | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  // Close menu on click outside or Escape
  useEffect(() => {
    if (!menuOpenId) return;
    function handleDown(e: MouseEvent | TouchEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpenId(null);
      }
    }
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setMenuOpenId(null);
    }
    document.addEventListener("mousedown", handleDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [menuOpenId]);

  function handleNewChat() {
    setIsOpen(false);
    setActiveId?.(null);
    focusChatInput?.();
    router.push("/");
  }

  function handleLogout() {
    logout();
    setIsOpen(false);
    router.replace("/login");
  }

  function startEditing(id: string, currentTitle: string) {
    setMenuOpenId(null);
    setEditingId(id);
    setEditTitle(currentTitle);
  }

  async function submitRename(id: string) {
    const trimmed = editTitle.trim();
    setEditingId(null);
    if (trimmed && trimmed !== conversations.find((c) => c.id === id)?.title) {
      await renameConversation(id, trimmed);
    }
  }

  function confirmDelete(id: string, title: string) {
    setMenuOpenId(null);
    setDeletingConversation({ id, title });
  }

  async function handleDelete() {
    if (!deletingConversation) return;
    setIsDeleting(true);
    try {
      await deleteConversation(deletingConversation.id);
      if (activeId === deletingConversation.id) {
        setActiveId?.(null);
        router.push("/");
      }
      setDeletingConversation(null);
    } finally {
      setIsDeleting(false);
    }
  }

  const sidebarWidth = isCollapsed ? "w-14" : "w-[260px]";

  return (
    <>
      {/* Mobile hamburger */}
      <button
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        aria-label="Toggle conversation list"
        className="fixed left-3 top-3 z-50 cursor-pointer rounded-lg border border-border bg-surface-raised p-2 text-text-primary md:hidden"
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
            className="hidden cursor-pointer rounded-md p-1 text-text-secondary hover:bg-border hover:text-text-primary md:block"
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
            className={`flex w-full cursor-pointer items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors duration-120 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-2 focus-visible:ring-offset-surface-overlay text-text-secondary hover:bg-border hover:text-text-primary ${
              isCollapsed ? "justify-center px-0" : ""
            }`}
            title="New chat"
            aria-label="New chat"
          >
            <IconPlus size={16} />
            {!isCollapsed && <span>New chat</span>}
          </button>

          <Link
            href="/knowledge"
            onClick={() => {
              setIsOpen(false);
              setActiveId?.(null);
            }}
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
              onClick={() => {
                setIsOpen(false);
                setActiveId?.(null);
              }}
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
              <div className="mb-1 mt-4 px-3 text-xs font-semibold text-text-tertiary">
                Recent
              </div>
              {loadError ? (
                <p className="px-3 py-2 text-sm text-status-void">{loadError}</p>
              ) : isLoading ? (
                <ul className="space-y-1 px-1 py-1" aria-label="Loading chat history">
                  {["w-3/4", "w-1/2", "w-4/5", "w-3/5", "w-2/3"].map((width, idx) => (
                    <li
                      key={idx}
                      className="flex items-center gap-2.5 rounded-lg px-2.5 py-2"
                    >
                      <div className="h-3.5 w-3.5 shrink-0 rounded animate-shimmer" />
                      <div className={`h-3.5 ${width} rounded animate-shimmer`} />
                    </li>
                  ))}
                </ul>
              ) : conversations.length === 0 ? (
                <p className="px-3 py-2 text-sm text-text-tertiary animate-fade-in">
                  No conversations yet. Start one above.
                </p>
              ) : (
                <ul className="space-y-0.5 animate-fade-in">
                  {conversations.map((conversation) => (
                    <li key={conversation.id} className="relative group">
                      {editingId === conversation.id ? (
                        <div className="flex items-center gap-2 rounded-lg bg-surface-raised px-2.5 py-1.5 ring-1 ring-gold">
                          <IconChat size={14} />
                          <input
                            type="text"
                            autoFocus
                            value={editTitle}
                            onChange={(e) => setEditTitle(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") {
                                e.preventDefault();
                                submitRename(conversation.id);
                              } else if (e.key === "Escape") {
                                e.preventDefault();
                                setEditingId(null);
                              }
                            }}
                            onBlur={() => submitRename(conversation.id)}
                            className="w-full bg-transparent text-sm text-text-primary outline-none focus:outline-none"
                            aria-label="Rename conversation"
                          />
                        </div>
                      ) : (
                        <div
                          className={`group relative flex items-center justify-between rounded-lg px-3 py-2 text-sm transition-all duration-150 cursor-pointer ${
                            conversation.id === activeId
                              ? "bg-surface-raised font-medium text-text-primary"
                              : "text-text-secondary hover:bg-border hover:text-text-primary"
                          }`}
                        >
                          <Link
                            href={`/chat/${conversation.id}`}
                            onClick={() => {
                              setIsOpen(false);
                              setActiveId?.(conversation.id);
                            }}
                            className="absolute inset-0 z-0 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold"
                            aria-label={conversation.title}
                          />

                          <div className="pointer-events-none relative z-10 flex min-w-0 flex-1 items-center gap-2.5 truncate">
                            <span className="shrink-0">
                              <IconChat size={14} />
                            </span>
                            <span className="truncate">{conversation.title}</span>
                          </div>

                          <div className="relative z-20 shrink-0 ml-1">
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                e.preventDefault();
                                setMenuOpenId((curr) => (curr === conversation.id ? null : conversation.id));
                              }}
                              aria-label="Conversation options"
                              title="Options"
                              className={`cursor-pointer rounded p-1 transition-all text-text-secondary hover:bg-surface-overlay hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold ${
                                menuOpenId === conversation.id
                                  ? "opacity-100 bg-surface-overlay text-text-primary"
                                  : "opacity-0 group-hover:opacity-100 focus:opacity-100"
                              }`}
                            >
                              <IconDots size={14} />
                            </button>

                            {menuOpenId === conversation.id && (
                              <div
                                ref={menuRef}
                                className="absolute right-0 top-full z-50 mt-1 w-32 overflow-hidden rounded-lg border border-border bg-surface-overlay p-1 shadow-lg animate-fade-in"
                                onClick={(e) => e.stopPropagation()}
                              >
                                <button
                                  type="button"
                                  onClick={() => startEditing(conversation.id, conversation.title)}
                                  className="flex w-full cursor-pointer items-center gap-2 rounded-md px-2.5 py-1.5 text-xs text-text-secondary transition-colors hover:bg-border hover:text-text-primary"
                                >
                                  <IconPencil size={13} />
                                  <span>Rename</span>
                                </button>
                                <button
                                  type="button"
                                  onClick={() => confirmDelete(conversation.id, conversation.title)}
                                  className="flex w-full cursor-pointer items-center gap-2 rounded-md px-2.5 py-1.5 text-xs text-status-void transition-colors hover:bg-status-void/15"
                                >
                                  <IconTrash size={13} />
                                  <span>Delete</span>
                                </button>
                              </div>
                            )}
                          </div>
                        </div>
                      )}
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
            className={`flex w-full cursor-pointer items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-text-secondary transition-colors duration-120 hover:bg-border hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-2 focus-visible:ring-offset-surface-overlay ${
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

      {/* Delete Confirmation Modal */}
      {deletingConversation && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="fixed inset-0 bg-black/70 backdrop-blur-xs animate-fade-in"
            onClick={() => !isDeleting && setDeletingConversation(null)}
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-dialog-title"
            className="relative z-10 w-full max-w-sm rounded-xl border border-border bg-surface-overlay p-5 shadow-2xl animate-scale-in"
          >
            <h3 id="delete-dialog-title" className="text-base font-semibold text-text-primary">
              Delete conversation?
            </h3>
            <p className="mt-2 text-sm text-text-secondary">
              This will delete <strong className="text-text-primary">&ldquo;{deletingConversation.title}&rdquo;</strong>. This action cannot be undone.
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                disabled={isDeleting}
                onClick={() => setDeletingConversation(null)}
                className="cursor-pointer rounded-lg border border-border px-3.5 py-1.5 text-sm font-medium text-text-secondary transition-colors hover:bg-border hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isDeleting}
                onClick={handleDelete}
                className="cursor-pointer rounded-lg bg-status-void px-3.5 py-1.5 text-sm font-medium text-white transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-status-void disabled:opacity-50"
              >
                {isDeleting ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
