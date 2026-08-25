import { describe, expect, it, vi } from "vitest";
import { createElement } from "react";
import { renderToString } from "react-dom/server";
import AuthLayout from "../app/(auth)/layout";
import LoginPage from "../app/(auth)/login/page";
import RegisterPage from "../app/(auth)/register/page";
import AdminPage from "../app/(app)/admin/page";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
  }),
}));

// Mock AuthProvider
const mockUseAuth = vi.fn(() => ({
  token: null,
  isReady: true,
  isAdmin: true,
  isSuperAdmin: false,
  isMember: false,
  user: {
    email: "admin@acme.com",
    role: "admin",
    displayName: "Admin",
    companyName: "Acme",
    approvalStatus: "approved",
    companyId: "c1",
    departmentId: null,
    departmentName: null,
  },
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
}));

vi.mock("@/components/AuthProvider", () => ({
  useAuth: () => mockUseAuth(),
}));

// Mock API
vi.mock("@/lib/api", () => ({
  ADMIN_REQUIRED: "admin_required",
  getStats: vi.fn().mockResolvedValue({
    documentCount: 42,
    estimatedCostUsd: 1.2345,
    messagesPerDay: [{ date: "2026-08-01", count: 10 }],
    documentsPerUser: [{ email: "user@example.com", count: 5 }],
    costPerDay: [{ date: "2026-08-01", costUsd: 0.5 }],
  }),
}));

describe("Auth and Admin Pages", () => {
  describe("AuthLayout", () => {
    it("renders with dark background, radial glow, and Wordmark", () => {
      const html = renderToString(
        createElement(AuthLayout, {}, createElement("div", null, "Child Content")),
      );
      expect(html).toContain("bg-surface-primary");
      expect(html).toContain("radial-gradient");
      expect(html).toContain("rgba(212,167,69,0.06)");
      expect(html).toContain("nowledgeHub");
      expect(html).toContain("Child Content");
    });
  });

  describe("LoginPage", () => {
    it("renders login form with new primitives and gold register link", () => {
      const html = renderToString(createElement(LoginPage));
      expect(html).toContain("Log in");
      expect(html).toContain("bg-surface-input");
      expect(html).toContain("bg-gold");
      expect(html).toContain("text-gold");
      expect(html).toContain("href=\"/register\"");
    });
  });

  describe("RegisterPage", () => {
    it("renders register form with new primitives and gold login link", () => {
      const html = renderToString(createElement(RegisterPage));
      expect(html).toContain("Register");
      expect(html).toContain("Company Name");
      expect(html).toContain("Name");
      expect(html).toContain("Email");
      expect(html).toContain("Password");
      expect(html).toContain("bg-surface-input");
      expect(html).toContain("bg-gold");
      expect(html).toContain("text-gold");
      expect(html).toContain("href=\"/login\"");
    });
  });

  describe("AdminPage", () => {
    it("renders company admin tabs (Stats, Team) when logged in as company admin", () => {
      mockUseAuth.mockReturnValueOnce({
        token: "test-token",
        isReady: true,
        isAdmin: true,
        isSuperAdmin: false,
        isMember: false,
        user: {
          email: "admin@acme.com",
          role: "admin",
          displayName: "Admin",
          companyName: "Acme",
          approvalStatus: "approved",
          companyId: "c1",
          departmentId: null,
          departmentName: null,
        },
        login: vi.fn(),
        register: vi.fn(),
        logout: vi.fn(),
      });

      const html = renderToString(createElement(AdminPage));
      expect(html).toContain("Admin");
      expect(html).toContain("Stats");
      expect(html).toContain("Team");
      expect(html).not.toContain("Pending Approvals");
      expect(html).not.toContain("Companies");
      expect(html).toContain("Usage across the vault, last 30 days.");
    });

    it("renders all 4 tabs for superadmin with Pending Approvals active", () => {
      mockUseAuth.mockReturnValueOnce({
        token: "super-token",
        isReady: true,
        isAdmin: true,
        isSuperAdmin: true,
        isMember: false,
        user: {
          email: "super@platform.com",
          role: "superadmin",
          displayName: "Super Admin",
          companyName: null,
          approvalStatus: "approved",
          companyId: null,
          departmentId: null,
          departmentName: null,
        },
        login: vi.fn(),
        register: vi.fn(),
        logout: vi.fn(),
      });

      const html = renderToString(createElement(AdminPage));
      expect(html).toContain("Admin");
      expect(html).toContain("Pending Approvals");
      expect(html).toContain("Companies");
      expect(html).toContain("Stats");
      expect(html).toContain("Team");
      expect(html).toContain("Platform administration and organization management.");
      expect(html).toContain("Pending company registrations will appear here.");
    });
  });
});
