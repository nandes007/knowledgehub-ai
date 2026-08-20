import { describe, expect, it, vi } from "vitest";
import { createElement } from "react";
import { renderToString } from "react-dom/server";
import { Sidebar } from "./Sidebar";

let mockPathname = "/chat/conv-123";

// Mock hooks used in Sidebar
vi.mock("next/navigation", () => ({
  useParams: () => ({ conversationId: "conv-123" }),
  usePathname: () => mockPathname,
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
  }),
}));

vi.mock("./AuthProvider", () => ({
  useAuth: () => ({
    isAdmin: true,
    logout: vi.fn(),
  }),
}));

let mockIsLoading = false;

vi.mock("./ConversationsProvider", () => ({
  useConversations: () => ({
    conversations: [
      { id: "conv-123", title: "Active Chat" },
      { id: "conv-456", title: "Past Chat" },
    ],
    activeId: "conv-123",
    setActiveId: vi.fn(),
    isLoading: mockIsLoading,
    loadError: null,
    createAndAdd: vi.fn().mockResolvedValue({ id: "conv-new", title: "New" }),
    renameConversation: vi.fn().mockResolvedValue(undefined),
    deleteConversation: vi.fn().mockResolvedValue(undefined),
    focusChatInput: vi.fn(),
    registerFocusHandler: vi.fn(),
  }),
}));

describe("Sidebar component", () => {
  it("renders with dark chrome, wordmark, nav items, and active conversation on chat route", () => {
    mockPathname = "/chat/conv-123";
    mockIsLoading = false;
    const html = renderToString(createElement(Sidebar));
    expect(html).toContain("bg-surface-overlay");
    expect(html).toContain("New chat");
    expect(html).toContain("Knowledge base");
    expect(html).toContain("Admin");
    expect(html).toContain("Active Chat");
    expect(html).toContain("Past Chat");
    expect(html).toContain("bg-surface-raised");
    expect(html).toContain("Log out");
    expect(html).toContain("Conversation options");
  });

  it("does not highlight conversations when on non-chat route like /knowledge", () => {
    mockPathname = "/knowledge";
    mockIsLoading = false;
    const html = renderToString(createElement(Sidebar));
    expect(html).toContain("Knowledge base");
    expect(html).toContain("bg-gold-muted text-gold");
    expect(html).toContain("Active Chat");
    // Ensure Active Chat does not have the active background class
    expect(html).not.toContain("bg-surface-raised font-medium text-text-primary");
  });

  it("includes collapse toggle button and mobile hamburger button", () => {
    mockPathname = "/chat/conv-123";
    mockIsLoading = false;
    const html = renderToString(createElement(Sidebar));
    expect(html).toContain("Collapse sidebar");
    expect(html).toContain("Toggle conversation list");
  });

  it("renders skeleton placeholders when loading chat history", () => {
    mockPathname = "/chat/conv-123";
    mockIsLoading = true;
    const html = renderToString(createElement(Sidebar));
    expect(html).toContain("Loading chat history");
    expect(html).toContain("animate-shimmer");
    expect(html).not.toContain("Active Chat");
    mockIsLoading = false;
  });
});
