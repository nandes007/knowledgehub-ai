const TOKEN_KEY = "kh_token";

// ponytail: in-memory fallback so this stays testable without adding jsdom;
// the browser always has localStorage, so real sessions never hit this path.
let memoryToken: string | null = null;

const listeners = new Set<() => void>();

function hasLocalStorage(): boolean {
  return typeof localStorage !== "undefined";
}

export function getToken(): string | null {
  return hasLocalStorage() ? localStorage.getItem(TOKEN_KEY) : memoryToken;
}

export function setToken(token: string): void {
  if (hasLocalStorage()) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    memoryToken = token;
  }
  listeners.forEach((listener) => listener());
}

export function clearToken(): void {
  if (hasLocalStorage()) {
    localStorage.removeItem(TOKEN_KEY);
  } else {
    memoryToken = null;
  }
  listeners.forEach((listener) => listener());
}

// For useSyncExternalStore: subscribes to changes made via setToken/clearToken
// (including from other components), returns an unsubscribe function.
export function subscribeToken(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

const LAST_COMPANY_KEY = "kh_last_company";

// Per-browser convenience only: where to land after login. Storage can throw
// (private mode, blocked site data), and nothing breaks without it.
export function getLastCompany(): string | null {
  try {
    return hasLocalStorage() ? localStorage.getItem(LAST_COMPANY_KEY) : null;
  } catch {
    return null;
  }
}

export function setLastCompany(slug: string): void {
  try {
    if (hasLocalStorage()) localStorage.setItem(LAST_COMPANY_KEY, slug);
  } catch {
    // ignore
  }
}

// Only same-site paths: an absolute or protocol-relative `next` would be an open redirect.
export function safeNext(next: string | string[] | undefined): string {
  return typeof next === "string" && next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/\\") ? next : "/";
}
