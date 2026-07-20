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
