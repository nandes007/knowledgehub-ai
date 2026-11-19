"use client";

import { use, useEffect } from "react";
import Link from "next/link";
import { useAuth } from "@/components/AuthProvider";
import { CompanyProvider } from "@/components/CompanyProvider";
import { ConversationsProvider } from "@/components/ConversationsProvider";
import { Sidebar } from "@/components/Sidebar";
import { setLastCompany } from "@/lib/auth";

function Notice({ title, message }: { title: string; message: string }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 bg-surface-primary p-6 text-center">
      <h1 className="text-lg font-semibold text-text-primary">{title}</h1>
      <p className="max-w-sm text-sm text-text-secondary">{message}</p>
      <Link href="/" className="mt-2 text-sm font-medium text-gold hover:underline">
        Go to your companies
      </Link>
    </div>
  );
}

export default function CompanyLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ slug: string }>;
}) {
  const { slug } = use(params);
  const { user } = useAuth();
  // The parent layout renders nothing until the user has loaded.
  const company = user?.companies.find((c) => c.slug === slug);
  const isUsable = company?.status === "active";

  useEffect(() => {
    if (isUsable) setLastCompany(slug);
  }, [isUsable, slug]);

  // Same answer for "no such company" and "not a member", like the API.
  if (!company) return <Notice title="Company not found" message="It doesn't exist, or you're not a member of it." />;
  if (!isUsable) {
    return <Notice title="Company suspended" message={`${company.name} has been suspended by the instance administrator.`} />;
  }

  return (
    <CompanyProvider company={company}>
      {/* Keyed so switching companies never shows the previous one's conversations. */}
      <ConversationsProvider key={slug}>
        <div className="flex flex-1 overflow-hidden">
          <Sidebar />
          {children}
        </div>
      </ConversationsProvider>
    </CompanyProvider>
  );
}
