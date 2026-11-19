"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { AuthShell } from "@/components/ui";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  const { token, isReady } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isReady && token) router.replace("/");
  }, [isReady, token, router]);

  if (isReady && token) return null;

  return <AuthShell>{children}</AuthShell>;
}
