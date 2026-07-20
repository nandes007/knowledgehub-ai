import { afterEach, describe, expect, it, vi } from "vitest";
import { clearToken, getToken, setToken, subscribeToken } from "./auth";

afterEach(() => {
  clearToken();
});

describe("token storage", () => {
  it("returns null when no token has been set", () => {
    expect(getToken()).toBeNull();
  });

  it("returns the token that was set", () => {
    setToken("abc123");

    expect(getToken()).toBe("abc123");
  });

  it("returns null after the token is cleared", () => {
    setToken("abc123");

    clearToken();

    expect(getToken()).toBeNull();
  });
});

describe("subscribeToken", () => {
  it("notifies listeners when the token is set", () => {
    const listener = vi.fn();
    subscribeToken(listener);

    setToken("abc123");

    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("notifies listeners when the token is cleared", () => {
    const listener = vi.fn();
    subscribeToken(listener);

    clearToken();

    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("stops notifying a listener once unsubscribed", () => {
    const listener = vi.fn();
    const unsubscribe = subscribeToken(listener);

    unsubscribe();
    setToken("abc123");

    expect(listener).not.toHaveBeenCalled();
  });
});
