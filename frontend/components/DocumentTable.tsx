"use client";

import { useCallback, useEffect, useState } from "react";
import { deleteDocument, listDocuments, type Document } from "../lib/api";
import { StatusPill, Card, Input } from "./ui";

const POLL_INTERVAL_MS = 4000;

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString();
}

/* ── File-type icon: colored inline SVG by extension ── */

const EXT_COLORS: Record<string, string> = {
  pdf: "#EF4444",
  docx: "#3B82F6",
  doc: "#3B82F6",
  pptx: "#F97316",
  ppt: "#F97316",
  md: "#8B8B8E",
};

export function FileIcon({ filename }: { filename: string }) {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  const color = EXT_COLORS[ext] ?? "#8B8B8E";

  return (
    <svg width="20" height="24" viewBox="0 0 20 24" fill="none" className="shrink-0">
      <path
        d="M2 2a2 2 0 0 1 2-2h8l6 6v16a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V2Z"
        fill={color}
        fillOpacity="0.15"
      />
      <path
        d="M12 0l6 6h-4a2 2 0 0 1-2-2V0Z"
        fill={color}
        fillOpacity="0.3"
      />
      <text
        x="10"
        y="18"
        textAnchor="middle"
        fontSize="6"
        fontWeight="700"
        fill={color}
        fontFamily="var(--font-mono), monospace"
      >
        {ext.toUpperCase()}
      </text>
    </svg>
  );
}

/* ── Delete icon ── */

function IconTrash() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 4h12M5.333 4V2.667a1.333 1.333 0 0 1 1.334-1.334h2.666a1.333 1.333 0 0 1 1.334 1.334V4M12.667 4v9.333a1.333 1.333 0 0 1-1.334 1.334H4.667a1.333 1.333 0 0 1-1.334-1.334V4" />
    </svg>
  );
}

export function DocumentTable({ refreshSignal }: { refreshSignal: number }) {
  const [documents, setDocuments] = useState<Document[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const refetch = useCallback(() => {
    listDocuments()
      .then((docs) => {
        setDocuments(docs);
        setLoadError(null);
      })
      .catch((err) => setLoadError(err instanceof Error ? err.message : "Couldn't load documents."));
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch, refreshSignal]);

  useEffect(() => {
    if (!documents?.some((doc) => doc.status === "processing")) return;
    const interval = setInterval(refetch, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [documents, refetch]);

  async function handleDelete(id: string, filename: string) {
    if (!window.confirm(`Delete "${filename}"? This can't be undone.`)) return;
    setDeletingId(id);
    setDeleteError(null);
    try {
      await deleteDocument(id);
      setDocuments((prev) => prev?.filter((doc) => doc.id !== id) ?? null);
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Couldn't delete document.");
    } finally {
      setDeletingId(null);
    }
  }

  if (loadError) {
    return <p className="text-sm text-status-void">{loadError}</p>;
  }
  if (documents === null) {
    return <p className="text-sm text-text-secondary">Loading…</p>;
  }
  if (documents.length === 0) {
    return <p className="text-sm text-text-secondary">No documents yet. Upload one above.</p>;
  }

  const filtered = searchQuery
    ? documents.filter((doc) => doc.filename.toLowerCase().includes(searchQuery.toLowerCase()))
    : documents;

  return (
    <div className="space-y-3">
      {/* Search filter */}
      <div className="relative">
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary"
        >
          <circle cx="7" cy="7" r="4.5" />
          <path d="m10.5 10.5 3 3" />
        </svg>
        <Input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search documents..."
          className="pl-9"
        />
      </div>

      {deleteError && <p className="text-sm text-status-void">{deleteError}</p>}

      {/* Document list */}
      <div className="space-y-2">
        {filtered.length === 0 ? (
          <p className="py-4 text-center text-sm text-text-secondary">No documents match your search.</p>
        ) : (
          filtered.map((doc) => (
            <Card key={doc.id} className="group flex items-center gap-3 px-4 py-3 transition-colors duration-120 hover:border-border-hover">
              <FileIcon filename={doc.filename} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-text-primary">{doc.filename}</p>
                <div className="mt-0.5 flex flex-wrap items-center gap-2">
                  <StatusPill status={doc.status} />
                  <span className="text-xs text-text-secondary">
                    {doc.visibility === "department" ? doc.department ?? "department" : "Company-wide"}
                  </span>
                  <span className="font-mono text-xs text-text-secondary">{formatDate(doc.createdAt)}</span>
                </div>
                {doc.status === "failed" && doc.errorMessage && (
                  <p className="mt-1 text-xs text-status-void">{doc.errorMessage}</p>
                )}
              </div>
              <button
                type="button"
                onClick={() => handleDelete(doc.id, doc.filename)}
                disabled={deletingId === doc.id}
                className="shrink-0 rounded-lg p-2 text-text-secondary opacity-0 transition-all duration-120 hover:bg-surface-overlay hover:text-status-void focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold group-hover:opacity-100 disabled:opacity-50"
                aria-label={`Delete ${doc.filename}`}
                title="Delete"
              >
                {deletingId === doc.id ? (
                  <span className="text-xs">…</span>
                ) : (
                  <IconTrash />
                )}
              </button>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}
