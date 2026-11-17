"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { CreateCompanyForm } from "@/components/CreateCompanyForm";
import { AuthShell, Button, Card } from "@/components/ui";
import { getLastCompany } from "@/lib/auth";

// Lands you in your last-used company, else your first; with none, offers to create one.
export default function Home() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const companies = user?.companies ?? [];
  const last = getLastCompany();
  // A suspended company only blocks itself: prefer an active one when there is one.
  const pool = companies.some((c) => c.status === "active") ? companies.filter((c) => c.status === "active") : companies;
  const target = pool.find((c) => c.slug === last) ?? pool[0];

  useEffect(() => {
    if (target) router.replace(`/${target.slug}`);
  }, [target, router]);

  if (target) return null;

  return (
    <AuthShell>
      <Card className="space-y-5 p-6">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">You&rsquo;re not in a company yet</h1>
          <p className="mt-1 text-sm text-text-secondary">
            Create one to start your own knowledge base, or ask a company admin to send you an invite link.
          </p>
        </div>
        <CreateCompanyForm />
        <div className="flex items-center justify-between text-sm">
          {user?.isInstanceAdmin ? (
            <Link href="/instance" className="font-medium text-gold hover:underline">
              Instance admin
            </Link>
          ) : (
            <span />
          )}
          <Button variant="ghost" onClick={logout}>
            Log out
          </Button>
        </div>
      </Card>
    </AuthShell>
  );
}
