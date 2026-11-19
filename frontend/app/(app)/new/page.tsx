"use client";

import Link from "next/link";
import { CreateCompanyForm } from "@/components/CreateCompanyForm";
import { AuthShell, Card } from "@/components/ui";

export default function NewCompanyPage() {
  return (
    <AuthShell>
      <Card className="space-y-5 p-6">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">Create a company</h1>
          <p className="mt-1 text-sm text-text-secondary">You&rsquo;ll be its owner. Its documents and chats stay separate from your other companies.</p>
        </div>
        <CreateCompanyForm />
        <Link href="/" className="block text-sm text-text-secondary hover:text-text-primary">
          Cancel
        </Link>
      </Card>
    </AuthShell>
  );
}
