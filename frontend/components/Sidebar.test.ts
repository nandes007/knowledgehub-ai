import { describe, expect, it, vi } from "vitest";
import { createElement } from "react";
import { renderToString } from "react-dom/server";
import { Sidebar } from "./Sidebar";

// Mock hooks used in Sidebar
vi.mock("next/navigation", () => ({
  useParams: () => ({ conversationId: "conv-123" }),
  usePathname: () => "/knowledge",
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
    isLoading: mockIsLoading,
    loadError: null,
    createAndAdd: vi.fn().mockResolvedValue({ id: "conv-new", title: "New" }),
  }),
}));

describe("Sidebar component", () => {
  it("renders with dark chrome, wordmark, nav items, and active conversation", () => {
    mockIsLoading = false;
    const html = renderToString(createElement(Sidebar));
    expect(html).toContain("bg-surface-overlay");
    expect(html).toContain("New chat");
    expect(html).toContain("Knowledge base");
    expect(html).toContain("Admin");
    expect(html).toContain("Active Chat");
    expect(html).toContain("Past Chat");
    expect(html).toContain("border-l-gold");
    expect(html).toContain("Log out");
  });

  it("includes collapse toggle button and mobile hamburger button", () => {
    mockIsLoading = false;
    const html = renderToString(createElement(Sidebar));
    expect(html).toContain("Collapse sidebar");
    expect(html).toContain("Toggle conversation list");
  });

  it("renders skeleton placeholders when loading chat history", () => {
    mockIsLoading = true;
    const html = renderToString(createElement(Sidebar));
    expect(html).toContain("Loading chat history");
    expect(html).toContain("animate-pulse");
    expect(html).not.toContain("Active Chat");
    mockIsLoading = false;
  });
});
