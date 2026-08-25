"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ADMIN_REQUIRED,
  activateCompany,
  approveUser,
  getStats,
  listCompanies,
  listPendingUsers,
  rejectUser,
  suspendCompany,
  type Stats,
  type SuperadminCompany,
  type SuperadminUser,
} from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";
import { BarChart, Button, Card, Toast, type ToastVariant } from "@/components/ui";

function formatUsd(value: number): string {
  return `$${value.toFixed(4)}`;
}

type TabKey = "pending" | "companies" | "stats" | "team";

interface TabItem {
  id: TabKey;
  label: string;
}

export default function AdminPage() {
  const router = useRouter();
  const { isSuperAdmin, isAdmin, isReady } = useAuth();

  // Tab State
  const availableTabs: TabItem[] = isSuperAdmin
    ? [
        { id: "pending", label: "Pending Approvals" },
        { id: "companies", label: "Companies" },
        { id: "stats", label: "Stats" },
        { id: "team", label: "Team" },
      ]
    : [
        { id: "stats", label: "Stats" },
        { id: "team", label: "Team" },
      ];

  const defaultTab: TabKey = isSuperAdmin ? "pending" : "stats";
  const [activeTab, setActiveTab] = useState<TabKey>(defaultTab);

  // Toast feedback state
  const [toast, setToast] = useState<{ message: string | null; variant: ToastVariant }>({
    message: null,
    variant: "success",
  });

  const showToast = (message: string, variant: ToastVariant = "success") => {
    setToast({ message, variant });
  };

  const dismissToast = () => {
    setToast({ message: null, variant: "success" });
  };

  // Stats tab data
  const [stats, setStats] = useState<Stats | null>(null);
  const [statsError, setStatsError] = useState<string | null>(null);

  // Pending Approvals tab data
  const [pendingUsers, setPendingUsers] = useState<SuperadminUser[] | null>(null);
  const [pendingLoading, setPendingLoading] = useState(false);
  const [pendingError, setPendingError] = useState<string | null>(null);

  // Companies tab data
  const [companies, setCompanies] = useState<SuperadminCompany[] | null>(null);
  const [companiesLoading, setCompaniesLoading] = useState(false);
  const [companiesError, setCompaniesError] = useState<string | null>(null);

  // Keep activeTab aligned if role loads after initial render
  useEffect(() => {
    if (isSuperAdmin && activeTab === "stats" && !availableTabs.some((t) => t.id === activeTab)) {
      setActiveTab("pending");
    }
  }, [isSuperAdmin, activeTab, availableTabs]);

  // Auth gate check
  useEffect(() => {
    if (isReady && !isAdmin) {
      router.replace("/");
    }
  }, [isReady, isAdmin, router]);

  // Load data based on active tab
  useEffect(() => {
    if (!isAdmin) return;

    if (activeTab === "stats" && !stats) {
      getStats()
        .then(setStats)
        .catch((err) => {
          if (err instanceof Error && err.message === ADMIN_REQUIRED) {
            router.replace("/");
            return;
          }
          setStatsError(err instanceof Error ? err.message : "Couldn't load stats.");
        });
    } else if (activeTab === "pending" && isSuperAdmin && !pendingUsers) {
      setPendingLoading(true);
      listPendingUsers()
        .then((users) => {
          setPendingUsers(users);
          setPendingError(null);
        })
        .catch((err) => {
          setPendingError(err instanceof Error ? err.message : "Failed to load pending registrations.");
        })
        .finally(() => setPendingLoading(false));
    } else if (activeTab === "companies" && isSuperAdmin && !companies) {
      setCompaniesLoading(true);
      listCompanies()
        .then((data) => {
          setCompanies(data);
          setCompaniesError(null);
        })
        .catch((err) => {
          setCompaniesError(err instanceof Error ? err.message : "Failed to load companies.");
        })
        .finally(() => setCompaniesLoading(false));
    }
  }, [activeTab, isAdmin, isSuperAdmin, router, stats, pendingUsers, companies]);

  // Superadmin Actions: Pending Approvals
  const handleApprove = async (userId: string) => {
    if (!pendingUsers) return;
    const previous = [...pendingUsers];
    const userToApprove = pendingUsers.find((u) => u.id === userId);
    setPendingUsers(pendingUsers.filter((u) => u.id !== userId));

    try {
      await approveUser(userId);
      showToast(
        userToApprove?.companyName
          ? `Registration for "${userToApprove.companyName}" approved.`
          : "Registration approved.",
        "success",
      );
    } catch (err) {
      setPendingUsers(previous);
      showToast(
        err instanceof Error ? err.message : "Failed to approve registration.",
        "error",
      );
    }
  };

  const handleReject = async (userId: string) => {
    if (!pendingUsers) return;
    const previous = [...pendingUsers];
    const userToReject = pendingUsers.find((u) => u.id === userId);
    setPendingUsers(pendingUsers.filter((u) => u.id !== userId));

    try {
      await rejectUser(userId);
      showToast(
        userToReject?.companyName
          ? `Registration for "${userToReject.companyName}" rejected.`
          : "Registration rejected.",
        "success",
      );
    } catch (err) {
      setPendingUsers(previous);
      showToast(
        err instanceof Error ? err.message : "Failed to reject registration.",
        "error",
      );
    }
  };

  // Superadmin Actions: Companies
  const handleToggleCompany = async (company: SuperadminCompany) => {
    if (!companies) return;
    const previous = [...companies];
    const targetStatus = company.status === "active" ? "suspended" : "active";

    setCompanies(
      companies.map((c) => (c.id === company.id ? { ...c, status: targetStatus } : c)),
    );

    try {
      if (company.status === "active") {
        await suspendCompany(company.id);
        showToast(`Company "${company.name}" has been suspended.`, "success");
      } else {
        await activateCompany(company.id);
        showToast(`Company "${company.name}" has been activated.`, "success");
      }
    } catch (err) {
      setCompanies(previous);
      showToast(
        err instanceof Error ? err.message : `Failed to update status for "${company.name}".`,
        "error",
      );
    }
  };

  return (
    <div className="flex flex-1 flex-col gap-6 overflow-y-auto bg-surface-primary px-4 pb-6 pt-16 md:px-6 md:pt-6">
      <div>
        <h1 className="text-lg font-semibold text-text-primary">Admin</h1>
        <p className="mt-1 text-sm text-text-secondary">
          {isSuperAdmin
            ? "Platform administration and organization management."
            : "Usage across the vault, last 30 days."}
        </p>
      </div>

      {/* Horizontal Tabs Bar */}
      <div className="flex border-b border-border">
        {availableTabs.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`relative px-4 py-2.5 text-sm font-medium transition-colors focus:outline-none ${
                isActive
                  ? "font-semibold text-gold"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              {tab.label}
              {isActive && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-gold" />
              )}
            </button>
          );
        })}
      </div>

      {/* Tab Contents: Stats */}
      {activeTab === "stats" && (
        <div className="flex flex-col gap-6">
          {statsError && <p className="text-sm text-status-void">{statsError}</p>}

          {!stats && !statsError && <p className="text-sm text-text-secondary">Loading stats…</p>}

          {stats && (
            <>
              <div className="grid gap-4 sm:grid-cols-2">
                <Card className="p-4">
                  <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-secondary">Documents filed</p>
                  <p className="mt-1 text-2xl font-semibold text-text-primary">{stats.documentCount}</p>
                </Card>
                <Card className="p-4">
                  <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-secondary">Estimated cost</p>
                  <p className="mt-1 text-2xl font-semibold text-text-primary">
                    {formatUsd(stats.estimatedCostUsd)}
                  </p>
                </Card>
              </div>

              <Card className="p-4">
                <h2 className="mb-3 text-sm font-semibold text-text-primary">Messages per day</h2>
                <BarChart data={stats.messagesPerDay.map(({ date, count }) => ({ label: date, value: count }))} />
              </Card>

              <Card className="p-4">
                <h2 className="mb-3 text-sm font-semibold text-text-primary">Documents per user</h2>
                <BarChart
                  data={stats.documentsPerUser.map(({ email, count }) => ({ label: email, value: count }))}
                  emptyMessage="Nobody has uploaded anything yet."
                />
              </Card>

              <Card className="p-4">
                <h2 className="mb-3 text-sm font-semibold text-text-primary">Cost over time</h2>
                <BarChart
                  data={stats.costPerDay.map(({ date, costUsd }) => ({ label: date, value: costUsd }))}
                  formatValue={formatUsd}
                />
              </Card>
            </>
          )}
        </div>
      )}

      {/* Tab Contents: Pending Approvals (Superadmin) */}
      {activeTab === "pending" && (
        <div className="flex flex-col gap-4">
          {pendingError && <p className="text-sm text-status-void">{pendingError}</p>}
          {pendingLoading && !pendingUsers && (
            <p className="text-sm text-text-secondary">Loading pending registrations…</p>
          )}

          {pendingUsers && pendingUsers.length === 0 && (
            <Card className="p-8 text-center text-text-secondary">
              <p className="text-sm">No pending registrations.</p>
            </Card>
          )}

          {pendingUsers && pendingUsers.length > 0 && (
            <Card className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-border bg-surface-raised text-xs font-medium uppercase tracking-[0.06em] text-text-secondary">
                  <tr>
                    <th className="px-4 py-3">Company Name</th>
                    <th className="px-4 py-3">Admin Name</th>
                    <th className="px-4 py-3">Email</th>
                    <th className="px-4 py-3">Registered Date</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {pendingUsers.map((user) => (
                    <tr key={user.id} className="transition-colors hover:bg-surface-raised/50">
                      <td className="px-4 py-3 font-medium text-text-primary">
                        {user.companyName ?? "—"}
                      </td>
                      <td className="px-4 py-3 text-text-primary">{user.displayName ?? "—"}</td>
                      <td className="px-4 py-3 font-mono text-xs text-text-secondary">{user.email}</td>
                      <td className="px-4 py-3 text-xs text-text-secondary">
                        {new Date(user.createdAt).toLocaleDateString()}
                      </td>
                      <td className="space-x-2 px-4 py-3 text-right">
                        <Button
                          variant="primary"
                          className="h-8 px-3 text-xs"
                          onClick={() => handleApprove(user.id)}
                        >
                          Approve
                        </Button>
                        <Button
                          variant="danger"
                          className="h-8 px-3 text-xs"
                          onClick={() => handleReject(user.id)}
                        >
                          Reject
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}
        </div>
      )}

      {/* Tab Contents: Companies (Superadmin) */}
      {activeTab === "companies" && (
        <div className="flex flex-col gap-4">
          {companiesError && <p className="text-sm text-status-void">{companiesError}</p>}
          {companiesLoading && !companies}

          {companies && companies.length === 0 && (
            <Card className="p-8 text-center text-text-secondary">
              <p className="text-sm">No companies registered yet.</p>
            </Card>
          )}

          {companies && companies.length > 0 && (
            <Card className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-border bg-surface-raised text-xs font-medium uppercase tracking-[0.06em] text-text-secondary">
                  <tr>
                    <th className="px-4 py-3">Company Name</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Created Date</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {companies.map((company) => {
                    const isActive = company.status === "active";
                    return (
                      <tr key={company.id} className="transition-colors hover:bg-surface-raised/50">
                        <td className="px-4 py-3 font-medium text-text-primary">{company.name}</td>
                        <td className="px-4 py-3">
                          <span
                            className={`inline-flex items-center rounded-full px-2.5 py-0.5 font-mono text-[10px] font-medium uppercase tracking-[0.08em] ${
                              isActive
                                ? "bg-status-ready-bg text-status-ready"
                                : "bg-status-void-bg text-status-void"
                            }`}
                          >
                            {isActive ? "Active" : "Suspended"}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-xs text-text-secondary">
                          {new Date(company.createdAt).toLocaleDateString()}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <Button
                            variant="secondary"
                            className={`h-8 px-3 text-xs ${
                              isActive
                                ? "hover:border-status-void/50 hover:text-status-void"
                                : "hover:border-status-ready/50 hover:text-status-ready"
                            }`}
                            onClick={() => handleToggleCompany(company)}
                          >
                            {isActive ? "Suspend" : "Activate"}
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </Card>
          )}
        </div>
      )}

      {/* Tab Contents: Team (Placeholder for #101/#102) */}
      {activeTab === "team" && (
        <Card className="p-8 text-center text-text-secondary">
          <p className="text-sm">Team member and department management will appear here.</p>
        </Card>
      )}

      {/* Toast Feedback */}
      <Toast message={toast.message} variant={toast.variant} onDismiss={dismissToast} />
    </div>
  );
}
