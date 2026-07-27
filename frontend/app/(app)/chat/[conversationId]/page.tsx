"use client";

import { use, useEffect, useState } from "react";
import { ChatPanel } from "@/components/ChatPanel";
import { getConversationMessages } from "@/lib/api";
import type { ChatMessage } from "@/components/MessageBubble";
import { useConversations } from "@/components/ConversationsProvider";

export default function ChatConversationPage({
  params,
}: {
  params: Promise<{ conversationId: string }>;
}) {
  const { conversationId } = use(params);
  return <ConversationLoader key={conversationId} conversationId={conversationId} />;
}

function ConversationLoader({ conversationId }: { conversationId: string }) {
  const [initialMessages, setInitialMessages] = useState<ChatMessage[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const { addOrRename } = useConversations();

  useEffect(() => {
    getConversationMessages(conversationId)
      .then((messages) => {
        setInitialMessages(messages.map(({ id, role, content, sources }) => ({ id, role, content, sources })));
        const firstUserMessage = messages.find((m) => m.role === "user");
        if (firstUserMessage) addOrRename(conversationId, firstUserMessage.content);
      })
      .catch((err) => setLoadError(err instanceof Error ? err.message : "Couldn't load this conversation."));
  }, [conversationId, addOrRename]);

  if (loadError) {
    return <div className="flex flex-1 items-center justify-center text-sm text-stamp-void">{loadError}</div>;
  }

  if (initialMessages === null) {
    return <div className="flex flex-1 items-center justify-center text-sm text-ink-muted">Loading…</div>;
  }

  return <ChatPanel conversationId={conversationId} initialMessages={initialMessages} />;
}
