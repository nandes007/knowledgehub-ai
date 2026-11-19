"use client";

import { createContext, useCallback, useContext, useEffect, useState, useSyncExternalStore } from "react";
import { getMe, loginAccount, registerAccount, type Me, type RegisterResult } from "@/lib/api";
import { clearToken, getToken, setToken, subscribeToken } from "@/lib/auth";

type AuthContextValue = {
  token: string | null;
  // The account and its memberships. Roles live per company: see useCompany().
  user: Me | null;
  // False on the server and on the very first client render, so the route
  // guard doesn't redirect to /login before it's had a chance to read
  // localStorage (which only exists client-side).
  isReady: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName: string, inviteToken?: string) => Promise<RegisterResult>;
  logout: () => void;
  // Re-reads memberships after creating, joining or leaving a company.
  refreshUser: () => Promise<Me | null>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

const alwaysReady = () => true;
const notReadyOnServer = () => false;
const noopSubscribe = () => () => {};

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const token = useSyncExternalStore(subscribeToken, getToken, () => null);
  const isReady = useSyncExternalStore(noopSubscribe, alwaysReady, notReadyOnServer);
  const [user, setUser] = useState<Me | null>(null);

  useEffect(() => {
    if (!token) {
      setUser(null);
      return;
    }
    let cancelled = false;
    getMe()
      .then((profile) => {
        if (!cancelled) setUser(profile);
      })
      .catch(() => {
        if (!cancelled) setUser(null);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const refreshUser = useCallback(async () => {
    try {
      const profile = await getMe();
      setUser(profile);
      return profile;
    } catch {
      return null;
    }
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const { accessToken } = await loginAccount(email, password);
    setToken(accessToken);
  }, []);

  const register = useCallback(
    (email: string, password: string, displayName: string, inviteToken?: string) =>
      registerAccount(email, password, displayName, inviteToken),
    [],
  );

  const logout = useCallback(() => {
    setUser(null);
    clearToken();
  }, []);

  return (
    <AuthContext.Provider value={{ token, user, isReady, login, register, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
