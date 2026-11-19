"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createCompany } from "@/lib/api";
import { useAuth } from "./AuthProvider";
import { Button, Input, Label } from "./ui";

export function CreateCompanyForm() {
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { refreshUser } = useAuth();
  const router = useRouter();

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const company = await createCompany(name.trim());
      await refreshUser();
      router.push(`/${company.slug}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't create the company.");
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-1">
        <Label htmlFor="companyName">Company name</Label>
        <Input
          id="companyName"
          required
          maxLength={100}
          placeholder="Acme Corp"
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
      </div>
      {error && <p className="text-sm text-status-void">{error}</p>}
      <Button type="submit" disabled={isSubmitting} className="w-full">
        {isSubmitting ? "Creating…" : "Create company"}
      </Button>
    </form>
  );
}
