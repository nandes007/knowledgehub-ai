"use client";

import { useEffect, useState } from "react";
import type { Stats } from "@/lib/api";
import { BarChart, Card } from "./ui";

function formatUsd(value: number): string {
  return `$${value.toFixed(4)}`;
}

// Usage for one company or for the whole instance, depending on what `load` fetches.
export function StatsPanel({ load }: { load: () => Promise<Stats> }) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Loaded once on mount; callers pass a fresh closure every render.
  useEffect(() => {
    load()
      .then(setStats)
      .catch((err) => setError(err instanceof Error ? err.message : "Couldn't load stats."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (error) return <p className="text-sm text-status-void">{error}</p>;
  if (!stats) return <p className="text-sm text-text-secondary">Loading stats…</p>;

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 sm:grid-cols-2">
        <Card className="p-4">
          <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-secondary">Documents filed</p>
          <p className="mt-1 text-2xl font-semibold text-text-primary">{stats.documentCount}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs font-medium uppercase tracking-[0.08em] text-text-secondary">Estimated cost</p>
          <p className="mt-1 text-2xl font-semibold text-text-primary">{formatUsd(stats.estimatedCostUsd)}</p>
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
        <BarChart data={stats.costPerDay.map(({ date, costUsd }) => ({ label: date, value: costUsd }))} formatValue={formatUsd} />
      </Card>
    </div>
  );
}
