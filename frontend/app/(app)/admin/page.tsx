"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ADMIN_REQUIRED, getStats, type Stats } from "@/lib/api";
import { BarChart, Card } from "@/components/ui";

function formatUsd(value: number): string {
  return `$${value.toFixed(4)}`;
}

export default function AdminPage() {
  const router = useRouter();
  const [stats, setStats] = useState<Stats | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    getStats()
      .then(setStats)
      .catch((err) => {
        // Members are bounced by the API's 403, not by a client-side role check.
        if (err instanceof Error && err.message === ADMIN_REQUIRED) {
          router.replace("/");
          return;
        }
        setLoadError(err instanceof Error ? err.message : "Couldn't load stats.");
      });
  }, [router]);

  return (
    <div className="flex flex-1 flex-col gap-6 overflow-y-auto bg-paper px-4 pb-6 pt-16 md:px-6 md:pt-6">
      <div>
        <h1 className="font-serif text-lg font-semibold text-ink">Admin</h1>
        <p className="mt-1 text-sm text-ink-muted">Usage across the vault, last 30 days.</p>
      </div>

      {loadError && <p className="text-sm text-stamp-void">{loadError}</p>}

      {!stats && !loadError && <p className="text-sm text-ink-muted">Loading stats…</p>}

      {stats && (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            <Card className="p-4">
              <p className="text-xs uppercase tracking-[0.08em] text-ink-muted">Documents filed</p>
              <p className="mt-1 font-serif text-2xl font-semibold text-ink">{stats.documentCount}</p>
            </Card>
            <Card className="p-4">
              <p className="text-xs uppercase tracking-[0.08em] text-ink-muted">Estimated cost</p>
              <p className="mt-1 font-serif text-2xl font-semibold text-ink">
                {formatUsd(stats.estimatedCostUsd)}
              </p>
            </Card>
          </div>

          <Card className="p-4">
            <h2 className="mb-3 font-serif text-sm font-semibold text-ink">Messages per day</h2>
            <BarChart data={stats.messagesPerDay.map(({ date, count }) => ({ label: date, value: count }))} />
          </Card>

          <Card className="p-4">
            <h2 className="mb-3 font-serif text-sm font-semibold text-ink">Documents per user</h2>
            <BarChart
              data={stats.documentsPerUser.map(({ email, count }) => ({ label: email, value: count }))}
              emptyMessage="Nobody has uploaded anything yet."
            />
          </Card>

          <Card className="p-4">
            <h2 className="mb-3 font-serif text-sm font-semibold text-ink">Cost over time</h2>
            <BarChart
              data={stats.costPerDay.map(({ date, costUsd }) => ({ label: date, value: costUsd }))}
              formatValue={formatUsd}
            />
          </Card>
        </>
      )}
    </div>
  );
}
