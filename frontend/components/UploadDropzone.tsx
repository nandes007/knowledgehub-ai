"use client";

import { useRef, useState } from "react";
import { uploadDocument } from "@/lib/api";

const ACCEPTED_TYPES = ".pdf,.docx,.pptx,.md";

export function UploadDropzone({ onUploaded }: { onUploaded: () => void }) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function uploadFiles(files: FileList) {
    setError(null);
    setIsUploading(true);
    try {
      for (const file of Array.from(files)) {
        await uploadDocument(file);
      }
      onUploaded();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setIsDragging(false);
        if (event.dataTransfer.files.length) uploadFiles(event.dataTransfer.files);
      }}
      onClick={() => inputRef.current?.click()}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") inputRef.current?.click();
      }}
      className={`cursor-pointer rounded-lg border-2 border-dashed p-8 text-center text-sm transition-colors ${
        isDragging
          ? "border-zinc-400 bg-zinc-100 dark:border-zinc-500 dark:bg-zinc-900"
          : "border-zinc-300 text-zinc-500 hover:border-zinc-400 dark:border-zinc-700 dark:text-zinc-400"
      }`}
    >
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_TYPES}
        multiple
        className="hidden"
        onChange={(event) => {
          if (event.target.files?.length) uploadFiles(event.target.files);
          event.target.value = "";
        }}
      />
      {isUploading ? "Uploading…" : "Drag and drop files here, or click to browse (PDF, DOCX, PPTX, MD)"}
      {error && <p className="mt-2 text-red-600 dark:text-red-400">{error}</p>}
    </div>
  );
}
