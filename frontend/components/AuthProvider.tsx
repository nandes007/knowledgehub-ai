"use client";

import { createContext, useCallback, useContext, useEffect, useState, useSyncExternalStore } from "react";
import { getMe, loginAccount, registerAccount, type Me, type RegisterResult } from "@/lib/api";
import { clearToken, getToken, setToken, subscribeToken } from "@/lib/auth";

type AuthContextValue = {
  token: string | null;
  user: Me | null;
  // True if superadmin or company admin
  isAdmin: boolean;
  isSuperAdmin: boolean;
  isMember: boolean;
  // False on the server and on the very first client render, so the route
  // guard doesn't redirect to /login before it's had a chance to read
  // localStorage (which only exists client-side).
  isReady: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (companyName: string, email: string, password: string, displayName: string) => Promise<RegisterResult>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

const alwaysReady = () => true;
const notReadyOnServer = () => false;
const noopSubscribe = () => () => {};

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const token = useSyncExternalStore(subscribeToken, getToken, () => null);
  const isReady = useSyncExternalStore(noopSubscribe, alwaysReady, notReadyOnServer);
  const [user, setUser] = useState<Me | null>(null);

  const isSuperAdmin = token !== null && user?.role === "superadmin";
  const isAdmin = token !== null && (user?.role === "admin" || user?.role === "superadmin");
  const isMember = token !== null && user?.role === "member";

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

  const login = useCallback(async (email: string, password: string) => {
    const { accessToken } = await loginAccount(email, password);
    setToken(accessToken);
  }, []);

  const register = useCallback(async (companyName: string, email: string, password: string, displayName: string) => {
    return await registerAccount(companyName, email, password, displayName);
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    clearToken();
  }, []);

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        isAdmin,
        isSuperAdmin,
        isMember,
        isReady,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
