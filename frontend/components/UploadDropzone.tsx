"use client";

import { useRef, useState } from "react";
import { uploadDocument, type Visibility } from "@/lib/api";
import { Label } from "@/components/ui";

const ACCEPTED_TYPES = ".pdf,.docx,.pptx,.md";

function IconCloudUpload() {
  return (
    <svg width="32" height="32" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-text-tertiary">
      <path d="M10.667 21.333 16 16l5.333 5.333M16 16v10.667" />
      <path d="M27.04 23.373A6.667 6.667 0 0 0 24 10.667h-1.68A10.667 10.667 0 1 0 4 22" />
      <path d="M10.667 21.333 16 16l5.333 5.333" />
    </svg>
  );
}

export function UploadDropzone({ onUploaded }: { onUploaded: () => void }) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [visibility, setVisibility] = useState<Visibility>("company");
  const [department, setDepartment] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  async function uploadFiles(files: FileList) {
    setError(null);
    setIsUploading(true);
    try {
      for (const file of Array.from(files)) {
        await uploadDocument(file, { visibility, department: department || undefined });
      }
      onUploaded();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-4">
        <div className="space-y-1">
          <Label htmlFor="visibility">Visibility</Label>
          <select
            id="visibility"
            value={visibility}
            onChange={(event) => setVisibility(event.target.value as Visibility)}
            className="w-full rounded-lg border border-border bg-surface-primary px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          >
            <option value="company">Whole company</option>
            <option value="department">My department only</option>
          </select>
        </div>
        {visibility === "department" && (
          <div className="space-y-1">
            <Label htmlFor="department">Department</Label>
            <input
              id="department"
              type="text"
              required
              value={department}
              onChange={(event) => setDepartment(event.target.value)}
              className="w-full rounded-lg border border-border bg-surface-primary px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
            />
          </div>
        )}
      </div>
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
        className={`flex cursor-pointer flex-col items-center gap-3 rounded-xl border-2 border-dashed p-8 text-center text-sm transition-all duration-120 ${
          isDragging
            ? "border-accent bg-accent-muted text-text-primary"
            : "border-border text-text-secondary hover:border-accent/40 hover:text-text-primary"
        }`}
      >
        <IconCloudUpload />
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
        {isUploading ? "Uploading…" : "Drag and drop files here, or click to browse"}
        <span className="text-xs text-text-tertiary">PDF, DOCX, PPTX, MD</span>
        {error && <p className="mt-1 text-status-void">{error}</p>}
      </div>
    </div>
  );
}
