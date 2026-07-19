"use client";

import { useCallback, useEffect, useState } from "react";
import { deleteDocument, listDocuments, type Document, type DocumentStatus } from "@/lib/api";

const POLL_INTERVAL_MS = 4000;

const STATUS_STYLES: Record<DocumentStatus, string> = {
  processing: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  ready: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  failed: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
};

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
    return <p className="text-sm text-red-600 dark:text-red-400">{loadError}</p>;
  }
  if (documents === null) {
    return <p className="text-sm text-zinc-500 dark:text-zinc-400">Loading…</p>;
  }
  if (documents.length === 0) {
    return <p className="text-sm text-zinc-500 dark:text-zinc-400">No documents yet. Upload one above.</p>;
  }

  return (
    <div>
      {deleteError && <p className="mb-2 text-sm text-red-600 dark:text-red-400">{deleteError}</p>}
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-zinc-200 text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
            <th className="py-2 pr-4 font-medium">Filename</th>
            <th className="py-2 pr-4 font-medium">Status</th>
            <th className="py-2 pr-4 font-medium">Uploaded</th>
            <th className="py-2 font-medium" aria-hidden />
          </tr>
        </thead>
        <tbody>
          {documents.map((doc) => (
            <tr key={doc.id} className="border-b border-zinc-100 dark:border-zinc-900">
              <td className="max-w-xs truncate py-2 pr-4">{doc.filename}</td>
              <td className="py-2 pr-4">
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[doc.status]}`}
                  title={doc.errorMessage ?? undefined}
                >
                  {doc.status}
                </span>
              </td>
              <td className="py-2 pr-4 text-zinc-500 dark:text-zinc-400">{formatDate(doc.createdAt)}</td>
              <td className="py-2 text-right">
                <button
                  type="button"
                  onClick={() => handleDelete(doc.id, doc.filename)}
                  disabled={deletingId === doc.id}
                  className="text-red-600 hover:underline disabled:opacity-50 dark:text-red-400"
                >
                  {deletingId === doc.id ? "Deleting…" : "Delete"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
