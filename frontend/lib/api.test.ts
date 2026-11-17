import { afterEach, describe, expect, it, vi } from "vitest";
import {
  acceptInvite,
  approveUser,
  createCompany,
  createConversation,
  createDepartment,
  createInvite,
  deleteConversation,
  deleteDepartment,
  deleteDocument,
  deleteInstanceUser,
  fetchProtectedFile,
  getConversationMessages,
  getInvitePreview,
  getMe,
  getStats,
  listConversations,
  listDepartments,
  listDocuments,
  listInstanceCompanies,
  listInstanceUsers,
  listMembers,
  loginAccount,
  registerAccount,
  removeMember,
  renameConversation,
  roleAtLeast,
  sendChatMessage,
  setCompanyStatus,
  transferOwnership,
  updateMember,
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

    const result = await sendChatMessage("acme", "How many vacation days?");

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

    await sendChatMessage("acme", "hello", "existing-conversation");

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/companies/acme/chat");
    expect(options.method).toBe("POST");
    expect(options.body.get("message")).toBe("hello");
    expect(options.body.get("conversation_id")).toBe("existing-conversation");
  });

  it("sends attachments as multipart files and reports status events", async () => {
    const body =
      'event: status\ndata: {"text": "Reading report.pdf\u2026"}\n\n' +
      'event: done\ndata: {"sources": [], "message_id": "m1", "conversation_id": "c1"}\n\n';
    const fetchMock = vi.fn().mockResolvedValue(sseResponse(body));
    vi.stubGlobal("fetch", fetchMock);
    const statuses: string[] = [];
    const file = new File(["%PDF"], "report.pdf", { type: "application/pdf" });

    await sendChatMessage("acme", "", undefined, undefined, [file], (text) => statuses.push(text));

    const form = fetchMock.mock.calls[0][1].body as FormData;
    expect((form.getAll("files")[0] as File).name).toBe("report.pdf");
    expect(statuses).toEqual(["Reading report.pdf\u2026"]);
  });

  it("surfaces the server's validation message", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ detail: "Attach at most 5 files per message." }), { status: 400 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(sendChatMessage("acme", "hi")).rejects.toThrow("Attach at most 5 files per message.");
  });

  it("throws with the error event's message on a mid-stream failure", async () => {
    const body = 'event: token\ndata: {"text": "Emplo"}\n\nevent: error\ndata: {"message": "upstream LLM timed out"}\n\n';
    const fetchMock = vi.fn().mockResolvedValue(sseResponse(body));
    vi.stubGlobal("fetch", fetchMock);

    await expect(sendChatMessage("acme", "hi")).rejects.toThrow("upstream LLM timed out");
  });

  it("throws when the HTTP request itself fails", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("Not Found", { status: 404 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(sendChatMessage("acme", "hi")).rejects.toThrow("404");
  });

  it("throws a friendly error when the server is unreachable", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(sendChatMessage("acme", "hi")).rejects.toThrow(
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
    const result = await sendChatMessage("acme", "How many vacation days?", undefined, (text) => chunks.push(text));

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

    await expect(sendChatMessage("acme", "hi")).rejects.toThrow(
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

    const result = await listConversations("acme");

    expect(result).toEqual([
      { id: "c1", title: "Vacation policy" },
      { id: "c2", title: "New chat" },
    ]);
    expect(fetchMock.mock.calls[0][0]).toContain("/companies/acme/conversations");
  });

  it("throws when the request fails", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("error", { status: 500 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listConversations("acme")).rejects.toThrow("500");
  });

  it("throws a friendly error when the server is unreachable", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listConversations("acme")).rejects.toThrow(
      "Couldn't reach the server. Check your connection and try again.",
    );
  });
});

describe("createConversation", () => {
  it("POSTs to /conversations and returns the created conversation", async () => {
    const body = { id: "c3", title: "New chat", created_at: "2026-01-03T00:00:00Z", updated_at: "2026-01-03T00:00:00Z" };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await createConversation("acme");

    expect(result).toEqual({ id: "c3", title: "New chat" });
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/companies/acme/conversations");
    expect(options.method).toBe("POST");
  });
});

describe("renameConversation", () => {
  it("PATCHes /conversations/{id} with new title and returns updated conversation", async () => {
    const body = { id: "c1", title: "New Title" };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await renameConversation("acme", "c1", "New Title");

    expect(result).toEqual({ id: "c1", title: "New Title" });
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/companies/acme/conversations/c1");
    expect(options.method).toBe("PATCH");
    expect(JSON.parse(options.body)).toEqual({ title: "New Title" });
  });

  it("throws when rename fails", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("error", { status: 404 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(renameConversation("acme", "c-missing", "Title")).rejects.toThrow("404");
  });
});

describe("deleteConversation", () => {
  it("DELETEs /conversations/{id}", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await deleteConversation("acme", "c1");

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/companies/acme/conversations/c1");
    expect(options.method).toBe("DELETE");
  });

  it("throws when delete fails", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("error", { status: 404 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(deleteConversation("acme", "c-missing")).rejects.toThrow("404");
  });
});

describe("getConversationMessages", () => {
  it("returns the parsed message history from GET /conversations/{id}/messages", async () => {
    const body = [
      {
        id: "m1",
        role: "user",
        content: "What is the vacation policy?",
        sources: null,
        attachments: [{ filename: "a.png", mime: "image/png", size: 3, truncated: false }],
        created_at: "2026-01-01T00:00:00Z",
      },
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

    const result = await getConversationMessages("acme", "c1");

    expect(result).toEqual([
      {
        id: "m1",
        role: "user",
        content: "What is the vacation policy?",
        sources: [],
        attachments: [{ filename: "a.png", mime: "image/png", size: 3, truncated: false }],
      },
      {
        id: "m2",
        role: "assistant",
        content: "20 days per year.",
        sources: [{ document_id: "doc-1", filename: "policy.md", chunk_preview: "..." }],
        attachments: [],
      },
    ]);
    expect(fetchMock.mock.calls[0][0]).toContain("/companies/acme/conversations/c1/messages");
  });

  it("throws a 404 when the conversation doesn't exist", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("not found", { status: 404 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getConversationMessages("acme", "missing")).rejects.toThrow("404");
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

    const result = await listDocuments("acme");

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
    expect(fetchMock.mock.calls[0][0]).toContain("/companies/acme/documents");
  });

  it("throws a friendly error when the server is unreachable", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listDocuments("acme")).rejects.toThrow(
      "Couldn't reach the server. Check your connection and try again.",
    );
  });
});

describe("uploadDocument", () => {
  // Minimal XHR fake: replies with `status`/`responseText` on send, after one progress event.
  function stubXhr(status: number, responseText: string) {
    const sent: { method?: string; url?: string; body?: unknown } = {};
    class FakeXhr {
      status = 0;
      responseText = "";
      upload: { onprogress?: (e: { lengthComputable: boolean; loaded: number; total: number }) => void } = {};
      onload?: () => void;
      onerror?: () => void;
      open(method: string, url: string) {
        sent.method = method;
        sent.url = url;
      }
      setRequestHeader() {}
      send(body: unknown) {
        sent.body = body;
        this.upload.onprogress?.({ lengthComputable: true, loaded: 1, total: 2 });
        this.status = status;
        this.responseText = responseText;
        this.onload?.();
      }
    }
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
    return sent;
  }

  it("POSTs the file as multipart form data, reports progress, and returns the created document", async () => {
    const body = { id: "d3", filename: "handbook.pdf", status: "processing" };
    const sent = stubXhr(202, JSON.stringify(body));
    const file = new File(["contents"], "handbook.pdf", { type: "application/pdf" });
    const onProgress = vi.fn();

    const result = await uploadDocument("acme", file, { onProgress });

    expect(result).toEqual(body);
    expect(onProgress).toHaveBeenCalledWith(0.5);
    expect(sent.url).toContain("/companies/acme/documents");
    expect(sent.method).toBe("POST");
    expect(sent.body).toBeInstanceOf(FormData);
    expect((sent.body as FormData).get("file")).toBe(file);
  });

  it("throws the backend's detail message when the upload is rejected", async () => {
    stubXhr(400, JSON.stringify({ detail: "Unsupported file type '.exe'. Supported: PDF, DOCX, PPTX, MD." }));
    const file = new File(["contents"], "virus.exe", { type: "application/octet-stream" });

    await expect(uploadDocument("acme", file)).rejects.toThrow("Unsupported file type");
  });

  it("falls back to a generic message when the error response has no detail", async () => {
    stubXhr(413, "too big");
    const file = new File(["contents"], "big.pdf", { type: "application/pdf" });

    await expect(uploadDocument("acme", file)).rejects.toThrow("413");
  });
});

describe("deleteDocument", () => {
  it("DELETEs /documents/{id}", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await deleteDocument("acme", "d1");

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/companies/acme/documents/d1");
    expect(options.method).toBe("DELETE");
  });

  it("throws a 404 when the document doesn't exist", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("not found", { status: 404 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(deleteDocument("acme", "missing")).rejects.toThrow("404");
  });
});

describe("authenticated requests", () => {
  it("attaches the stored token as a Bearer header", async () => {
    setToken("my-token");
    const fetchMock = vi.fn().mockResolvedValue(new Response("[]", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await listConversations("acme");

    const [, options] = fetchMock.mock.calls[0];
    const headers = new Headers(options.headers);
    expect(headers.get("Authorization")).toBe("Bearer my-token");
  });

  it("sends no Authorization header when there is no stored token", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("[]", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await listConversations("acme");

    const [, options] = fetchMock.mock.calls[0];
    const headers = new Headers(options.headers);
    expect(headers.has("Authorization")).toBe(false);
  });

  it("clears the token when an authenticated request comes back 401", async () => {
    setToken("stale-token");
    const fetchMock = vi.fn().mockResolvedValue(new Response("unauthorized", { status: 401 }));
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("window", { location: { href: "" } });

    await expect(listConversations("acme")).rejects.toThrow();

    expect(getToken()).toBeNull();
  });

  it("does not touch the token when a request without one gets a 401", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("unauthorized", { status: 401 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listConversations("acme")).rejects.toThrow();

    expect(getToken()).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function stubFetch(...responses: Response[]) {
  const fetchMock = vi.fn();
  for (const r of responses) fetchMock.mockResolvedValueOnce(r);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function sentJson(fetchMock: ReturnType<typeof vi.fn>, call = 0): unknown {
  return JSON.parse(fetchMock.mock.calls[call][1].body as string);
}

describe("company-scoped requests", () => {
  it("put the slug from the caller into every company path", async () => {
    const stats = { messages_per_day: [], document_count: 0, estimated_cost_usd: 0, documents_per_user: [], cost_per_day: [] };
    const fetchMock = stubFetch(json([]), json([]), json(stats));
    await listMembers("acme");
    await listDepartments("other-co");
    await getStats("acme");
    expect(fetchMock.mock.calls.map((c) => c[0])).toEqual([
      "http://localhost:8000/companies/acme/members",
      "http://localhost:8000/companies/other-co/departments",
      "http://localhost:8000/companies/acme/stats",
    ]);
  });

  it("resolves protected document paths inside the company", async () => {
    vi.stubGlobal("URL", { ...URL, createObjectURL: () => "blob:x" });
    const fetchMock = stubFetch(new Response("img"));
    await fetchProtectedFile("acme", "/documents/d1/images/0");
    expect(fetchMock.mock.calls[0][0]).toBe("http://localhost:8000/companies/acme/documents/d1/images/0");
  });

  it("surfaces the backend's limit message", async () => {
    stubFetch(json({ detail: "Document limit reached: this instance allows 5 documents per company." }, 403));
    await expect(createDepartment("acme", "Ops")).rejects.toThrow("Document limit reached");
  });

  it("falls back to a status message when there is no detail", async () => {
    stubFetch(json({}, 500));
    await expect(deleteDepartment("acme", "d1")).rejects.toThrow("Failed to delete department: 500");
  });
});

describe("registerAccount", () => {
  it("POSTs account fields only, plus an invite token when given", async () => {
    const fetchMock = stubFetch(json({ message: "Account created", approval_status: "approved", company_slug: "acme" }, 201));
    const result = await registerAccount("new@example.com", "password123", "Jane", "tok");
    expect(fetchMock.mock.calls[0][0]).toContain("/auth/register");
    expect(sentJson(fetchMock)).toEqual({
      email: "new@example.com",
      password: "password123",
      display_name: "Jane",
      invite_token: "tok",
    });
    expect(result).toEqual({ message: "Account created", approvalStatus: "approved", companySlug: "acme" });
  });

  it("reports a pending account in approval mode", async () => {
    stubFetch(json({ message: "Registration pending approval", approval_status: "pending", company_slug: null }, 201));
    expect((await registerAccount("a@b.co", "password123", "A")).approvalStatus).toBe("pending");
  });

  it("explains closed signup", async () => {
    stubFetch(json({ detail: "Signup is closed. Ask a company admin for an invite link." }, 403));
    await expect(registerAccount("a@b.co", "password123", "A")).rejects.toThrow("Signup is closed");
  });

  it("throws a friendly message when the email is taken", async () => {
    stubFetch(json({ detail: "Email already registered" }, 409));
    await expect(registerAccount("a@b.co", "password123", "A")).rejects.toThrow("Email already registered");
  });
});

describe("loginAccount", () => {
  it("POSTs credentials and returns the access token", async () => {
    const fetchMock = stubFetch(json({ access_token: "jwt", token_type: "bearer" }));
    expect(await loginAccount("u@example.com", "pw")).toEqual({ accessToken: "jwt" });
    expect(fetchMock.mock.calls[0][0]).toContain("/auth/login");
  });

  it("shows pending/rejected messages from the server", async () => {
    stubFetch(json({ detail: "Your account is pending approval" }, 403));
    await expect(loginAccount("u@example.com", "pw")).rejects.toThrow("Your account is pending approval");
  });

  it("falls back on invalid credentials", async () => {
    stubFetch(json({}, 401));
    await expect(loginAccount("u@example.com", "pw")).rejects.toThrow("Invalid email or password.");
  });
});

describe("getMe", () => {
  it("returns the account with its memberships", async () => {
    stubFetch(
      json({
        id: "u1",
        email: "jane@acme.com",
        display_name: "Jane",
        is_instance_admin: false,
        approval_status: "approved",
        companies: [
          { id: "c1", name: "Acme", slug: "acme", status: "active", role: "owner", department_id: null, department_name: null },
        ],
      }),
    );
    expect(await getMe()).toEqual({
      id: "u1",
      email: "jane@acme.com",
      displayName: "Jane",
      isInstanceAdmin: false,
      approvalStatus: "approved",
      companies: [{ id: "c1", name: "Acme", slug: "acme", status: "active", role: "owner", departmentId: null, departmentName: null }],
    });
  });
});

describe("roleAtLeast", () => {
  it("ranks owner > admin > member", () => {
    expect(roleAtLeast("owner", "admin")).toBe(true);
    expect(roleAtLeast("admin", "admin")).toBe(true);
    expect(roleAtLeast("member", "admin")).toBe(false);
    expect(roleAtLeast("admin", "owner")).toBe(false);
    expect(roleAtLeast(undefined, "member")).toBe(false);
  });
});

describe("companies", () => {
  it("creates a company at account level", async () => {
    const fetchMock = stubFetch(json({ id: "c2", name: "New Co", slug: "new-co", status: "active", role: "owner" }, 201));
    const company = await createCompany("New Co");
    expect(fetchMock.mock.calls[0][0]).toBe("http://localhost:8000/companies");
    expect(company.slug).toBe("new-co");
    expect(company.role).toBe("owner");
  });
});

describe("members", () => {
  const raw = {
    user_id: "u2",
    email: "bob@acme.com",
    display_name: "Bob",
    role: "member",
    department_id: null,
    department_name: null,
    joined_at: "2026-11-01T00:00:00Z",
  };

  it("lists members", async () => {
    stubFetch(json([raw]));
    expect(await listMembers("acme")).toEqual([
      { userId: "u2", email: "bob@acme.com", displayName: "Bob", role: "member", departmentId: null, departmentName: null, joinedAt: "2026-11-01T00:00:00Z" },
    ]);
  });

  it("sends only the fields that change, and null to clear a department", async () => {
    const fetchMock = stubFetch(json(raw), json(raw));
    await updateMember("acme", "u2", { role: "admin" });
    await updateMember("acme", "u2", { departmentId: null });
    expect(fetchMock.mock.calls[0][0]).toContain("/companies/acme/members/u2");
    expect(fetchMock.mock.calls[0][1].method).toBe("PATCH");
    expect(sentJson(fetchMock, 0)).toEqual({ role: "admin" });
    expect(sentJson(fetchMock, 1)).toEqual({ department_id: null });
  });

  it("removes a member (or leaves) with DELETE", async () => {
    const fetchMock = stubFetch(new Response(null, { status: 204 }));
    await removeMember("acme", "u2");
    expect(fetchMock.mock.calls[0][0]).toContain("/companies/acme/members/u2");
    expect(fetchMock.mock.calls[0][1].method).toBe("DELETE");
  });

  it("surfaces the owner-must-transfer refusal", async () => {
    stubFetch(json({ detail: "Transfer ownership before leaving the company" }, 409));
    await expect(removeMember("acme", "me")).rejects.toThrow("Transfer ownership before leaving the company");
  });

  it("transfers ownership", async () => {
    const fetchMock = stubFetch(json({ ...raw, role: "owner" }));
    expect((await transferOwnership("acme", "u2")).role).toBe("owner");
    expect(fetchMock.mock.calls[0][0]).toContain("/companies/acme/transfer-ownership");
    expect(sentJson(fetchMock)).toEqual({ user_id: "u2" });
  });
});

describe("invites", () => {
  it("creates an invite and returns its one-time token", async () => {
    const fetchMock = stubFetch(
      json(
        {
          id: "i1",
          email: "new@acme.com",
          role: "member",
          department_id: "d1",
          expires_at: "2026-11-24T00:00:00Z",
          created_at: "2026-11-17T00:00:00Z",
          token: "secret",
        },
        201,
      ),
    );
    const invite = await createInvite("acme", { email: "new@acme.com", role: "member", departmentId: "d1" });
    expect(fetchMock.mock.calls[0][0]).toContain("/companies/acme/invites");
    expect(sentJson(fetchMock)).toEqual({ email: "new@acme.com", role: "member", department_id: "d1" });
    expect(invite.token).toBe("secret");
    expect(invite.departmentId).toBe("d1");
  });

  it("previews and accepts an invite at account level", async () => {
    const fetchMock = stubFetch(
      json({ company_name: "Acme", email: "new@acme.com", role: "admin" }),
      json({ company_slug: "acme" }),
    );
    expect(await getInvitePreview("tok")).toEqual({ companyName: "Acme", email: "new@acme.com", role: "admin" });
    expect(await acceptInvite("tok")).toEqual({ companySlug: "acme" });
    expect(fetchMock.mock.calls[0][0]).toBe("http://localhost:8000/invites/tok");
    expect(fetchMock.mock.calls[1][0]).toBe("http://localhost:8000/invites/tok/accept");
    expect(fetchMock.mock.calls[1][1].method).toBe("POST");
  });

  it("shows why an invite can't be used", async () => {
    stubFetch(json({ detail: "This invite was sent to a different email address" }, 403));
    await expect(acceptInvite("tok")).rejects.toThrow("different email address");
  });
});

describe("instance administration", () => {
  it("lists users, optionally pending only", async () => {
    const fetchMock = stubFetch(json([]), json([]));
    await listInstanceUsers();
    await listInstanceUsers("pending");
    expect(fetchMock.mock.calls[0][0]).toBe("http://localhost:8000/instance/users");
    expect(fetchMock.mock.calls[1][0]).toBe("http://localhost:8000/instance/users?approval_status=pending");
  });

  it("approves and deletes users", async () => {
    const user = {
      id: "u1",
      email: "a@b.co",
      display_name: null,
      is_instance_admin: false,
      approval_status: "approved",
      companies: [{ name: "Acme", slug: "acme", role: "member" }],
      created_at: "2026-11-01T00:00:00Z",
    };
    const fetchMock = stubFetch(json(user), new Response(null, { status: 204 }));
    expect((await approveUser("u1")).approvalStatus).toBe("approved");
    await deleteInstanceUser("u1");
    expect(fetchMock.mock.calls[0][0]).toContain("/instance/users/u1/approve");
    expect(fetchMock.mock.calls[1][0]).toContain("/instance/users/u1");
    expect(fetchMock.mock.calls[1][1].method).toBe("DELETE");
  });

  it("lists companies and changes their status", async () => {
    const company = {
      id: "c1",
      name: "Acme",
      slug: "acme",
      status: "suspended",
      member_count: 3,
      created_at: "2026-11-01T00:00:00Z",
      updated_at: "2026-11-01T00:00:00Z",
    };
    const fetchMock = stubFetch(json([company]), json(company), json({ ...company, status: "active" }));
    expect((await listInstanceCompanies())[0].memberCount).toBe(3);
    await setCompanyStatus("c1", "suspended");
    expect((await setCompanyStatus("c1", "active")).status).toBe("active");
    expect(fetchMock.mock.calls[1][0]).toContain("/instance/companies/c1/suspend");
    expect(fetchMock.mock.calls[2][0]).toContain("/instance/companies/c1/activate");
  });
});
