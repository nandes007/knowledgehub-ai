import { afterEach, describe, expect, it, vi } from "vitest";
import {
  activateCompany,
  approveUser,
  createConversation,
  createDepartment,
  createUser,
  deleteConversation,
  deleteDepartment,
  deleteDocument,
  deleteUser,
  getConversationMessages,
  getMe,
  getStats,
  listCompanies,
  listConversations,
  listDepartments,
  listDocuments,
  listPendingUsers,
  listTeamUsers,
  loginAccount,
  registerAccount,
  rejectUser,
  renameConversation,
  sendChatMessage,
  suspendCompany,
  updateUser,
  uploadDocument,
} from "./api";
import { clearToken, getToken, setToken } from "./auth";

function sseResponse(body: string, init?: ResponseInit): Response {
  return new Response(body, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
    ...init,
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  clearToken();
});

describe("sendChatMessage", () => {
  it("concatenates token events and returns the done event's sources", async () => {
    const body =
      'event: token\ndata: {"text": "Employees "}\n\n' +
      'event: token\ndata: {"text": "get 20 days."}\n\n' +
      'event: done\ndata: {"sources": [{"document_id": "doc-1", "filename": "policy.md", "chunk_preview": "..."}], "message_id": "m1", "conversation_id": "c1"}\n\n';
    const fetchMock = vi.fn().mockResolvedValue(sseResponse(body));
    vi.stubGlobal("fetch", fetchMock);

    const result = await sendChatMessage("How many vacation days?");

    expect(result.answer).toBe("Employees get 20 days.");
    expect(result.sources).toEqual([
      { document_id: "doc-1", filename: "policy.md", chunk_preview: "..." },
    ]);
    expect(result.conversationId).toBe("c1");
    expect(result.messageId).toBe("m1");
  });

  it("sends the message and optional conversationId as the POST body", async () => {
    const body = 'event: done\ndata: {"sources": [], "message_id": "m1", "conversation_id": "c1"}\n\n';
    const fetchMock = vi.fn().mockResolvedValue(sseResponse(body));
    vi.stubGlobal("fetch", fetchMock);

    await sendChatMessage("hello", "existing-conversation");

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/chat");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body)).toEqual({
      message: "hello",
      conversation_id: "existing-conversation",
    });
  });

  it("throws with the error event's message on a mid-stream failure", async () => {
    const body = 'event: token\ndata: {"text": "Emplo"}\n\nevent: error\ndata: {"message": "upstream LLM timed out"}\n\n';
    const fetchMock = vi.fn().mockResolvedValue(sseResponse(body));
    vi.stubGlobal("fetch", fetchMock);

    await expect(sendChatMessage("hi")).rejects.toThrow("upstream LLM timed out");
  });

  it("throws when the HTTP request itself fails", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("Not Found", { status: 404 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(sendChatMessage("hi")).rejects.toThrow("404");
  });

  it("throws a friendly error when the server is unreachable", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(sendChatMessage("hi")).rejects.toThrow(
      "Couldn't reach the server. Check your connection and try again.",
    );
  });

  it("invokes onToken for each token event as it streams in, before done resolves", async () => {
    const body =
      'event: token\ndata: {"text": "Employees "}\n\n' +
      'event: token\ndata: {"text": "get 20 days."}\n\n' +
      'event: done\ndata: {"sources": [], "message_id": "m1", "conversation_id": "c1"}\n\n';
    const fetchMock = vi.fn().mockResolvedValue(sseResponse(body));
    vi.stubGlobal("fetch", fetchMock);

    const chunks: string[] = [];
    const result = await sendChatMessage("How many vacation days?", undefined, (text) => chunks.push(text));

    expect(chunks).toEqual(["Employees ", "get 20 days."]);
    expect(result.answer).toBe("Employees get 20 days.");
  });

  it("throws a friendly error if the connection drops mid-stream", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('event: token\ndata: {"text": "Hel"}\n\n'));
      },
      pull() {
        return Promise.reject(new TypeError("network error"));
      },
    });
    const fetchMock = vi.fn().mockResolvedValue(new Response(stream));
    vi.stubGlobal("fetch", fetchMock);

    await expect(sendChatMessage("hi")).rejects.toThrow(
      "Couldn't reach the server. Check your connection and try again.",
    );
  });
});

describe("listConversations", () => {
  it("returns the parsed conversation list from GET /conversations", async () => {
    const body = [
      { id: "c1", title: "Vacation policy", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-02T00:00:00Z" },
      { id: "c2", title: "New chat", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
    ];
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await listConversations();

    expect(result).toEqual([
      { id: "c1", title: "Vacation policy" },
      { id: "c2", title: "New chat" },
    ]);
    expect(fetchMock.mock.calls[0][0]).toContain("/conversations");
  });

  it("throws when the request fails", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("error", { status: 500 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listConversations()).rejects.toThrow("500");
  });

  it("throws a friendly error when the server is unreachable", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listConversations()).rejects.toThrow(
      "Couldn't reach the server. Check your connection and try again.",
    );
  });
});

describe("createConversation", () => {
  it("POSTs to /conversations and returns the created conversation", async () => {
    const body = { id: "c3", title: "New chat", created_at: "2026-01-03T00:00:00Z", updated_at: "2026-01-03T00:00:00Z" };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await createConversation();

    expect(result).toEqual({ id: "c3", title: "New chat" });
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/conversations");
    expect(options.method).toBe("POST");
  });
});

describe("renameConversation", () => {
  it("PATCHes /conversations/{id} with new title and returns updated conversation", async () => {
    const body = { id: "c1", title: "New Title" };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await renameConversation("c1", "New Title");

    expect(result).toEqual({ id: "c1", title: "New Title" });
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/conversations/c1");
    expect(options.method).toBe("PATCH");
    expect(JSON.parse(options.body)).toEqual({ title: "New Title" });
  });

  it("throws when rename fails", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("error", { status: 404 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(renameConversation("c-missing", "Title")).rejects.toThrow("404");
  });
});

describe("deleteConversation", () => {
  it("DELETEs /conversations/{id}", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await deleteConversation("c1");

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/conversations/c1");
    expect(options.method).toBe("DELETE");
  });

  it("throws when delete fails", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("error", { status: 404 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(deleteConversation("c-missing")).rejects.toThrow("404");
  });
});

describe("getConversationMessages", () => {
  it("returns the parsed message history from GET /conversations/{id}/messages", async () => {
    const body = [
      { id: "m1", role: "user", content: "What is the vacation policy?", sources: null, created_at: "2026-01-01T00:00:00Z" },
      {
        id: "m2",
        role: "assistant",
        content: "20 days per year.",
        sources: [{ document_id: "doc-1", filename: "policy.md", chunk_preview: "..." }],
        created_at: "2026-01-01T00:00:01Z",
      },
    ];
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await getConversationMessages("c1");

    expect(result).toEqual([
      { id: "m1", role: "user", content: "What is the vacation policy?", sources: [] },
      {
        id: "m2",
        role: "assistant",
        content: "20 days per year.",
        sources: [{ document_id: "doc-1", filename: "policy.md", chunk_preview: "..." }],
      },
    ]);
    expect(fetchMock.mock.calls[0][0]).toContain("/conversations/c1/messages");
  });

  it("throws a 404 when the conversation doesn't exist", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("not found", { status: 404 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getConversationMessages("missing")).rejects.toThrow("404");
  });
});

describe("listDocuments", () => {
  it("returns the parsed document list from GET /documents", async () => {
    const body = [
      {
        id: "d1",
        filename: "policy.md",
        status: "ready",
        chunk_count: 3,
        error_message: null,
        created_at: "2026-01-01T00:00:00Z",
      },
      {
        id: "d2",
        filename: "handbook.pdf",
        status: "failed",
        chunk_count: null,
        error_message: "unsupported format",
        created_at: "2026-01-02T00:00:00Z",
      },
    ];
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await listDocuments();

    expect(result).toEqual([
      {
        id: "d1",
        filename: "policy.md",
        status: "ready",
        chunkCount: 3,
        errorMessage: null,
        createdAt: "2026-01-01T00:00:00Z",
      },
      {
        id: "d2",
        filename: "handbook.pdf",
        status: "failed",
        chunkCount: null,
        errorMessage: "unsupported format",
        createdAt: "2026-01-02T00:00:00Z",
      },
    ]);
    expect(fetchMock.mock.calls[0][0]).toContain("/documents");
  });

  it("throws a friendly error when the server is unreachable", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listDocuments()).rejects.toThrow(
      "Couldn't reach the server. Check your connection and try again.",
    );
  });
});

describe("uploadDocument", () => {
  it("POSTs the file as multipart form data and returns the created document", async () => {
    const body = { id: "d3", filename: "handbook.pdf", status: "processing" };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 202 }));
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["contents"], "handbook.pdf", { type: "application/pdf" });

    const result = await uploadDocument(file);

    expect(result).toEqual({ id: "d3", filename: "handbook.pdf", status: "processing" });
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/documents");
    expect(options.method).toBe("POST");
    expect(options.body).toBeInstanceOf(FormData);
    expect((options.body as FormData).get("file")).toBe(file);
  });

  it("throws the backend's detail message when the upload is rejected", async () => {
    const body = JSON.stringify({ detail: "Unsupported file type '.exe'. Supported: PDF, DOCX, PPTX, MD." });
    const fetchMock = vi.fn().mockResolvedValue(new Response(body, { status: 400 }));
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["contents"], "virus.exe", { type: "application/octet-stream" });

    await expect(uploadDocument(file)).rejects.toThrow("Unsupported file type");
  });

  it("falls back to a generic message when the error response has no detail", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("too big", { status: 413 }));
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["contents"], "big.pdf", { type: "application/pdf" });

    await expect(uploadDocument(file)).rejects.toThrow("413");
  });
});

describe("deleteDocument", () => {
  it("DELETEs /documents/{id}", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await deleteDocument("d1");

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/documents/d1");
    expect(options.method).toBe("DELETE");
  });

  it("throws a 404 when the document doesn't exist", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("not found", { status: 404 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(deleteDocument("missing")).rejects.toThrow("404");
  });
});

describe("authenticated requests", () => {
  it("attaches the stored token as a Bearer header", async () => {
    setToken("my-token");
    const fetchMock = vi.fn().mockResolvedValue(new Response("[]", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await listConversations();

    const [, options] = fetchMock.mock.calls[0];
    const headers = new Headers(options.headers);
    expect(headers.get("Authorization")).toBe("Bearer my-token");
  });

  it("sends no Authorization header when there is no stored token", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("[]", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await listConversations();

    const [, options] = fetchMock.mock.calls[0];
    const headers = new Headers(options.headers);
    expect(headers.has("Authorization")).toBe(false);
  });

  it("clears the token when an authenticated request comes back 401", async () => {
    setToken("stale-token");
    const fetchMock = vi.fn().mockResolvedValue(new Response("unauthorized", { status: 401 }));
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("window", { location: { href: "" } });

    await expect(listConversations()).rejects.toThrow();

    expect(getToken()).toBeNull();
  });

  it("does not touch the token when a request without one gets a 401", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("unauthorized", { status: 401 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listConversations()).rejects.toThrow();

    expect(getToken()).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("registerAccount", () => {
  it("POSTs to /auth/register and returns the success message", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ message: "Registration pending approval" }), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await registerAccount("Acme Corp", "new@example.com", "password123", "Jane Doe");

    expect(result).toEqual({ message: "Registration pending approval" });
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/auth/register");
    expect(JSON.parse(options.body)).toEqual({
      company_name: "Acme Corp",
      email: "new@example.com",
      password: "password123",
      display_name: "Jane Doe",
    });
  });

  it("throws a friendly message when the email is already registered", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Email already registered" }), { status: 409 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(registerAccount("Acme Corp", "dup@example.com", "password123", "Jane")).rejects.toThrow(
      "Email already registered",
    );
  });

  it("throws a friendly message when the company name is already taken", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Company name already taken" }), { status: 409 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(registerAccount("Existing Corp", "new@example.com", "password123", "Jane")).rejects.toThrow(
      "Company name already taken",
    );
  });
});

describe("loginAccount", () => {
  it("POSTs to /auth/login and returns the access token", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ access_token: "existing-token", token_type: "bearer" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await loginAccount("user@example.com", "password123");

    expect(result).toEqual({ accessToken: "existing-token" });
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/auth/login");
    expect(JSON.parse(options.body)).toEqual({ email: "user@example.com", password: "password123" });
  });

  it("throws a friendly message on invalid credentials", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Invalid email or password" }), { status: 401 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(loginAccount("user@example.com", "wrong")).rejects.toThrow("Invalid email or password");
  });

  it("throws specific backend error detail on 403 pending approval", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Your account is pending approval" }), { status: 403 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(loginAccount("user@example.com", "password123")).rejects.toThrow(
      "Your account is pending approval",
    );
  });

  it("throws specific backend error detail on 403 company suspended", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Your company has been suspended" }), { status: 403 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(loginAccount("user@example.com", "password123")).rejects.toThrow(
      "Your company has been suspended",
    );
  });
});

describe("getMe", () => {
  it("GETs /auth/me and camelCases the profile", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          email: "a@b.com",
          display_name: "Ada",
          role: "admin",
          approval_status: "approved",
          company_id: "c1",
          company_name: "Acme",
          department_id: "d1",
          department_name: "Engineering",
        }),
        { status: 200 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const me = await getMe();

    expect(me).toEqual({
      email: "a@b.com",
      displayName: "Ada",
      role: "admin",
      approvalStatus: "approved",
      companyId: "c1",
      companyName: "Acme",
      departmentId: "d1",
      departmentName: "Engineering",
    });
    expect(fetchMock.mock.calls[0][0]).toContain("/auth/me");
  });

  it("throws when the profile can't be loaded", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("boom", { status: 500 })));

    await expect(getMe()).rejects.toThrow("Failed to load profile: 500");
  });
});

describe("getStats", () => {
  it("GETs /stats and camelCases the payload", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          messages_per_day: [{ date: "2026-08-01", count: 3 }],
          document_count: 7,
          estimated_cost_usd: 0.42,
          documents_per_user: [{ email: "a@b.com", count: 4 }],
          cost_per_day: [{ date: "2026-08-01", cost_usd: 0.12 }],
        }),
        { status: 200 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const stats = await getStats();

    expect(stats).toEqual({
      messagesPerDay: [{ date: "2026-08-01", count: 3 }],
      documentCount: 7,
      estimatedCostUsd: 0.42,
      documentsPerUser: [{ email: "a@b.com", count: 4 }],
      costPerDay: [{ date: "2026-08-01", costUsd: 0.12 }],
    });
    expect(fetchMock.mock.calls[0][0]).toContain("/stats");
  });

  it("throws a friendly message when the user isn't an admin", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("forbidden", { status: 403 })));

    await expect(getStats()).rejects.toThrow("Admin access required.");
  });
});

describe("listPendingUsers", () => {
  it("GETs /superadmin/users?approval_status=pending and maps users", async () => {
    const mockData = [
      {
        id: "u1",
        email: "alice@acme.com",
        display_name: "Alice Admin",
        role: "admin",
        approval_status: "pending",
        company_id: "c1",
        company_name: "Acme Corp",
        department_id: null,
        created_at: "2026-08-24T00:00:00Z",
      },
    ];
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(mockData), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const users = await listPendingUsers();

    expect(users).toEqual([
      {
        id: "u1",
        email: "alice@acme.com",
        displayName: "Alice Admin",
        role: "admin",
        approvalStatus: "pending",
        companyId: "c1",
        companyName: "Acme Corp",
        departmentId: null,
        createdAt: "2026-08-24T00:00:00Z",
      },
    ]);
    expect(fetchMock.mock.calls[0][0]).toContain("/superadmin/users?approval_status=pending");
  });

  it("throws on error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("Forbidden", { status: 403 })));
    await expect(listPendingUsers()).rejects.toThrow("Failed to load pending users: 403");
  });
});

describe("approveUser", () => {
  it("PATCHes /superadmin/users/{id}/approve and returns approved user", async () => {
    const mockUser = {
      id: "u1",
      email: "alice@acme.com",
      display_name: "Alice",
      role: "admin",
      approval_status: "approved",
      company_id: "c1",
      company_name: "Acme Corp",
      department_id: null,
      created_at: "2026-08-24T00:00:00Z",
    };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(mockUser), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await approveUser("u1");

    expect(result.approvalStatus).toBe("approved");
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/superadmin/users/u1/approve");
    expect(options.method).toBe("PATCH");
  });

  it("throws when approval fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "User not found" }), { status: 404 })),
    );
    await expect(approveUser("u1")).rejects.toThrow("User not found");
  });
});

describe("rejectUser", () => {
  it("PATCHes /superadmin/users/{id}/reject and returns rejected user", async () => {
    const mockUser = {
      id: "u1",
      email: "alice@acme.com",
      display_name: "Alice",
      role: "admin",
      approval_status: "rejected",
      company_id: "c1",
      company_name: "Acme Corp",
      department_id: null,
      created_at: "2026-08-24T00:00:00Z",
    };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(mockUser), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await rejectUser("u1");

    expect(result.approvalStatus).toBe("rejected");
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/superadmin/users/u1/reject");
    expect(options.method).toBe("PATCH");
  });
});

describe("listCompanies", () => {
  it("GETs /superadmin/companies and maps companies", async () => {
    const mockData = [
      {
        id: "c1",
        name: "Acme Corp",
        status: "active",
        created_at: "2026-08-24T00:00:00Z",
        updated_at: "2026-08-24T00:00:00Z",
      },
    ];
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(mockData), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const companies = await listCompanies();

    expect(companies).toEqual([
      {
        id: "c1",
        name: "Acme Corp",
        status: "active",
        createdAt: "2026-08-24T00:00:00Z",
        updatedAt: "2026-08-24T00:00:00Z",
      },
    ]);
    expect(fetchMock.mock.calls[0][0]).toContain("/superadmin/companies");
  });
});

describe("suspendCompany and activateCompany", () => {
  it("PATCHes /superadmin/companies/{id}/suspend", async () => {
    const mockCompany = {
      id: "c1",
      name: "Acme Corp",
      status: "suspended",
      created_at: "2026-08-24T00:00:00Z",
      updated_at: "2026-08-24T01:00:00Z",
    };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(mockCompany), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await suspendCompany("c1");

    expect(result.status).toBe("suspended");
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/superadmin/companies/c1/suspend");
    expect(options.method).toBe("PATCH");
  });

  it("PATCHes /superadmin/companies/{id}/activate", async () => {
    const mockCompany = {
      id: "c1",
      name: "Acme Corp",
      status: "active",
      created_at: "2026-08-24T00:00:00Z",
      updated_at: "2026-08-24T01:00:00Z",
    };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(mockCompany), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await activateCompany("c1");

    expect(result.status).toBe("active");
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/superadmin/companies/c1/activate");
    expect(options.method).toBe("PATCH");
  });
});

describe("listTeamUsers", () => {
  it("GETs /users and maps team members", async () => {
    const mockData = [
      {
        id: "u1",
        email: "bob@acme.com",
        display_name: "Bob Dev",
        role: "member",
        approval_status: "approved",
        company_id: "c1",
        department_id: "d1",
        department_name: "Engineering",
        created_at: "2026-08-24T00:00:00Z",
      },
    ];
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(mockData), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const users = await listTeamUsers();

    expect(users).toEqual([
      {
        id: "u1",
        email: "bob@acme.com",
        displayName: "Bob Dev",
        role: "member",
        approvalStatus: "approved",
        companyId: "c1",
        departmentId: "d1",
        departmentName: "Engineering",
        createdAt: "2026-08-24T00:00:00Z",
      },
    ]);
    expect(fetchMock.mock.calls[0][0]).toContain("/users");
  });
});

describe("createUser", () => {
  it("POSTs to /users with correct body and returns created member", async () => {
    const mockUser = {
      id: "u2",
      email: "charlie@acme.com",
      display_name: "Charlie",
      role: "member",
      approval_status: "approved",
      company_id: "c1",
      department_id: "d1",
      department_name: "Engineering",
      created_at: "2026-08-24T00:00:00Z",
    };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(mockUser), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await createUser({
      email: "charlie@acme.com",
      password: "password123",
      displayName: "Charlie",
      departmentId: "d1",
    });

    expect(result.email).toBe("charlie@acme.com");
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/users");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body)).toEqual({
      email: "charlie@acme.com",
      password: "password123",
      display_name: "Charlie",
      department_id: "d1",
      role: "member",
    });
  });
});

describe("updateUser", () => {
  it("PATCHes /users/{id} with payload", async () => {
    const mockUser = {
      id: "u2",
      email: "charlie@acme.com",
      display_name: "Charlie Senior",
      role: "admin",
      approval_status: "approved",
      company_id: "c1",
      department_id: "d2",
      department_name: "Product",
      created_at: "2026-08-24T00:00:00Z",
    };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(mockUser), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await updateUser("u2", {
      displayName: "Charlie Senior",
      departmentId: "d2",
      role: "admin",
    });

    expect(result.displayName).toBe("Charlie Senior");
    expect(result.role).toBe("admin");
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/users/u2");
    expect(options.method).toBe("PATCH");
  });
});

describe("deleteUser", () => {
  it("DELETEs /users/{id}", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await deleteUser("u2");

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/users/u2");
    expect(options.method).toBe("DELETE");
  });
});

describe("listDepartments", () => {
  it("GETs /departments and maps departments", async () => {
    const mockData = [
      {
        id: "d1",
        name: "Engineering",
        company_id: "c1",
        created_at: "2026-08-24T00:00:00Z",
      },
    ];
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(mockData), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const depts = await listDepartments();

    expect(depts).toEqual([
      {
        id: "d1",
        name: "Engineering",
        companyId: "c1",
        createdAt: "2026-08-24T00:00:00Z",
      },
    ]);
    expect(fetchMock.mock.calls[0][0]).toContain("/departments");
  });
});

describe("createDepartment", () => {
  it("POSTs to /departments with name", async () => {
    const mockDept = {
      id: "d2",
      name: "Marketing",
      company_id: "c1",
      created_at: "2026-08-24T00:00:00Z",
    };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(mockDept), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await createDepartment("Marketing");

    expect(result).toEqual({
      id: "d2",
      name: "Marketing",
      companyId: "c1",
      createdAt: "2026-08-24T00:00:00Z",
    });
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/departments");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body)).toEqual({ name: "Marketing" });
  });
});

describe("deleteDepartment", () => {
  it("DELETEs /departments/{id}", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await deleteDepartment("d1");

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/departments/d1");
    expect(options.method).toBe("DELETE");
  });
});
