"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  approveUser,
  deleteInstanceCompany,
  deleteInstanceUser,
  getInstanceStats,
  listInstanceCompanies,
  listInstanceUsers,
  rejectUser,
  setCompanyStatus,
  type InstanceCompany,
  type InstanceUser,
} from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";
import { StatsPanel } from "@/components/StatsPanel";
import { Button, Card, StatusBadge, Tabs, Toast, type ToastVariant } from "@/components/ui";

type TabKey = "users" | "companies" | "stats";
type Notify = (message: string, variant?: ToastVariant) => void;

const TH = "px-4 py-3";
const THEAD =
  "border-b border-border bg-surface-raised text-xs font-medium uppercase tracking-[0.06em] text-text-secondary";

function errorText(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback;
}

// Platform administration. It sits outside any company and shows no company's documents or chats.
export default function InstanceAdminPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabKey>("users");
  const [toast, setToast] = useState<{ message: string | null; variant: ToastVariant }>({ message: null, variant: "success" });
  const notify: Notify = (message, variant = "success") => setToast({ message, variant });
  const isInstanceAdmin = user?.isInstanceAdmin ?? false;

  useEffect(() => {
    if (!isInstanceAdmin) router.replace("/");
  }, [isInstanceAdmin, router]);
  if (!isInstanceAdmin) return null;

  const tabs: { id: TabKey; label: string }[] = [
    { id: "users", label: "Users" },
    { id: "companies", label: "Companies" },
    { id: "stats", label: "Stats" },
  ];

  return (
    <div className="flex flex-1 flex-col gap-6 overflow-y-auto bg-surface-primary px-4 py-6 md:px-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold text-text-primary">Instance admin</h1>
          <p className="mt-1 text-sm text-text-secondary">Manage this instance&rsquo;s users and companies.</p>
        </div>
        <Link href="/" className="text-sm font-medium text-gold hover:underline">
          Back to my companies
        </Link>
      </div>

      <Tabs tabs={tabs} active={activeTab} onChange={setActiveTab} />

      {activeTab === "users" && <UsersTab notify={notify} selfId={user?.id} />}
      {activeTab === "companies" && <CompaniesTab notify={notify} />}
      {activeTab === "stats" && <StatsPanel load={getInstanceStats} />}

      <Toast message={toast.message} variant={toast.variant} onDismiss={() => setToast({ message: null, variant: "success" })} />
    </div>
  );
}

function UsersTab({ notify, selfId }: { notify: Notify; selfId?: string }) {
  const [users, setUsers] = useState<InstanceUser[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingOnly, setPendingOnly] = useState(false);

  useEffect(() => {
    listInstanceUsers(pendingOnly ? "pending" : undefined)
      .then(setUsers)
      .catch((err) => setError(errorText(err, "Couldn't load users.")));
  }, [pendingOnly]);

  async function setApproval(target: InstanceUser, approve: boolean) {
    try {
      const updated = await (approve ? approveUser(target.id) : rejectUser(target.id));
      setUsers((prev) =>
        prev && (pendingOnly ? prev.filter((u) => u.id !== target.id) : prev.map((u) => (u.id === target.id ? updated : u))),
      );
      notify(`${target.email} ${approve ? "approved" : "rejected"}.`);
    } catch (err) {
      notify(errorText(err, "Couldn't update the user."), "error");
    }
  }

  async function handleDelete(target: InstanceUser) {
    if (!window.confirm(`Delete the account ${target.email}? Their conversations are deleted; their documents stay with their companies.`)) return;
    try {
      await deleteInstanceUser(target.id);
      setUsers((prev) => prev?.filter((u) => u.id !== target.id) ?? null);
      notify(`${target.email} deleted.`);
    } catch (err) {
      notify(errorText(err, "Couldn't delete the user."), "error");
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <label className="flex items-center gap-2 text-sm text-text-secondary">
        <input type="checkbox" checked={pendingOnly} onChange={(e) => setPendingOnly(e.target.checked)} />
        Pending approval only
      </label>
      {error && <p className="text-sm text-status-void">{error}</p>}
      {!users && !error && <p className="text-sm text-text-secondary">Loading users…</p>}
      {users && users.length === 0 && (
        <Card className="p-8 text-center text-sm text-text-secondary">{pendingOnly ? "No pending registrations." : "No users yet."}</Card>
      )}
      {users && users.length > 0 && (
        <Card className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className={THEAD}>
              <tr>
                <th className={TH}>User</th>
                <th className={TH}>Status</th>
                <th className={TH}>Companies</th>
                <th className={TH}>Registered</th>
                <th className={`${TH} text-right`}>Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {users.map((u) => (
                <tr key={u.id}>
                  <td className="px-4 py-3">
                    <div className="font-medium text-text-primary">
                      {u.displayName ?? "—"} {u.isInstanceAdmin && <span className="text-xs text-gold">instance admin</span>}
                    </div>
                    <div className="font-mono text-xs text-text-secondary">{u.email}</div>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={u.approvalStatus} />
                  </td>
                  <td className="px-4 py-3 text-xs text-text-secondary">
                    {u.companies.length === 0 ? "—" : u.companies.map((c) => `${c.name} (${c.role})`).join(", ")}
                  </td>
                  <td className="px-4 py-3 text-xs text-text-secondary">{new Date(u.createdAt).toLocaleDateString()}</td>
                  <td className="space-x-2 whitespace-nowrap px-4 py-3 text-right">
                    {u.approvalStatus !== "approved" && (
                      <Button className="h-8 px-3 text-xs" onClick={() => setApproval(u, true)}>
                        Approve
                      </Button>
                    )}
                    {u.id !== selfId && u.approvalStatus !== "rejected" && (
                      <Button variant="secondary" className="h-8 px-3 text-xs" onClick={() => setApproval(u, false)}>
                        Reject
                      </Button>
                    )}
                    {u.id !== selfId && (
                      <Button variant="danger" className="h-8 px-3 text-xs" onClick={() => handleDelete(u)}>
                        Delete
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}

function CompaniesTab({ notify }: { notify: Notify }) {
  const [companies, setCompanies] = useState<InstanceCompany[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listInstanceCompanies()
      .then(setCompanies)
      .catch((err) => setError(errorText(err, "Couldn't load companies.")));
  }, []);

  async function toggle(company: InstanceCompany) {
    const next = company.status === "active" ? "suspended" : "active";
    try {
      const updated = await setCompanyStatus(company.id, next);
      setCompanies((prev) => prev?.map((c) => (c.id === company.id ? updated : c)) ?? null);
      notify(`${company.name} ${next === "active" ? "reactivated" : "suspended"}.`);
    } catch (err) {
      notify(errorText(err, "Couldn't update the company."), "error");
    }
  }

  async function handleDelete(company: InstanceCompany) {
    if (window.prompt(`This permanently deletes ${company.name} and all its data. Type its name to confirm.`) !== company.name) return;
    try {
      await deleteInstanceCompany(company.id);
      setCompanies((prev) => prev?.filter((c) => c.id !== company.id) ?? null);
      notify(`${company.name} deleted.`);
    } catch (err) {
      notify(errorText(err, "Couldn't delete the company."), "error");
    }
  }

  if (error) return <p className="text-sm text-status-void">{error}</p>;
  if (!companies) return <p className="text-sm text-text-secondary">Loading companies…</p>;
  if (companies.length === 0) return <Card className="p-8 text-center text-sm text-text-secondary">No companies yet.</Card>;

  return (
    <Card className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className={THEAD}>
          <tr>
            <th className={TH}>Company</th>
            <th className={TH}>Status</th>
            <th className={TH}>Members</th>
            <th className={TH}>Created</th>
            <th className={`${TH} text-right`}>Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {companies.map((c) => (
            <tr key={c.id}>
              <td className="px-4 py-3">
                <div className="font-medium text-text-primary">{c.name}</div>
                <div className="font-mono text-xs text-text-secondary">/{c.slug}</div>
              </td>
              <td className="px-4 py-3">
                <StatusBadge status={c.status} />
              </td>
              <td className="px-4 py-3 text-text-primary">{c.memberCount}</td>
              <td className="px-4 py-3 text-xs text-text-secondary">{new Date(c.createdAt).toLocaleDateString()}</td>
              <td className="space-x-2 whitespace-nowrap px-4 py-3 text-right">
                <Button variant="secondary" className="h-8 px-3 text-xs" onClick={() => toggle(c)}>
                  {c.status === "active" ? "Suspend" : "Reactivate"}
                </Button>
                <Button variant="danger" className="h-8 px-3 text-xs" onClick={() => handleDelete(c)}>
                  Delete
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
