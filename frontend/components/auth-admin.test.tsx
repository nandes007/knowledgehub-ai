import { beforeEach, describe, expect, it, vi } from "vitest";
import { createElement } from "react";
import { renderToString } from "react-dom/server";
import AuthLayout from "../app/(auth)/layout";
import LoginPage from "../app/(auth)/login/page";
import RegisterPage from "../app/(auth)/register/page";
import Home from "../app/(app)/page";
import CompanyLayout from "../app/(app)/[slug]/layout";
import CompanyAdminPage from "../app/(app)/[slug]/admin/page";
import InstanceAdminPage from "../app/(app)/instance/page";
import InvitePage from "../app/invite/[token]/page";
import { CompanyProvider } from "./CompanyProvider";
import type { Me, MyCompany } from "@/lib/api";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/acme",
  useParams: () => ({}),
}));

// The company layout's chrome is covered by its own tests.
vi.mock("./Sidebar", () => ({ Sidebar: () => null }));
vi.mock("./ConversationsProvider", () => ({
  ConversationsProvider: ({ children }: { children: React.ReactNode }) => children,
}));

// React's `use` reads an already-settled thenable synchronously, so SSR doesn't suspend.
function settled<T>(value: T): Promise<T> {
  return Object.assign(Promise.resolve(value), { status: "fulfilled", value });
}

function company(overrides: Partial<MyCompany> = {}): MyCompany {
  return { id: "c1", name: "Acme", slug: "acme", status: "active", role: "admin", departmentId: null, departmentName: null, ...overrides };
}

function me(overrides: Partial<Me> = {}): Me {
  return { id: "u1", email: "jane@acme.com", displayName: "Jane", isInstanceAdmin: false, approvalStatus: "approved", companies: [company()], ...overrides };
}

let auth: { token: string | null; user: Me | null };
beforeEach(() => {
  auth = { token: "t", user: me() };
});

vi.mock("@/components/AuthProvider", () => ({
  useAuth: () => ({
    ...auth,
    isReady: true,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
  }),
}));

function inCompany(role: MyCompany["role"], element: React.ReactElement) {
  return renderToString(<CompanyProvider company={company({ role })}>{element}</CompanyProvider>);
}

describe("auth pages", () => {
  it("AuthLayout renders the branded shell around its child", () => {
    auth.token = null;
    const html = renderToString(createElement(AuthLayout, null, createElement("div", null, "Child Content")));
    expect(html).toContain("radial-gradient");
    expect(html).toContain("nowledgeHub");
    expect(html).toContain("Child Content");
  });

  it("LoginPage renders the form and a register link", () => {
    const html = renderToString(createElement(LoginPage, { searchParams: settled({}) }));
    expect(html).toContain("Log in");
    expect(html).toContain('href="/register"');
  });

  it("RegisterPage asks for an account only, no company", () => {
    const html = renderToString(createElement(RegisterPage));
    expect(html).toContain("Register");
    expect(html).toContain("Email");
    expect(html).toContain("Password");
    expect(html).not.toContain("Company");
    expect(html).toContain('href="/login"');
  });
});

describe("home", () => {
  it("offers to create a company or ask for an invite when the user has none", () => {
    auth.user = me({ companies: [] });
    const html = renderToString(createElement(Home));
    expect(html).toContain("not in a company yet");
    expect(html).toContain("Create company");
    expect(html).toContain("invite link");
    expect(html).not.toContain('href="/instance"');
  });

  it("links instance admins to platform administration from the empty state", () => {
    auth.user = me({ companies: [], isInstanceAdmin: true });
    expect(renderToString(createElement(Home))).toContain('href="/instance"');
  });

  it("renders nothing while redirecting a user who has companies", () => {
    expect(renderToString(createElement(Home))).toBe("");
  });
});

describe("company layout", () => {
  const render = (slug: string) =>
    renderToString(
      <CompanyLayout params={settled({ slug })}>
        <main>page body</main>
      </CompanyLayout>,
    );

  it("renders the page for a member of the slug's company", () => {
    expect(render("acme")).toContain("page body");
  });

  it("says not found for a company the user isn't a member of", () => {
    const html = render("globex");
    expect(html).toContain("Company not found");
    expect(html).not.toContain("page body");
  });

  it("blocks only a suspended company", () => {
    auth.user = me({ companies: [company({ status: "suspended" }), company({ id: "c2", slug: "globex", name: "Globex" })] });
    expect(render("acme")).toContain("Company suspended");
    expect(render("globex")).toContain("page body");
  });
});

describe("company admin page", () => {
  it("gives the owner a Settings tab", () => {
    const html = inCompany("owner", createElement(CompanyAdminPage));
    expect(html).toContain("Members");
    expect(html).toContain("Departments");
    expect(html).toContain("Settings");
  });

  it("gives an admin everything but Settings", () => {
    const html = inCompany("admin", createElement(CompanyAdminPage));
    expect(html).toContain("Members");
    expect(html).not.toContain("Settings");
  });

  it("renders nothing for a member", () => {
    expect(inCompany("member", createElement(CompanyAdminPage))).toBe("");
  });
});

describe("instance admin page", () => {
  it("is shown to instance admins", () => {
    auth.user = me({ isInstanceAdmin: true });
    const html = renderToString(createElement(InstanceAdminPage));
    expect(html).toContain("Instance admin");
    expect(html).toContain("Users");
    expect(html).toContain("Companies");
  });

  it("renders nothing for everyone else, even company owners", () => {
    auth.user = me({ companies: [company({ role: "owner" })] });
    expect(renderToString(createElement(InstanceAdminPage))).toBe("");
  });
});

describe("invite page", () => {
  it("loads the invite before showing what to do", () => {
    auth = { token: null, user: null };
    const html = renderToString(createElement(InvitePage, { params: settled({ token: "tok" }) }));
    expect(html).toContain("Loading invite");
  });
});
