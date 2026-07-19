"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { createConversation, listConversations, type Conversation } from "@/lib/api";

const TITLE_MAX_LENGTH = 48;

function deriveTitle(message: string): string {
  return message.length > TITLE_MAX_LENGTH ? `${message.slice(0, TITLE_MAX_LENGTH)}…` : message;
}

type ConversationsContextValue = {
  conversations: Conversation[];
  loadError: string | null;
  createAndAdd: () => Promise<Conversation>;
  addOrRename: (id: string, firstMessage: string) => void;
};

const ConversationsContext = createContext<ConversationsContextValue | null>(null);

export function ConversationsProvider({ children }: { children: React.ReactNode }) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  // First-write-wins titles derived client-side, since the backend never persists a real
  // title. Kept outside React state so a slow GET /conversations can't clobber a title
  // that a page already derived from that conversation's first message.
  const titleOverridesRef = useRef<Map<string, string>>(new Map());

  const applyOverrides = useCallback((list: Conversation[]) => {
    const overrides = titleOverridesRef.current;
    return list.map((c) => (overrides.has(c.id) ? { ...c, title: overrides.get(c.id)! } : c));
  }, []);

  useEffect(() => {
    listConversations()
      .then((list) => setConversations(applyOverrides(list)))
      .catch((err) => setLoadError(err instanceof Error ? err.message : "Couldn't load conversations."));
  }, [applyOverrides]);

  const createAndAdd = useCallback(async () => {
    const conversation = await createConversation();
    setConversations((prev) => [conversation, ...prev]);
    return conversation;
  }, []);

  const addOrRename = useCallback((id: string, firstMessage: string) => {
    const overrides = titleOverridesRef.current;
    if (!overrides.has(id)) overrides.set(id, deriveTitle(firstMessage));
    const title = overrides.get(id)!;

    setConversations((prev) => {
      const exists = prev.some((c) => c.id === id);
      if (!exists) return [{ id, title }, ...prev];
      return prev.map((c) => (c.id === id ? { ...c, title } : c));
    });
  }, []);

  return (
    <ConversationsContext.Provider value={{ conversations, loadError, createAndAdd, addOrRename }}>
      {children}
    </ConversationsContext.Provider>
  );
}

export function useConversations() {
  const ctx = useContext(ConversationsContext);
  if (!ctx) throw new Error("useConversations must be used within ConversationsProvider");
  return ctx;
}
