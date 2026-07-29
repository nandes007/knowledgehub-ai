"use client";

import { useCallback, useEffect, useState } from "react";
import { deleteDocument, listDocuments, type Document } from "@/lib/api";
import { StatusStamp } from "@/components/ui";

const POLL_INTERVAL_MS = 4000;

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString();
}

export function DocumentTable({ refreshSignal }: { refreshSignal: number }) {
  const [documents, setDocuments] = useState<Document[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

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
    return <p className="text-sm text-stamp-void">{loadError}</p>;
  }
  if (documents === null) {
    return <p className="text-sm text-ink-muted">Loading…</p>;
  }
  if (documents.length === 0) {
    return <p className="text-sm text-ink-muted">No documents yet. Upload one above.</p>;
  }

  return (
    <div>
      {deleteError && <p className="mb-2 text-sm text-stamp-void">{deleteError}</p>}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-rule text-ink-muted">
              <th className="py-2 pr-4 font-medium">Filename</th>
              <th className="py-2 pr-4 font-medium">Status</th>
              <th className="py-2 pr-4 font-medium">Visibility</th>
              <th className="py-2 pr-4 font-medium">Uploaded</th>
              <th className="py-2 font-medium" aria-hidden />
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => (
              <tr key={doc.id} className="border-b border-rule">
                <td className="max-w-xs truncate py-2 pr-4">{doc.filename}</td>
                <td className="py-2 pr-4">
                  <StatusStamp status={doc.status} />
                  {doc.status === "failed" && doc.errorMessage && (
                    <p className="mt-1 max-w-xs text-xs text-stamp-void">{doc.errorMessage}</p>
                  )}
                </td>
                <td className="py-2 pr-4 text-xs text-ink-muted">
                  {doc.visibility === "department" ? doc.department ?? "department" : "Company-wide"}
                </td>
                <td className="py-2 pr-4 font-mono text-xs text-ink-muted">{formatDate(doc.createdAt)}</td>
                <td className="py-2 text-right">
                  <button
                    type="button"
                    onClick={() => handleDelete(doc.id, doc.filename)}
                    disabled={deletingId === doc.id}
                    className="rounded-sm text-stamp-void hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass focus-visible:ring-offset-2 focus-visible:ring-offset-paper disabled:opacity-50"
                  >
                    {deletingId === doc.id ? "Deleting…" : "Delete"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
