"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { ConversationsProvider } from "@/components/ConversationsProvider";
import { Sidebar } from "@/components/Sidebar";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { token, isReady } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isReady && !token) router.replace("/login");
  }, [isReady, token, router]);

  // Avoid flashing protected content before the redirect above kicks in.
  if (!isReady || !token) return null;

  return (
    <ConversationsProvider>
      <div className="flex flex-1">
        <Sidebar />
        {children}
      </div>
    </ConversationsProvider>
  );
}
