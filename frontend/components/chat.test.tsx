import { describe, expect, it, vi } from "vitest";
import { createElement } from "react";
import { renderToString } from "react-dom/server";
import { MessageBubble } from "./MessageBubble";
import { ChatPanel } from "./ChatPanel";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
  }),
}));

// Mock ConversationsProvider
vi.mock("./ConversationsProvider", () => ({
  useConversations: () => ({
    conversations: [],
    activeId: null,
    setActiveId: vi.fn(),
    addOrRename: vi.fn(),
    registerFocusHandler: vi.fn(),
    focusChatInput: vi.fn(),
  }),
}));

describe("Chat Experience Components", () => {
  describe("MessageBubble", () => {
    it("renders user message as a right-aligned pill with bg-user-bubble", () => {
      const html = renderToString(
        createElement(MessageBubble, {
          message: {
            id: "msg-1",
            role: "user",
            content: "Hello vault!",
          },
        }),
      );

      expect(html).toContain("justify-end");
      expect(html).toContain("bg-user-bubble");
      expect(html).toContain("max-w-[80%]");
      expect(html).toContain("Hello vault!");
    });

    it("renders assistant thinking state with animated dots", () => {
      const html = renderToString(
        createElement(MessageBubble, {
          message: {
            id: "msg-2",
            role: "assistant",
            content: "",
            streaming: true,
          },
        }),
      );

      expect(html).toContain("thinking-dot");
      expect(html).toContain('aria-label="Thinking"');
    });

    it("renders assistant message directly on surface with markdown formatting", () => {
      const html = renderToString(
        createElement(MessageBubble, {
          message: {
            id: "msg-3",
            role: "assistant",
            content: "Here is **bold** text and `code snippet`.",
            streaming: false,
          },
        }),
      );

      expect(html).toContain("<strong>bold</strong>");
      expect(html).toContain("<code>code snippet</code>");
      expect(html).not.toContain("bg-user-bubble");
    });

    it("does not show sources under the answer", () => {
      const html = renderToString(
        createElement(MessageBubble, {
          message: {
            id: "msg-4",
            role: "assistant",
            content: "Hi! How can I help?",
            streaming: false,
            sources: [{ document_id: "doc-1", filename: "handbook.pdf", chunk_preview: "Company policy..." }],
          },
        }),
      );

      expect(html).toContain("Hi! How can I help?");
      expect(html).not.toContain("handbook.pdf");
    });
  });

  describe("ChatPanel", () => {
    it("renders empty state with centered Wordmark and prompt subtitle", () => {
      const html = renderToString(createElement(ChatPanel, {}));
      expect(html).toContain("Ask anything about your company");
      expect(html).toContain("max-w-3xl");
      expect(html).toContain("textarea");
      expect(html).toContain("bg-gold");
    });

    it("renders message history in centered column", () => {
      const html = renderToString(
        createElement(ChatPanel, {
          initialMessages: [
            { id: "m1", role: "user", content: "What is vacation policy?" },
            { id: "m2", role: "assistant", content: "You get 20 days off." },
          ],
        }),
      );

      expect(html).toContain("What is vacation policy?");
      expect(html).toContain("You get 20 days off.");
      expect(html).toContain("max-w-3xl");
    });
  });
});
