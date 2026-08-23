"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/components/AuthProvider";
import { Button, Card, Input, Label } from "@/components/ui";

export default function RegisterPage() {
  const [companyName, setCompanyName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const { register } = useAuth();

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await register(companyName.trim(), email.trim(), password, displayName.trim());
      setIsSubmitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isSubmitted) {
    return (
      <Card className="w-full max-w-sm space-y-5 p-6 text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-gold/10 text-gold">
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <div>
          <h1 className="text-xl font-semibold text-text-primary">Registration Submitted</h1>
          <p className="mt-2 text-sm text-text-secondary">
            Your account for <span className="font-medium text-text-primary">{companyName}</span> is pending administrator approval.
          </p>
          <p className="mt-2 text-xs text-text-tertiary">
            You will be able to log in once an administrator approves your request.
          </p>
        </div>
        <div className="pt-2">
          <Link href="/login" className="block w-full">
            <Button variant="primary" className="w-full">
              Go to Log in
            </Button>
          </Link>
        </div>
      </Card>
    );
  }

  return (
    <Card className="w-full max-w-sm space-y-5 p-6">
      <div>
        <h1 className="text-xl font-semibold text-text-primary">Register</h1>
        <p className="mt-1 text-sm text-text-secondary">Create a new company account.</p>
      </div>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-1">
          <Label htmlFor="companyName">Company Name</Label>
          <Input
            id="companyName"
            type="text"
            required
            placeholder="Acme Corp"
            value={companyName}
            onChange={(event) => setCompanyName(event.target.value)}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="displayName">Name</Label>
          <Input
            id="displayName"
            type="text"
            autoComplete="name"
            required
            placeholder="Jane Doe"
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            placeholder="jane@acme.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <p className="text-xs text-text-tertiary">At least 8 characters.</p>
        </div>
        {error && <p className="text-sm text-status-void">{error}</p>}
        <Button type="submit" disabled={isSubmitting} className="w-full">
          {isSubmitting ? "Submitting…" : "Register"}
        </Button>
      </form>
      <p className="text-sm text-text-secondary">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-gold hover:text-gold-hover hover:underline">
          Log in
        </Link>
      </p>
    </Card>
  );
}
