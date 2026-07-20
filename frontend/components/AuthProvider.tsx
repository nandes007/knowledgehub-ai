"use client";

import { createContext, useCallback, useContext, useSyncExternalStore } from "react";
import { loginAccount, registerAccount } from "@/lib/api";
import { clearToken, getToken, setToken, subscribeToken } from "@/lib/auth";

type AuthContextValue = {
  token: string | null;
  // False on the server and on the very first client render, so the route
  // guard doesn't redirect to /login before it's had a chance to read
  // localStorage (which only exists client-side).
  isReady: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

const alwaysReady = () => true;
const notReadyOnServer = () => false;
const noopSubscribe = () => () => {};

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const token = useSyncExternalStore(subscribeToken, getToken, () => null);
  const isReady = useSyncExternalStore(noopSubscribe, alwaysReady, notReadyOnServer);

  const login = useCallback(async (email: string, password: string) => {
    const { accessToken } = await loginAccount(email, password);
    setToken(accessToken);
  }, []);

  const register = useCallback(async (email: string, password: string, displayName?: string) => {
    const { accessToken } = await registerAccount(email, password, displayName);
    setToken(accessToken);
  }, []);

  const logout = useCallback(() => {
    clearToken();
  }, []);

  return (
    <AuthContext.Provider value={{ token, isReady, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
