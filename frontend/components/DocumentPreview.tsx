"use client";

import { useEffect, useRef, useState } from "react";
import { getDocumentPreview, type DocumentPreview as Preview } from "../lib/api";
import { Markdown } from "./Markdown";

export function DocumentPreview({
  documentId,
  filename,
  onClose,
}: {
  documentId: string;
  filename: string;
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    dialogRef.current?.showModal();
  }, []);

  useEffect(() => {
    let cancelled = false;
    let url: string | undefined;
    getDocumentPreview(documentId)
      .then((result) => {
        if ("url" in result) url = result.url;
        if (cancelled) {
          if (url) URL.revokeObjectURL(url);
          return;
        }
        setPreview(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Couldn't load preview.");
      });
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [documentId]);

  return (
    // Native <dialog>: Escape closes it and focus stays inside; a click on the backdrop lands on the dialog itself.
    <dialog
      ref={dialogRef}
      onClose={onClose}
      onClick={(e) => e.target === dialogRef.current && dialogRef.current?.close()}
      aria-label={`Preview of ${filename}`}
      className="m-auto h-[85vh] w-[min(960px,calc(100vw-2rem))] max-w-none overflow-hidden rounded-xl border border-border bg-surface-raised p-0 text-text-primary backdrop:bg-black/70"
    >
      <div className="flex h-full flex-col">
        <header className="flex items-center gap-3 border-b border-border px-4 py-3">
          <h2 className="min-w-0 flex-1 truncate text-sm font-medium">{filename}</h2>
          <button
            type="button"
            onClick={() => dialogRef.current?.close()}
            className="shrink-0 rounded-lg p-2 text-text-secondary transition-colors duration-120 hover:bg-surface-overlay hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold"
            aria-label="Close preview"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
              <path d="M4 4l8 8M12 4l-8 8" />
            </svg>
          </button>
        </header>

        <div className="min-h-0 flex-1 overflow-auto">
          {error ? (
            <p className="p-6 text-sm text-status-void">{error}</p>
          ) : preview === null ? (
            <p className="p-6 text-sm text-text-secondary">Loading preview…</p>
          ) : preview.kind === "pdf" ? (
            <iframe src={preview.url} title={filename} className="h-full w-full border-0 bg-white" />
          ) : preview.kind === "image" ? (
            // eslint-disable-next-line @next/next/no-img-element -- blob URL, nothing for next/image to optimize
            <img src={preview.url} alt={filename} className="mx-auto max-w-full p-4" />
          ) : preview.text.trim() ? (
            <Markdown className="px-6 py-5">{preview.text}</Markdown>
          ) : (
            <p className="p-6 text-sm text-text-secondary">This document has no readable text.</p>
          )}
        </div>
      </div>
    </dialog>
  );
}
