"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  const { token, isReady } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isReady && token) router.replace("/");
  }, [isReady, token, router]);

  if (isReady && token) return null;

  return <div className="flex flex-1 items-center justify-center p-4">{children}</div>;
}
