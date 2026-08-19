"use client";

import { useRef, useState } from "react";
import { uploadDocument, type Visibility } from "../lib/api";
import { Label, Input } from "./ui";

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
  const [uploadProgress, setUploadProgress] = useState<{ current: number; total: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [visibility, setVisibility] = useState<Visibility>("company");
  const [department, setDepartment] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  async function uploadFiles(files: FileList) {
    setError(null);
    const fileArray = Array.from(files);
    if (fileArray.length === 0) return;

    setUploadProgress({ current: 1, total: fileArray.length });
    try {
      for (let i = 0; i < fileArray.length; i++) {
        setUploadProgress({ current: i + 1, total: fileArray.length });
        await uploadDocument(fileArray[i], { visibility, department: department || undefined });
      }
      onUploaded();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploadProgress(null);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-4">
        <div className="w-48 space-y-1">
          <Label htmlFor="visibility">Visibility</Label>
          <select
            id="visibility"
            value={visibility}
            onChange={(event) => setVisibility(event.target.value as Visibility)}
            className="h-10 w-full rounded-lg border border-border bg-surface-input px-3 py-2 text-sm text-text-primary focus:border-gold focus:outline-none focus:ring-1 focus:ring-gold"
          >
            <option value="company">Whole company</option>
            <option value="department">My department only</option>
          </select>
        </div>
        {visibility === "department" && (
          <div className="min-w-[200px] flex-1 space-y-1">
            <Label htmlFor="department">Department</Label>
            <Input
              id="department"
              type="text"
              required
              placeholder="e.g. Engineering"
              value={department}
              onChange={(event) => setDepartment(event.target.value)}
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
            ? "border-gold bg-gold-muted text-text-primary"
            : "border-border text-text-secondary hover:border-gold/40 hover:text-text-primary"
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
        {uploadProgress ? (
          <span>Uploading file {uploadProgress.current} of {uploadProgress.total}...</span>
        ) : (
          "Drag and drop files here, or click to browse"
        )}
        <span className="text-xs text-text-tertiary">PDF, DOCX, PPTX, MD</span>
        {error && <p className="mt-1 text-status-void">{error}</p>}
      </div>
    </div>
  );
}
