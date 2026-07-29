"use client";

import { useRef, useState } from "react";
import { uploadDocument, type Visibility } from "@/lib/api";
import { Input, Label } from "@/components/ui";

const ACCEPTED_TYPES = ".pdf,.docx,.pptx,.md";

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
            className="w-full rounded-t-sm border-0 border-b-2 border-rule bg-paper px-3 py-2 text-sm text-ink focus:border-brass focus:outline-none"
          >
            <option value="company">Whole company</option>
            <option value="department">My department only</option>
          </select>
        </div>
        {visibility === "department" && (
          <div className="space-y-1">
            <Label htmlFor="department">Department</Label>
            <Input
              id="department"
              type="text"
              required
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
        className={`cursor-pointer rounded-sm border-2 border-dashed p-8 text-center text-sm transition-colors ${
          isDragging ? "border-brass bg-brass/10 text-ink" : "border-rule text-ink-muted hover:border-brass/60"
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
        {error && <p className="mt-2 text-stamp-void">{error}</p>}
      </div>
    </div>
  );
}
