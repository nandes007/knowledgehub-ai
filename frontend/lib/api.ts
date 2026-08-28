import { clearToken, getToken } from "./auth";
import { parseSseStream } from "./sse";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
  message: string,
  conversationId?: string,
  onToken?: (text: string) => void,
): Promise<ChatResult> {
  const response = await apiFetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });

  if (!response.ok) {
    throw new Error(`Chat request failed: ${response.status}`);
  }

  let answer = "";
  try {
    for await (const { event, data } of parseSseStream(response)) {
      if (event === "token") {
        const text = (JSON.parse(data) as { text: string }).text;
        answer += text;
        onToken?.(text);
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

export async function listConversations(): Promise<Conversation[]> {
  const response = await apiFetch(`${API_URL}/conversations`);
  if (!response.ok) {
    throw new Error(`Failed to load conversations: ${response.status}`);
  }
  const data = (await response.json()) as { id: string; title: string }[];
  return data.map(({ id, title }) => ({ id, title }));
}

export async function createConversation(): Promise<Conversation> {
  const response = await apiFetch(`${API_URL}/conversations`, { method: "POST" });
  if (!response.ok) {
    throw new Error(`Failed to create conversation: ${response.status}`);
  }
  const { id, title } = (await response.json()) as { id: string; title: string };
  return { id, title };
}

export async function renameConversation(conversationId: string, title: string): Promise<Conversation> {
  const response = await apiFetch(`${API_URL}/conversations/${conversationId}`, {
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

export async function deleteConversation(conversationId: string): Promise<void> {
  const response = await apiFetch(`${API_URL}/conversations/${conversationId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(`Failed to delete conversation: ${response.status}`);
  }
}

export type ConversationMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: Source[];
};

export async function getConversationMessages(conversationId: string): Promise<ConversationMessage[]> {
  const response = await apiFetch(`${API_URL}/conversations/${conversationId}/messages`);
  if (!response.ok) {
    throw new Error(`Failed to load conversation messages: ${response.status}`);
  }
  const data = (await response.json()) as {
    id: string;
    role: "user" | "assistant";
    content: string;
    sources: Source[] | null;
  }[];
  return data.map(({ id, role, content, sources }) => ({ id, role, content, sources: sources ?? [] }));
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
  errorMessage: string | null;
  createdAt: string;
};

export async function listDocuments(): Promise<Document[]> {
  const response = await apiFetch(`${API_URL}/documents`);
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
    error_message: string | null;
    created_at: string;
  }[];
  return data.map(({ id, filename, status, department, visibility, chunk_count, error_message, created_at }) => ({
    id,
    filename,
    status,
    department,
    visibility,
    chunkCount: chunk_count,
    errorMessage: error_message,
    createdAt: created_at,
  }));
}

export type UploadedDocument = {
  id: string;
  filename: string;
  status: DocumentStatus;
};

export async function uploadDocument(
  file: File,
  options?: { department?: string; visibility?: Visibility },
): Promise<UploadedDocument> {
  const formData = new FormData();
  formData.append("file", file);
  if (options?.department) formData.append("department", options.department);
  if (options?.visibility) formData.append("visibility", options.visibility);
  const response = await apiFetch(`${API_URL}/documents`, { method: "POST", body: formData });
  if (!response.ok) {
    const detail = await response
      .json()
      .then((body: { detail?: string }) => body.detail)
      .catch(() => undefined);
    throw new Error(detail ?? `Failed to upload document: ${response.status}`);
  }
  return (await response.json()) as UploadedDocument;
}

export async function deleteDocument(documentId: string): Promise<void> {
  const response = await apiFetch(`${API_URL}/documents/${documentId}`, { method: "DELETE" });
  if (!response.ok) {
    throw new Error(`Failed to delete document: ${response.status}`);
  }
}

export type Me = {
  email: string;
  displayName: string | null;
  role: string;
  approvalStatus: string;
  companyId: string | null;
  companyName: string | null;
  departmentId: string | null;
  departmentName: string | null;
};

export async function getMe(): Promise<Me> {
  const response = await apiFetch(`${API_URL}/auth/me`);
  if (!response.ok) {
    throw new Error(`Failed to load profile: ${response.status}`);
  }
  const data = (await response.json()) as {
    email: string;
    display_name: string | null;
    role: string;
    approval_status: string;
    company_id: string | null;
    company_name: string | null;
    department_id: string | null;
    department_name: string | null;
  };
  return {
    email: data.email,
    displayName: data.display_name,
    role: data.role,
    approvalStatus: data.approval_status,
    companyId: data.company_id,
    companyName: data.company_name,
    departmentId: data.department_id,
    departmentName: data.department_name,
  };
}

export type Stats = {
  messagesPerDay: { date: string; count: number }[];
  documentCount: number;
  estimatedCostUsd: number;
  documentsPerUser: { email: string; count: number }[];
  costPerDay: { date: string; costUsd: number }[];
};

// The API is the real gate (403 for non-admins); the admin page matches on
// this message to redirect rather than render an error.
export const ADMIN_REQUIRED = "Admin access required.";

export async function getStats(): Promise<Stats> {
  const response = await apiFetch(`${API_URL}/stats`);
  if (response.status === 403) {
    throw new Error(ADMIN_REQUIRED);
  }
  if (!response.ok) {
    throw new Error(`Failed to load stats: ${response.status}`);
  }
  const data = (await response.json()) as {
    messages_per_day: { date: string; count: number }[];
    document_count: number;
    estimated_cost_usd: number;
    documents_per_user: { email: string; count: number }[];
    cost_per_day: { date: string; cost_usd: number }[];
  };
  return {
    messagesPerDay: data.messages_per_day,
    documentCount: data.document_count,
    estimatedCostUsd: data.estimated_cost_usd,
    documentsPerUser: data.documents_per_user,
    costPerDay: data.cost_per_day.map(({ date, cost_usd }) => ({ date, costUsd: cost_usd })),
  };
}

export type AuthResult = { accessToken: string };
export type RegisterResult = { message: string };

export async function registerAccount(
  companyName: string,
  email: string,
  password: string,
  displayName: string,
): Promise<RegisterResult> {
  const response = await apiFetch(`${API_URL}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      company_name: companyName,
      email,
      password,
      display_name: displayName,
    }),
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    if (response.status === 409) {
      throw new Error(body.detail ?? "An account with that email or company already exists.");
    }
    throw new Error(body.detail ?? "Registration failed. Please try again.");
  }
  const { message } = (await response.json()) as { message: string };
  return { message };
}

export async function loginAccount(email: string, password: string): Promise<AuthResult> {
  const response = await apiFetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? "Invalid email or password.");
  }
  const { access_token } = (await response.json()) as { access_token: string };
  return { accessToken: access_token };
}

export type SuperadminUser = {
  id: string;
  email: string;
  displayName: string | null;
  role: string;
  approvalStatus: string;
  companyId: string | null;
  companyName: string | null;
  departmentId: string | null;
  createdAt: string;
};

export async function listPendingUsers(): Promise<SuperadminUser[]> {
  const response = await apiFetch(`${API_URL}/superadmin/users?approval_status=pending`);
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Failed to load pending users: ${response.status}`);
  }
  const data = (await response.json()) as {
    id: string;
    email: string;
    display_name: string | null;
    role: string;
    approval_status: string;
    company_id: string | null;
    company_name: string | null;
    department_id: string | null;
    created_at: string;
  }[];
  return data.map((u) => ({
    id: u.id,
    email: u.email,
    displayName: u.display_name,
    role: u.role,
    approvalStatus: u.approval_status,
    companyId: u.company_id,
    companyName: u.company_name,
    departmentId: u.department_id,
    createdAt: u.created_at,
  }));
}

export async function approveUser(userId: string): Promise<SuperadminUser> {
  const response = await apiFetch(`${API_URL}/superadmin/users/${userId}/approve`, {
    method: "PATCH",
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Failed to approve user: ${response.status}`);
  }
  const u = (await response.json()) as {
    id: string;
    email: string;
    display_name: string | null;
    role: string;
    approval_status: string;
    company_id: string | null;
    company_name: string | null;
    department_id: string | null;
    created_at: string;
  };
  return {
    id: u.id,
    email: u.email,
    displayName: u.display_name,
    role: u.role,
    approvalStatus: u.approval_status,
    companyId: u.company_id,
    companyName: u.company_name,
    departmentId: u.department_id,
    createdAt: u.created_at,
  };
}

export async function rejectUser(userId: string): Promise<SuperadminUser> {
  const response = await apiFetch(`${API_URL}/superadmin/users/${userId}/reject`, {
    method: "PATCH",
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Failed to reject user: ${response.status}`);
  }
  const u = (await response.json()) as {
    id: string;
    email: string;
    display_name: string | null;
    role: string;
    approval_status: string;
    company_id: string | null;
    company_name: string | null;
    department_id: string | null;
    created_at: string;
  };
  return {
    id: u.id,
    email: u.email,
    displayName: u.display_name,
    role: u.role,
    approvalStatus: u.approval_status,
    companyId: u.company_id,
    companyName: u.company_name,
    departmentId: u.department_id,
    createdAt: u.created_at,
  };
}

export async function deleteSuperadminUser(userId: string): Promise<void> {
  const response = await apiFetch(`${API_URL}/superadmin/users/${userId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Failed to delete user: ${response.status}`);
  }
}

export type SuperadminCompany = {
  id: string;
  name: string;
  status: string;
  createdAt: string;
  updatedAt: string;
};

export async function listCompanies(): Promise<SuperadminCompany[]> {
  const response = await apiFetch(`${API_URL}/superadmin/companies`);
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Failed to load companies: ${response.status}`);
  }
  const data = (await response.json()) as {
    id: string;
    name: string;
    status: string;
    created_at: string;
    updated_at: string;
  }[];
  return data.map((c) => ({
    id: c.id,
    name: c.name,
    status: c.status,
    createdAt: c.created_at,
    updatedAt: c.updated_at,
  }));
}

export async function suspendCompany(companyId: string): Promise<SuperadminCompany> {
  const response = await apiFetch(`${API_URL}/superadmin/companies/${companyId}/suspend`, {
    method: "PATCH",
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Failed to suspend company: ${response.status}`);
  }
  const c = (await response.json()) as {
    id: string;
    name: string;
    status: string;
    created_at: string;
    updated_at: string;
  };
  return {
    id: c.id,
    name: c.name,
    status: c.status,
    createdAt: c.created_at,
    updatedAt: c.updated_at,
  };
}

export async function activateCompany(companyId: string): Promise<SuperadminCompany> {
  const response = await apiFetch(`${API_URL}/superadmin/companies/${companyId}/activate`, {
    method: "PATCH",
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Failed to activate company: ${response.status}`);
  }
  const c = (await response.json()) as {
    id: string;
    name: string;
    status: string;
    created_at: string;
    updated_at: string;
  };
  return {
    id: c.id,
    name: c.name,
    status: c.status,
    createdAt: c.created_at,
    updatedAt: c.updated_at,
  };
}

export type TeamUser = {
  id: string;
  email: string;
  displayName: string | null;
  role: string;
  approvalStatus: string;
  companyId: string | null;
  departmentId: string | null;
  departmentName: string | null;
  createdAt: string;
};

export type CreateUserPayload = {
  email: string;
  password: string;
  displayName?: string;
  departmentId: string;
  role?: string;
};

export type UpdateUserPayload = {
  displayName?: string;
  departmentId?: string;
  role?: string;
};

export async function listTeamUsers(): Promise<TeamUser[]> {
  const response = await apiFetch(`${API_URL}/users`);
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Failed to load team users: ${response.status}`);
  }
  const data = (await response.json()) as {
    id: string;
    email: string;
    display_name: string | null;
    role: string;
    approval_status: string;
    company_id: string | null;
    department_id: string | null;
    department_name: string | null;
    created_at: string;
  }[];
  return data.map((u) => ({
    id: u.id,
    email: u.email,
    displayName: u.display_name,
    role: u.role,
    approvalStatus: u.approval_status,
    companyId: u.company_id,
    departmentId: u.department_id,
    departmentName: u.department_name,
    createdAt: u.created_at,
  }));
}

export async function createUser(payload: CreateUserPayload): Promise<TeamUser> {
  const response = await apiFetch(`${API_URL}/users`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: payload.email,
      password: payload.password,
      display_name: payload.displayName,
      department_id: payload.departmentId,
      role: payload.role ?? "member",
    }),
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Failed to create user: ${response.status}`);
  }
  const u = (await response.json()) as {
    id: string;
    email: string;
    display_name: string | null;
    role: string;
    approval_status: string;
    company_id: string | null;
    department_id: string | null;
    department_name: string | null;
    created_at: string;
  };
  return {
    id: u.id,
    email: u.email,
    displayName: u.display_name,
    role: u.role,
    approvalStatus: u.approval_status,
    companyId: u.company_id,
    departmentId: u.department_id,
    departmentName: u.department_name,
    createdAt: u.created_at,
  };
}

export async function updateUser(userId: string, payload: UpdateUserPayload): Promise<TeamUser> {
  const response = await apiFetch(`${API_URL}/users/${userId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      display_name: payload.displayName,
      department_id: payload.departmentId,
      role: payload.role,
    }),
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Failed to update user: ${response.status}`);
  }
  const u = (await response.json()) as {
    id: string;
    email: string;
    display_name: string | null;
    role: string;
    approval_status: string;
    company_id: string | null;
    department_id: string | null;
    department_name: string | null;
    created_at: string;
  };
  return {
    id: u.id,
    email: u.email,
    displayName: u.display_name,
    role: u.role,
    approvalStatus: u.approval_status,
    companyId: u.company_id,
    departmentId: u.department_id,
    departmentName: u.department_name,
    createdAt: u.created_at,
  };
}

export async function deleteUser(userId: string): Promise<void> {
  const response = await apiFetch(`${API_URL}/users/${userId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Failed to delete user: ${response.status}`);
  }
}

export type Department = {
  id: string;
  name: string;
  companyId: string;
  createdAt: string;
};

export async function listDepartments(): Promise<Department[]> {
  const response = await apiFetch(`${API_URL}/departments`);
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Failed to load departments: ${response.status}`);
  }
  const data = (await response.json()) as {
    id: string;
    name: string;
    company_id: string;
    created_at: string;
  }[];
  return data.map((d) => ({
    id: d.id,
    name: d.name,
    companyId: d.company_id,
    createdAt: d.created_at,
  }));
}

export async function createDepartment(name: string): Promise<Department> {
  const response = await apiFetch(`${API_URL}/departments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Failed to create department: ${response.status}`);
  }
  const d = (await response.json()) as {
    id: string;
    name: string;
    company_id: string;
    created_at: string;
  };
  return {
    id: d.id,
    name: d.name,
    companyId: d.company_id,
    createdAt: d.created_at,
  };
}

export async function deleteDepartment(departmentId: string): Promise<void> {
  const response = await apiFetch(`${API_URL}/departments/${departmentId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Failed to delete department: ${response.status}`);
  }
}
