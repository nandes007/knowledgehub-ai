"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  createDepartment,
  createInvite,
  deleteCompany,
  deleteDepartment,
  getStats,
  inviteLink,
  listDepartments,
  listInvites,
  listMembers,
  removeMember,
  renameCompany,
  revokeInvite,
  transferOwnership,
  updateMember,
  type Department,
  type Invite,
  type Member,
} from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";
import { useCompany } from "@/components/CompanyProvider";
import { Button, Card, Input, Label, Tabs, Toast, type ToastVariant } from "@/components/ui";
import { StatsPanel } from "@/components/StatsPanel";

type TabKey = "stats" | "members" | "departments" | "settings";
type Notify = (message: string, variant?: ToastVariant) => void;

const SELECT_CLASS =
  "h-9 rounded-lg border border-border bg-surface-input px-2 text-sm text-text-primary focus:border-gold focus:outline-none disabled:opacity-50";
const TH = "px-4 py-3";
const THEAD =
  "border-b border-border bg-surface-raised text-xs font-medium uppercase tracking-[0.06em] text-text-secondary";

function errorText(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback;
}

export default function CompanyAdminPage() {
  const router = useRouter();
  const { slug, company, isAdmin, isOwner } = useCompany();
  const [activeTab, setActiveTab] = useState<TabKey>("stats");
  const [toast, setToast] = useState<{ message: string | null; variant: ToastVariant }>({
    message: null,
    variant: "success",
  });
  const notify: Notify = useCallback((message, variant = "success") => setToast({ message, variant }), []);

  // Members never see this page; the API refuses them regardless.
  useEffect(() => {
    if (!isAdmin) router.replace(`/${slug}`);
  }, [isAdmin, router, slug]);
  if (!isAdmin) return null;

  const tabs: { id: TabKey; label: string }[] = [
    { id: "stats", label: "Stats" },
    { id: "members", label: "Members" },
    { id: "departments", label: "Departments" },
    ...(isOwner ? [{ id: "settings" as const, label: "Settings" }] : []),
  ];

  return (
    <div className="flex flex-1 flex-col gap-6 overflow-y-auto bg-surface-primary px-4 pb-6 pt-16 md:px-6 md:pt-6">
      <div>
        <h1 className="text-lg font-semibold text-text-primary">Admin</h1>
        <p className="mt-1 text-sm text-text-secondary">Manage {company.name}.</p>
      </div>

      <Tabs tabs={tabs} active={activeTab} onChange={setActiveTab} />

      {activeTab === "stats" && <StatsPanel load={() => getStats(slug)} />}
      {activeTab === "members" && <MembersTab notify={notify} />}
      {activeTab === "departments" && <DepartmentsTab notify={notify} />}
      {activeTab === "settings" && isOwner && <SettingsTab notify={notify} />}

      <Toast message={toast.message} variant={toast.variant} onDismiss={() => setToast({ message: null, variant: "success" })} />
    </div>
  );
}

function MembersTab({ notify }: { notify: Notify }) {
  const { slug, isOwner } = useCompany();
  const { user, refreshUser } = useAuth();
  const [members, setMembers] = useState<Member[] | null>(null);
  const [invites, setInvites] = useState<Invite[] | null>(null);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"member" | "admin">("member");
  const [departmentId, setDepartmentId] = useState("");
  const [isInviting, setIsInviting] = useState(false);
  const [newLink, setNewLink] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([listMembers(slug), listInvites(slug), listDepartments(slug)])
      .then(([m, i, d]) => {
        setMembers(m);
        setInvites(i);
        setDepartments(d);
      })
      .catch((err) => setLoadError(errorText(err, "Couldn't load members.")));
  }, [slug]);

  // The owner manages everyone; an admin manages members only.
  const canManage = (m: Member) => isOwner || m.role === "member";

  async function handleInvite(event: React.FormEvent) {
    event.preventDefault();
    setIsInviting(true);
    setNewLink(null);
    try {
      const invite = await createInvite(slug, { email: email.trim(), role, departmentId: departmentId || null });
      const { token, ...rest } = invite;
      setInvites((prev) => [rest, ...(prev ?? []).filter((i) => i.email !== rest.email)]);
      setNewLink(inviteLink(token));
      setEmail("");
    } catch (err) {
      notify(errorText(err, "Couldn't create the invite."), "error");
    } finally {
      setIsInviting(false);
    }
  }

  async function copyLink() {
    if (!newLink) return;
    try {
      await navigator.clipboard.writeText(newLink);
      notify("Invite link copied.");
    } catch {
      notify("Couldn't copy. Select the link and copy it manually.", "error");
    }
  }

  async function handleRevoke(invite: Invite) {
    try {
      await revokeInvite(slug, invite.id);
      setInvites((prev) => prev?.filter((i) => i.id !== invite.id) ?? null);
      notify(`Invite for ${invite.email} revoked.`);
    } catch (err) {
      notify(errorText(err, "Couldn't revoke the invite."), "error");
    }
  }

  async function handleUpdate(member: Member, changes: { role?: "admin" | "member"; departmentId?: string | null }) {
    try {
      const updated = await updateMember(slug, member.userId, changes);
      setMembers((prev) => prev?.map((m) => (m.userId === updated.userId ? updated : m)) ?? null);
      notify(`${member.displayName ?? member.email} updated.`);
    } catch (err) {
      notify(errorText(err, "Couldn't update the member."), "error");
    }
  }

  async function handleRemove(member: Member) {
    const name = member.displayName ?? member.email;
    if (!window.confirm(`Remove ${name}? Their documents stay; their conversations here are deleted.`)) return;
    try {
      await removeMember(slug, member.userId);
      setMembers((prev) => prev?.filter((m) => m.userId !== member.userId) ?? null);
      notify(`${name} removed.`);
    } catch (err) {
      notify(errorText(err, "Couldn't remove the member."), "error");
    }
  }

  async function handleTransfer(member: Member) {
    const name = member.displayName ?? member.email;
    if (!window.confirm(`Make ${name} the owner? You will become an admin.`)) return;
    try {
      await transferOwnership(slug, member.userId);
      notify(`${name} is now the owner.`);
      // Your own role just changed; the page re-renders from the refreshed membership.
      await refreshUser();
      setMembers(await listMembers(slug));
    } catch (err) {
      notify(errorText(err, "Couldn't transfer ownership."), "error");
    }
  }

  if (loadError) return <p className="text-sm text-status-void">{loadError}</p>;
  if (!members || !invites) return <p className="text-sm text-text-secondary">Loading members…</p>;

  return (
    <div className="flex flex-col gap-6">
      <Card className="space-y-4 p-4">
        <div>
          <h2 className="text-sm font-semibold text-text-primary">Invite someone</h2>
          <p className="text-xs text-text-secondary">
            You get a link to send them. It works only for that email, once, for 7 days.
          </p>
        </div>
        <form onSubmit={handleInvite} className="grid gap-3 sm:grid-cols-[1fr_auto_auto_auto] sm:items-end">
          <div className="space-y-1">
            <Label htmlFor="invite-email">Email</Label>
            <Input id="invite-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="invite-role">Role</Label>
            <select
              id="invite-role"
              className={`${SELECT_CLASS} block h-10 w-full`}
              value={role}
              onChange={(e) => setRole(e.target.value as "member" | "admin")}
            >
              <option value="member">Member</option>
              {isOwner && <option value="admin">Admin</option>}
            </select>
          </div>
          <div className="space-y-1">
            <Label htmlFor="invite-department">Department</Label>
            <select
              id="invite-department"
              className={`${SELECT_CLASS} block h-10 w-full`}
              value={departmentId}
              onChange={(e) => setDepartmentId(e.target.value)}
            >
              <option value="">None</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>
          <Button type="submit" disabled={isInviting} className="h-10">
            {isInviting ? "Creating…" : "Create invite link"}
          </Button>
        </form>
        {newLink && (
          <div className="flex flex-col gap-2 sm:flex-row">
            <Input readOnly value={newLink} aria-label="Invite link" onFocus={(e) => e.target.select()} className="font-mono text-xs" />
            <Button type="button" variant="secondary" onClick={copyLink}>
              Copy link
            </Button>
          </div>
        )}
      </Card>

      {invites.length > 0 && (
        <Card className="overflow-x-auto">
          <h2 className="px-4 pt-4 text-sm font-semibold text-text-primary">Pending invites</h2>
          <table className="mt-3 w-full text-left text-sm">
            <thead className={THEAD}>
              <tr>
                <th className={TH}>Email</th>
                <th className={TH}>Role</th>
                <th className={TH}>Expires</th>
                <th className={`${TH} text-right`}>Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {invites.map((invite) => (
                <tr key={invite.id}>
                  <td className="px-4 py-3 font-mono text-xs text-text-secondary">{invite.email}</td>
                  <td className="px-4 py-3 capitalize text-text-primary">{invite.role}</td>
                  <td className="px-4 py-3 text-xs text-text-secondary">{new Date(invite.expiresAt).toLocaleDateString()}</td>
                  <td className="px-4 py-3 text-right">
                    <Button variant="danger" className="h-8 px-3 text-xs" onClick={() => handleRevoke(invite)}>
                      Revoke
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      <Card className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className={THEAD}>
            <tr>
              <th className={TH}>Member</th>
              <th className={TH}>Role</th>
              <th className={TH}>Department</th>
              <th className={`${TH} text-right`}>Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {members.map((member) => {
              const isSelf = member.userId === user?.id;
              const editable = isSelf || canManage(member);
              return (
                <tr key={member.userId}>
                  <td className="px-4 py-3">
                    <div className="font-medium text-text-primary">
                      {member.displayName ?? "—"} {isSelf && <span className="text-xs text-text-tertiary">(you)</span>}
                    </div>
                    <div className="font-mono text-xs text-text-secondary">{member.email}</div>
                  </td>
                  <td className="px-4 py-3">
                    {/* Only the owner changes roles, never their own, and ownership moves by transfer. */}
                    {isOwner && !isSelf && member.role !== "owner" ? (
                      <select
                        aria-label={`Role of ${member.email}`}
                        className={SELECT_CLASS}
                        value={member.role}
                        onChange={(e) => handleUpdate(member, { role: e.target.value as "admin" | "member" })}
                      >
                        <option value="member">Member</option>
                        <option value="admin">Admin</option>
                      </select>
                    ) : (
                      <span className="capitalize text-text-primary">{member.role}</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <select
                      aria-label={`Department of ${member.email}`}
                      className={SELECT_CLASS}
                      disabled={!editable}
                      value={member.departmentId ?? ""}
                      onChange={(e) => handleUpdate(member, { departmentId: e.target.value || null })}
                    >
                      <option value="">None</option>
                      {departments.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.name}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="space-x-2 whitespace-nowrap px-4 py-3 text-right">
                    {isOwner && !isSelf && (
                      <Button variant="secondary" className="h-8 px-3 text-xs" onClick={() => handleTransfer(member)}>
                        Make owner
                      </Button>
                    )}
                    {!isSelf && member.role !== "owner" && canManage(member) && (
                      <Button variant="danger" className="h-8 px-3 text-xs" onClick={() => handleRemove(member)}>
                        Remove
                      </Button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

function DepartmentsTab({ notify }: { notify: Notify }) {
  const { slug } = useCompany();
  const [departments, setDepartments] = useState<Department[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [name, setName] = useState("");

  useEffect(() => {
    listDepartments(slug)
      .then(setDepartments)
      .catch((err) => setLoadError(errorText(err, "Couldn't load departments.")));
  }, [slug]);

  async function handleAdd(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    try {
      const created = await createDepartment(slug, trimmed);
      setDepartments((prev) => [...(prev ?? []), created]);
      setName("");
      notify(`Department "${trimmed}" created.`);
    } catch (err) {
      notify(errorText(err, "Couldn't create the department."), "error");
    }
  }

  async function handleDelete(department: Department) {
    try {
      await deleteDepartment(slug, department.id);
      setDepartments((prev) => prev?.filter((d) => d.id !== department.id) ?? null);
      notify(`Department "${department.name}" deleted.`);
    } catch (err) {
      notify(errorText(err, "Couldn't delete the department."), "error");
    }
  }

  if (loadError) return <p className="text-sm text-status-void">{loadError}</p>;
  if (!departments) return <p className="text-sm text-text-secondary">Loading departments…</p>;

  return (
    <Card className="space-y-4 p-4">
      <p className="text-xs text-text-secondary">
        Members see company-wide documents plus those of their own department.
      </p>
      <form onSubmit={handleAdd} className="flex gap-2">
        <Input aria-label="New department name" placeholder="e.g. Engineering" value={name} onChange={(e) => setName(e.target.value)} />
        <Button type="submit">Add</Button>
      </form>
      {departments.length === 0 ? (
        <p className="text-sm text-text-tertiary">No departments yet.</p>
      ) : (
        <ul className="divide-y divide-border">
          {departments.map((d) => (
            <li key={d.id} className="flex items-center justify-between py-2 text-sm text-text-primary">
              {d.name}
              <Button variant="danger" className="h-8 px-3 text-xs" onClick={() => handleDelete(d)}>
                Delete
              </Button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function SettingsTab({ notify }: { notify: Notify }) {
  const { slug, company } = useCompany();
  const { refreshUser } = useAuth();
  const router = useRouter();
  const [name, setName] = useState(company.name);
  const [confirmName, setConfirmName] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);

  async function handleRename(event: React.FormEvent) {
    event.preventDefault();
    try {
      await renameCompany(slug, name.trim());
      await refreshUser();
      notify("Company renamed. Its URL stays the same.");
    } catch (err) {
      notify(errorText(err, "Couldn't rename the company."), "error");
    }
  }

  async function handleDelete() {
    setIsDeleting(true);
    try {
      await deleteCompany(slug);
      await refreshUser();
      router.replace("/");
    } catch (err) {
      notify(errorText(err, "Couldn't delete the company."), "error");
      setIsDeleting(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <Card className="space-y-3 p-4">
        <h2 className="text-sm font-semibold text-text-primary">Company name</h2>
        <form onSubmit={handleRename} className="flex gap-2">
          <Input aria-label="Company name" required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} />
          <Button type="submit" disabled={!name.trim() || name.trim() === company.name}>
            Rename
          </Button>
        </form>
        <p className="text-xs text-text-tertiary">
          The URL keeps using <span className="font-mono">/{slug}</span>, so existing links keep working.
        </p>
      </Card>

      <Card className="space-y-3 border-status-void/40 p-4">
        <h2 className="text-sm font-semibold text-status-void">Delete company</h2>
        <p className="text-xs text-text-secondary">
          Permanently deletes all of its documents, conversations, departments, members and invites.
          To leave instead, make someone else the owner on the Members tab first.
        </p>
        <Label htmlFor="confirm-delete">Type {company.name} to confirm</Label>
        <div className="flex gap-2">
          <Input id="confirm-delete" value={confirmName} onChange={(e) => setConfirmName(e.target.value)} />
          <Button
            type="button"
            className="bg-status-void text-white hover:bg-status-void/90"
            disabled={confirmName !== company.name || isDeleting}
            onClick={handleDelete}
          >
            {isDeleting ? "Deleting…" : "Delete"}
          </Button>
        </div>
      </Card>
    </div>
  );
}
