"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { acceptInvite, getInvitePreview, type InvitePreview } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";
import { AuthShell, Button, Card, Input, Label } from "@/components/ui";

// Outside the (auth) group on purpose: that layout sends signed-in people away,
// and a signed-in person accepts here.
export default function InvitePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);
  const { token: session, isReady, user, register, login, logout, refreshUser } = useAuth();
  const router = useRouter();
  const [preview, setPreview] = useState<InvitePreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");

  useEffect(() => {
    getInvitePreview(token)
      .then(setPreview)
      .catch((err) => setError(err instanceof Error ? err.message : "This invite link is invalid or has expired."));
  }, [token]);

  async function join(run: () => Promise<{ companySlug: string | null }>) {
    setError(null);
    setIsSubmitting(true);
    try {
      const { companySlug } = await run();
      await refreshUser();
      router.replace(companySlug ? `/${companySlug}` : "/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
      setIsSubmitting(false);
    }
  }

  // Registering through the invite joins the company and skips approval, even when signup is closed.
  function handleRegister(event: React.FormEvent) {
    event.preventDefault();
    if (!preview) return;
    join(async () => {
      const result = await register(preview.email, password, displayName.trim(), token);
      await login(preview.email, password);
      return result;
    });
  }

  if (!isReady) return null;

  const loginHref = `/login?next=${encodeURIComponent(`/invite/${token}`)}`;
  const wrongAccount = user && preview && user.email.toLowerCase() !== preview.email.toLowerCase();

  return (
    <AuthShell>
      <Card className="space-y-5 p-6">
        {!preview ? (
          <div>
            <h1 className="text-xl font-semibold text-text-primary">Invite</h1>
            <p className="mt-2 text-sm text-status-void">{error ?? "Loading invite…"}</p>
          </div>
        ) : (
          <>
            <div>
              <h1 className="text-xl font-semibold text-text-primary">Join {preview.companyName}</h1>
              <p className="mt-1 text-sm text-text-secondary">
                You&rsquo;ve been invited as {preview.role === "admin" ? "an admin" : "a member"}. This invite is for{" "}
                <span className="font-medium text-text-primary">{preview.email}</span>.
              </p>
            </div>

            {session ? (
              wrongAccount ? (
                <div className="space-y-3">
                  <p className="text-sm text-text-secondary">
                    You&rsquo;re signed in as <span className="font-medium text-text-primary">{user.email}</span>. Log out and
                    sign in as {preview.email} to accept.
                  </p>
                  <Button variant="secondary" className="w-full" onClick={logout}>
                    Log out
                  </Button>
                </div>
              ) : (
                <Button className="w-full" disabled={isSubmitting} onClick={() => join(() => acceptInvite(token))}>
                  {isSubmitting ? "Joining…" : `Join ${preview.companyName}`}
                </Button>
              )
            ) : (
              <>
                <form onSubmit={handleRegister} className="space-y-4">
                  <div className="space-y-1">
                    <Label htmlFor="email">Email</Label>
                    <Input id="email" type="email" value={preview.email} readOnly disabled />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="displayName">Name</Label>
                    <Input
                      id="displayName"
                      autoComplete="name"
                      required
                      value={displayName}
                      onChange={(event) => setDisplayName(event.target.value)}
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
                  </div>
                  <Button type="submit" disabled={isSubmitting} className="w-full">
                    {isSubmitting ? "Creating account…" : "Create account and join"}
                  </Button>
                </form>
                <p className="text-sm text-text-secondary">
                  Already have an account?{" "}
                  <Link href={loginHref} className="font-medium text-gold hover:underline">
                    Log in to accept
                  </Link>
                </p>
              </>
            )}
            {error && <p className="text-sm text-status-void">{error}</p>}
          </>
        )}
      </Card>
    </AuthShell>
  );
}
