"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { SealMark } from "@/components/ui";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  const { token, isReady } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isReady && token) router.replace("/");
  }, [isReady, token, router]);

  if (isReady && token) return null;

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-6 bg-ledger p-4">
      <div className="flex items-center gap-2 text-ledger-ink">
        <SealMark className="h-9 w-9 text-brass" />
        <span className="font-serif text-lg font-semibold">KnowledgeHub AI</span>
      </div>
      {children}
    </div>
  );
}
