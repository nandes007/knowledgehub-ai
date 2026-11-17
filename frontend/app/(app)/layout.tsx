"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";

// Signed-in area. Company pages add their own chrome in [slug]/layout.
export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { token, user, isReady } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isReady && !token) router.replace("/login");
  }, [isReady, token, router]);

  // Avoid flashing protected content before the redirect above kicks in.
  if (!isReady || !token) return null;
  if (!user) return <div className="flex flex-1 items-center justify-center text-sm text-text-tertiary">Loading…</div>;

  return <>{children}</>;
}
