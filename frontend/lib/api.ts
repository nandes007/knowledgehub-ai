import { clearToken, getToken } from "./auth";
import { parseSseStream } from "./sse";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Every company-scoped resource lives under its company's slug; callers pass the slug
// from the route, so two tabs can hold two companies at once.
function companyUrl(slug: string, path: string): string {
  return `${API_URL}/companies/${encodeURIComponent(slug)}${path}`;
}

// fetch() rejects (rather than resolving with a bad status) when the server is
// unreachable, e.g. it's down or the network drops. That raw rejection reads as a
// blank/broken UI, so surface it as a message a user can act on.
async function apiFetch(input: string, init?: RequestInit): Promise<Response> {
  const token = getToken();
  const headers = new Headers(init?.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(input, { ...init, headers });
  } catch {
    throw new Error("Couldn't reach the server. Check your connection and try again.");
  }

  // A 401 on a request that carried a token means the session itself is no
  // longer valid (expired/revoked) - not a login/register attempt failing,
  // those never carry a token in the first place.
  if (response.status === 401 && token) {
    clearToken();
    if (typeof window !== "undefined") window.location.href = "/login";
  }

  return response;
}

export type Source = {
  document_id: string;
  filename: string;
  chunk_preview: string;
};

export type ChatResult = {
  answer: string;
  sources: Source[];
  conversationId: string;
  messageId: string;
};

export async function sendChatMessage(
  slug: string,
  message: string,
  conversationId?: string,
  onToken?: (text: string) => void,
  files: File[] = [],
  onStatus?: (text: string) => void,
): Promise<ChatResult> {
  const body = new FormData();
  body.append("message", message);
  if (conversationId) body.append("conversation_id", conversationId);
  for (const file of files) body.append("files", file);
  const response = await apiFetch(companyUrl(slug, "/chat"), { method: "POST", body });

  if (!response.ok) {
    const detail = await response
      .json()
      .then((b: { detail?: unknown }) => (typeof b.detail === "string" ? b.detail : undefined))
      .catch(() => undefined);
    throw new Error(detail ?? `Chat request failed: ${response.status}`);
  }

  let answer = "";
  try {
    for await (const { event, data } of parseSseStream(response)) {
      if (event === "token") {
        const text = (JSON.parse(data) as { text: string }).text;
        answer += text;
        onToken?.(text);
      } else if (event === "status") {
        onStatus?.((JSON.parse(data) as { text: string }).text);
      } else if (event === "error") {
        throw new Error((JSON.parse(data) as { message: string }).message);
      } else if (event === "done") {
        const doneData = JSON.parse(data) as {
          sources: Source[];
          message_id: string;
          conversation_id: string;
        };
        return {
          answer,
          sources: doneData.sources,
          conversationId: doneData.conversation_id,
          messageId: doneData.message_id,
        };
      }
    }
  } catch (err) {
    // A dropped connection mid-stream surfaces as a TypeError from the reader, distinct
    // from the `error` SSE event above (a plain Error we threw ourselves with a message
    // already meant for display).
    if (err instanceof TypeError) {
      throw new Error("Couldn't reach the server. Check your connection and try again.");
    }
    throw err;
  }

  throw new Error("Chat stream ended without a done event");
}

export type Conversation = {
  id: string;
  title: string;
};

export async function listConversations(slug: string): Promise<Conversation[]> {
  const response = await apiFetch(companyUrl(slug, "/conversations"));
  if (!response.ok) {
    throw new Error(`Failed to load conversations: ${response.status}`);
  }
  const data = (await response.json()) as { id: string; title: string }[];
  return data.map(({ id, title }) => ({ id, title }));
}

export async function createConversation(slug: string): Promise<Conversation> {
  const response = await apiFetch(companyUrl(slug, "/conversations"), { method: "POST" });
  if (!response.ok) {
    throw new Error(`Failed to create conversation: ${response.status}`);
  }
  const { id, title } = (await response.json()) as { id: string; title: string };
  return { id, title };
}

export async function renameConversation(slug: string, conversationId: string, title: string): Promise<Conversation> {
  const response = await apiFetch(companyUrl(slug, `/conversations/${conversationId}`), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!response.ok) {
    throw new Error(`Failed to rename conversation: ${response.status}`);
  }
  const { id, title: updatedTitle } = (await response.json()) as { id: string; title: string };
  return { id, title: updatedTitle };
}

export async function deleteConversation(slug: string, conversationId: string): Promise<void> {
  const response = await apiFetch(companyUrl(slug, `/conversations/${conversationId}`), {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(`Failed to delete conversation: ${response.status}`);
  }
}

export type Attachment = {
  filename: string;
  mime: string;
  size: number;
  truncated: boolean;
};

export type ConversationMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: Source[];
  attachments: Attachment[];
};

export function attachmentPath(conversationId: string, messageId: string, index: number): string {
  return `/conversations/${conversationId}/messages/${messageId}/attachments/${index}`;
}

// Images and attachments sit behind auth, and a plain <img src> can't send the Bearer
// header, so they're fetched here and handed back as a blob URL (the caller revokes it).
export function isProtectedPath(src: string): boolean {
  return src.startsWith("/documents/") || src.startsWith("/conversations/");
}

export async function fetchProtectedFile(slug: string, path: string): Promise<string> {
  const response = await apiFetch(companyUrl(slug, path));
  if (!response.ok) throw new Error(`Couldn't load file: ${response.status}`);
  return URL.createObjectURL(await response.blob());
}

export async function getConversationMessages(slug: string, conversationId: string): Promise<ConversationMessage[]> {
  const response = await apiFetch(companyUrl(slug, `/conversations/${conversationId}/messages`));
  if (!response.ok) {
    throw new Error(`Failed to load conversation messages: ${response.status}`);
  }
  const data = (await response.json()) as {
    id: string;
    role: "user" | "assistant";
    content: string;
    sources: Source[] | null;
    attachments?: Attachment[] | null;
  }[];
  return data.map(({ id, role, content, sources, attachments }) => ({
    id,
    role,
    content,
    sources: sources ?? [],
    attachments: attachments ?? [],
  }));
}

export type DocumentStatus = "processing" | "ready" | "failed";

export type Visibility = "company" | "department";

export type Document = {
  id: string;
  filename: string;
  status: DocumentStatus;
  department: string | null;
  visibility: Visibility;
  chunkCount: number | null;
  progress: number;
  errorMessage: string | null;
  createdAt: string;
};

export async function listDocuments(slug: string): Promise<Document[]> {
  const response = await apiFetch(companyUrl(slug, "/documents"));
  if (!response.ok) {
    throw new Error(`Failed to load documents: ${response.status}`);
  }
  const data = (await response.json()) as {
    id: string;
    filename: string;
    status: DocumentStatus;
    department: string | null;
    visibility: Visibility;
    chunk_count: number | null;
    progress: number;
    error_message: string | null;
    created_at: string;
  }[];
  return data.map(({ id, filename, status, department, visibility, chunk_count, progress, error_message, created_at }) => ({
    id,
    filename,
    status,
    department,
    visibility,
    chunkCount: chunk_count,
    progress,
    errorMessage: error_message,
    createdAt: created_at,
  }));
}

export type DocumentPreview =
  | { kind: "markdown"; text: string }
  | { kind: "pdf"; url: string }
  | { kind: "image"; url: string };

// PDFs and images come back as the original file, rendered by the browser from a blob URL
// (the caller must revoke it); other formats come back as extracted markdown.
export async function getDocumentPreview(slug: string, documentId: string): Promise<DocumentPreview> {
  const response = await apiFetch(companyUrl(slug, `/documents/${documentId}/preview`));
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Couldn't load preview: ${response.status}`);
  }
  const type = response.headers.get("content-type") ?? "";
  if (type.startsWith("text/markdown")) return { kind: "markdown", text: await response.text() };
  const url = URL.createObjectURL(await response.blob());
  return type === "application/pdf" ? { kind: "pdf", url } : { kind: "image", url };
}

export type UploadedDocument = {
  id: string;
  filename: string;
  status: DocumentStatus;
};

// ponytail: XHR instead of apiFetch because fetch() can't report upload
// progress. Mirrors apiFetch's auth header, 401 redirect, and network error.
export function uploadDocument(
  slug: string,
  file: File,
  options?: { department?: string; visibility?: Visibility; onProgress?: (fraction: number) => void },
): Promise<UploadedDocument> {
  const formData = new FormData();
  formData.append("file", file);
  if (options?.department) formData.append("department", options.department);
  if (options?.visibility) formData.append("visibility", options.visibility);
  const token = getToken();

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", companyUrl(slug, "/documents"));
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) options?.onProgress?.(event.loaded / event.total);
    };
    xhr.onerror = () => reject(new Error("Couldn't reach the server. Check your connection and try again."));
    xhr.onload = () => {
      if (xhr.status === 401 && token) {
        clearToken();
        window.location.href = "/login";
      }
      let body: { detail?: string } | undefined;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        body = undefined;
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body as UploadedDocument);
      else reject(new Error(body?.detail ?? `Failed to upload document: ${xhr.status}`));
    };
    xhr.send(formData);
  });
}

export async function deleteDocument(slug: string, documentId: string): Promise<void> {
  const response = await apiFetch(companyUrl(slug, `/documents/${documentId}`), { method: "DELETE" });
  if (!response.ok) {
    throw new Error(`Failed to delete document: ${response.status}`);
  }
}

// Throws the backend's `detail` message (they're written for people) or the fallback.
async function ensureOk(response: Response, fallback: string): Promise<Response> {
  if (response.ok) return response;
  const body = (await response.json().catch(() => ({}))) as { detail?: unknown };
  throw new Error(typeof body.detail === "string" ? body.detail : `${fallback}: ${response.status}`);
}

function jsonInit(method: string, body?: unknown): RequestInit {
  return body === undefined
    ? { method }
    : { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

export type Role = "owner" | "admin" | "member";

const ROLE_RANK: Record<Role, number> = { member: 0, admin: 1, owner: 2 };

export function roleAtLeast(role: string | undefined, minimum: Role): boolean {
  return role !== undefined && role in ROLE_RANK && ROLE_RANK[role as Role] >= ROLE_RANK[minimum];
}

export type MyCompany = {
  id: string;
  name: string;
  slug: string;
  status: string;
  role: Role;
  departmentId: string | null;
  departmentName: string | null;
};

export type Me = {
  id: string;
  email: string;
  displayName: string | null;
  isInstanceAdmin: boolean;
  approvalStatus: string;
  companies: MyCompany[];
};

type RawMyCompany = {
  id: string;
  name: string;
  slug: string;
  status: string;
  role: Role;
  department_id?: string | null;
  department_name?: string | null;
};

function toMyCompany(c: RawMyCompany): MyCompany {
  return {
    id: c.id,
    name: c.name,
    slug: c.slug,
    status: c.status,
    role: c.role,
    departmentId: c.department_id ?? null,
    departmentName: c.department_name ?? null,
  };
}

export async function getMe(): Promise<Me> {
  const response = await ensureOk(await apiFetch(`${API_URL}/auth/me`), "Failed to load profile");
  const data = (await response.json()) as {
    id: string;
    email: string;
    display_name: string | null;
    is_instance_admin: boolean;
    approval_status: string;
    companies: RawMyCompany[];
  };
  return {
    id: data.id,
    email: data.email,
    displayName: data.display_name,
    isInstanceAdmin: data.is_instance_admin,
    approvalStatus: data.approval_status,
    companies: data.companies.map(toMyCompany),
  };
}

export type AuthResult = { accessToken: string };
export type RegisterResult = { message: string; approvalStatus: string; companySlug: string | null };

export async function registerAccount(
  email: string,
  password: string,
  displayName: string,
  inviteToken?: string,
): Promise<RegisterResult> {
  const response = await apiFetch(
    `${API_URL}/auth/register`,
    jsonInit("POST", { email, password, display_name: displayName, invite_token: inviteToken }),
  );
  if (response.status === 409) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? "An account with that email already exists.");
  }
  await ensureOk(response, "Registration failed");
  const data = (await response.json()) as { message: string; approval_status: string; company_slug: string | null };
  return { message: data.message, approvalStatus: data.approval_status, companySlug: data.company_slug };
}

export async function loginAccount(email: string, password: string): Promise<AuthResult> {
  const response = await apiFetch(`${API_URL}/auth/login`, jsonInit("POST", { email, password }));
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? "Invalid email or password.");
  }
  const { access_token } = (await response.json()) as { access_token: string };
  return { accessToken: access_token };
}

// ── Companies ──

export async function createCompany(name: string): Promise<MyCompany> {
  const response = await ensureOk(
    await apiFetch(`${API_URL}/companies`, jsonInit("POST", { name })),
    "Failed to create company",
  );
  return toMyCompany((await response.json()) as RawMyCompany);
}

export async function renameCompany(slug: string, name: string): Promise<MyCompany> {
  const response = await ensureOk(
    await apiFetch(companyUrl(slug, ""), jsonInit("PATCH", { name })),
    "Failed to rename company",
  );
  return toMyCompany((await response.json()) as RawMyCompany);
}

export async function deleteCompany(slug: string): Promise<void> {
  await ensureOk(await apiFetch(companyUrl(slug, ""), { method: "DELETE" }), "Failed to delete company");
}

// ── Stats ──

export type Stats = {
  messagesPerDay: { date: string; count: number }[];
  documentCount: number;
  estimatedCostUsd: number;
  documentsPerUser: { email: string; count: number }[];
  costPerDay: { date: string; costUsd: number }[];
};

function toStats(data: {
  messages_per_day: { date: string; count: number }[];
  document_count: number;
  estimated_cost_usd: number;
  documents_per_user: { email: string; count: number }[];
  cost_per_day: { date: string; cost_usd: number }[];
}): Stats {
  return {
    messagesPerDay: data.messages_per_day,
    documentCount: data.document_count,
    estimatedCostUsd: data.estimated_cost_usd,
    documentsPerUser: data.documents_per_user,
    costPerDay: data.cost_per_day.map(({ date, cost_usd }) => ({ date, costUsd: cost_usd })),
  };
}

export async function getStats(slug: string): Promise<Stats> {
  const response = await ensureOk(await apiFetch(companyUrl(slug, "/stats")), "Failed to load stats");
  return toStats(await response.json());
}

export async function getInstanceStats(): Promise<Stats> {
  const response = await ensureOk(await apiFetch(`${API_URL}/instance/stats`), "Failed to load stats");
  return toStats(await response.json());
}

// ── Members ──

export type Member = {
  userId: string;
  email: string;
  displayName: string | null;
  role: Role;
  departmentId: string | null;
  departmentName: string | null;
  joinedAt: string;
};

type RawMember = {
  user_id: string;
  email: string;
  display_name: string | null;
  role: Role;
  department_id: string | null;
  department_name: string | null;
  joined_at: string;
};

function toMember(m: RawMember): Member {
  return {
    userId: m.user_id,
    email: m.email,
    displayName: m.display_name,
    role: m.role,
    departmentId: m.department_id,
    departmentName: m.department_name,
    joinedAt: m.joined_at,
  };
}

export async function listMembers(slug: string): Promise<Member[]> {
  const response = await ensureOk(await apiFetch(companyUrl(slug, "/members")), "Failed to load members");
  return ((await response.json()) as RawMember[]).map(toMember);
}

// Fields left out are unchanged; departmentId: null clears the department.
export async function updateMember(
  slug: string,
  userId: string,
  changes: { role?: "admin" | "member"; departmentId?: string | null },
): Promise<Member> {
  const body: Record<string, unknown> = {};
  if (changes.role !== undefined) body.role = changes.role;
  if (changes.departmentId !== undefined) body.department_id = changes.departmentId;
  const response = await ensureOk(
    await apiFetch(companyUrl(slug, `/members/${userId}`), jsonInit("PATCH", body)),
    "Failed to update member",
  );
  return toMember((await response.json()) as RawMember);
}

// Removing yourself is leaving the company.
export async function removeMember(slug: string, userId: string): Promise<void> {
  await ensureOk(
    await apiFetch(companyUrl(slug, `/members/${userId}`), { method: "DELETE" }),
    "Failed to remove member",
  );
}

export async function transferOwnership(slug: string, userId: string): Promise<Member> {
  const response = await ensureOk(
    await apiFetch(companyUrl(slug, "/transfer-ownership"), jsonInit("POST", { user_id: userId })),
    "Failed to transfer ownership",
  );
  return toMember((await response.json()) as RawMember);
}

// ── Invites ──

export type Invite = {
  id: string;
  email: string;
  role: Role;
  departmentId: string | null;
  expiresAt: string;
  createdAt: string;
};

type RawInvite = {
  id: string;
  email: string;
  role: Role;
  department_id: string | null;
  expires_at: string;
  created_at: string;
};

function toInvite(i: RawInvite): Invite {
  return {
    id: i.id,
    email: i.email,
    role: i.role,
    departmentId: i.department_id,
    expiresAt: i.expires_at,
    createdAt: i.created_at,
  };
}

export async function listInvites(slug: string): Promise<Invite[]> {
  const response = await ensureOk(await apiFetch(companyUrl(slug, "/invites")), "Failed to load invites");
  return ((await response.json()) as RawInvite[]).map(toInvite);
}

// The token comes back only here (the server keeps its hash), so the caller shows the link now.
export async function createInvite(
  slug: string,
  payload: { email: string; role: "admin" | "member"; departmentId: string | null },
): Promise<Invite & { token: string }> {
  const response = await ensureOk(
    await apiFetch(
      companyUrl(slug, "/invites"),
      jsonInit("POST", { email: payload.email, role: payload.role, department_id: payload.departmentId }),
    ),
    "Failed to create invite",
  );
  const data = (await response.json()) as RawInvite & { token: string };
  return { ...toInvite(data), token: data.token };
}

export async function revokeInvite(slug: string, inviteId: string): Promise<void> {
  await ensureOk(
    await apiFetch(companyUrl(slug, `/invites/${inviteId}`), { method: "DELETE" }),
    "Failed to revoke invite",
  );
}

export function inviteLink(token: string): string {
  const origin = typeof window !== "undefined" ? window.location.origin : "";
  return `${origin}/invite/${token}`;
}

export type InvitePreview = { companyName: string; email: string; role: Role };

export async function getInvitePreview(token: string): Promise<InvitePreview> {
  const response = await ensureOk(
    await apiFetch(`${API_URL}/invites/${encodeURIComponent(token)}`),
    "Failed to load invite",
  );
  const data = (await response.json()) as { company_name: string; email: string; role: Role };
  return { companyName: data.company_name, email: data.email, role: data.role };
}

export async function acceptInvite(token: string): Promise<{ companySlug: string }> {
  const response = await ensureOk(
    await apiFetch(`${API_URL}/invites/${encodeURIComponent(token)}/accept`, { method: "POST" }),
    "Failed to accept invite",
  );
  const { company_slug } = (await response.json()) as { company_slug: string };
  return { companySlug: company_slug };
}

// ── Departments ──

export type Department = {
  id: string;
  name: string;
  companyId: string;
  createdAt: string;
};

type RawDepartment = { id: string; name: string; company_id: string; created_at: string };

function toDepartment(d: RawDepartment): Department {
  return { id: d.id, name: d.name, companyId: d.company_id, createdAt: d.created_at };
}

export async function listDepartments(slug: string): Promise<Department[]> {
  const response = await ensureOk(await apiFetch(companyUrl(slug, "/departments")), "Failed to load departments");
  return ((await response.json()) as RawDepartment[]).map(toDepartment);
}

export async function createDepartment(slug: string, name: string): Promise<Department> {
  const response = await ensureOk(
    await apiFetch(companyUrl(slug, "/departments"), jsonInit("POST", { name })),
    "Failed to create department",
  );
  return toDepartment((await response.json()) as RawDepartment);
}

export async function deleteDepartment(slug: string, departmentId: string): Promise<void> {
  await ensureOk(
    await apiFetch(companyUrl(slug, `/departments/${departmentId}`), { method: "DELETE" }),
    "Failed to delete department",
  );
}

// ── Instance administration (instance admins only, outside any company) ──

export type InstanceUser = {
  id: string;
  email: string;
  displayName: string | null;
  isInstanceAdmin: boolean;
  approvalStatus: string;
  companies: { name: string; slug: string; role: Role }[];
  createdAt: string;
};

type RawInstanceUser = {
  id: string;
  email: string;
  display_name: string | null;
  is_instance_admin: boolean;
  approval_status: string;
  companies: { name: string; slug: string; role: Role }[];
  created_at: string;
};

function toInstanceUser(u: RawInstanceUser): InstanceUser {
  return {
    id: u.id,
    email: u.email,
    displayName: u.display_name,
    isInstanceAdmin: u.is_instance_admin,
    approvalStatus: u.approval_status,
    companies: u.companies,
    createdAt: u.created_at,
  };
}

export async function listInstanceUsers(approvalStatus?: string): Promise<InstanceUser[]> {
  const query = approvalStatus ? `?approval_status=${encodeURIComponent(approvalStatus)}` : "";
  const response = await ensureOk(await apiFetch(`${API_URL}/instance/users${query}`), "Failed to load users");
  return ((await response.json()) as RawInstanceUser[]).map(toInstanceUser);
}

export async function approveUser(userId: string): Promise<InstanceUser> {
  const response = await ensureOk(
    await apiFetch(`${API_URL}/instance/users/${userId}/approve`, { method: "PATCH" }),
    "Failed to approve user",
  );
  return toInstanceUser((await response.json()) as RawInstanceUser);
}

export async function rejectUser(userId: string): Promise<InstanceUser> {
  const response = await ensureOk(
    await apiFetch(`${API_URL}/instance/users/${userId}/reject`, { method: "PATCH" }),
    "Failed to reject user",
  );
  return toInstanceUser((await response.json()) as RawInstanceUser);
}

export async function deleteInstanceUser(userId: string): Promise<void> {
  await ensureOk(
    await apiFetch(`${API_URL}/instance/users/${userId}`, { method: "DELETE" }),
    "Failed to delete user",
  );
}

export type InstanceCompany = {
  id: string;
  name: string;
  slug: string;
  status: string;
  memberCount: number;
  createdAt: string;
};

type RawInstanceCompany = {
  id: string;
  name: string;
  slug: string;
  status: string;
  member_count: number;
  created_at: string;
};

function toInstanceCompany(c: RawInstanceCompany): InstanceCompany {
  return {
    id: c.id,
    name: c.name,
    slug: c.slug,
    status: c.status,
    memberCount: c.member_count,
    createdAt: c.created_at,
  };
}

export async function listInstanceCompanies(): Promise<InstanceCompany[]> {
  const response = await ensureOk(await apiFetch(`${API_URL}/instance/companies`), "Failed to load companies");
  return ((await response.json()) as RawInstanceCompany[]).map(toInstanceCompany);
}

export async function setCompanyStatus(companyId: string, status: "active" | "suspended"): Promise<InstanceCompany> {
  const action = status === "active" ? "activate" : "suspend";
  const response = await ensureOk(
    await apiFetch(`${API_URL}/instance/companies/${companyId}/${action}`, { method: "PATCH" }),
    `Failed to ${action} company`,
  );
  return toInstanceCompany((await response.json()) as RawInstanceCompany);
}

export async function deleteInstanceCompany(companyId: string): Promise<void> {
  await ensureOk(
    await apiFetch(`${API_URL}/instance/companies/${companyId}`, { method: "DELETE" }),
    "Failed to delete company",
  );
}
