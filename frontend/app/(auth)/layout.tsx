"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { Wordmark } from "@/components/ui";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  const { token, isReady } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isReady && token) router.replace("/");
  }, [isReady, token, router]);

  if (isReady && token) return null;

  return (
    <div className="relative flex min-h-screen flex-1 flex-col items-center justify-center gap-6 bg-surface-primary p-4">
      {/* Subtle radial gold glow behind the card */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background: "radial-gradient(ellipse at center, rgba(212,167,69,0.06) 0%, transparent 70%)",
        }}
        aria-hidden="true"
      />
      <div className="relative flex items-center gap-2 text-text-primary">
        <Wordmark className="text-lg" />
        <span className="text-lg font-semibold text-text-primary">AI</span>
      </div>
      <div className="relative w-full max-w-sm">{children}</div>
    </div>
  );
}
