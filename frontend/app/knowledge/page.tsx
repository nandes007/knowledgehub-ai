"use client";

import { useState } from "react";
import { UploadDropzone } from "@/components/UploadDropzone";
import { DocumentTable } from "@/components/DocumentTable";

export default function KnowledgePage() {
  const [refreshSignal, setRefreshSignal] = useState(0);

  return (
    <div className="flex flex-1 flex-col gap-6 overflow-y-auto px-4 pb-6 pt-16 md:px-6 md:pt-6">
      <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Knowledge base</h1>
      <UploadDropzone onUploaded={() => setRefreshSignal((s) => s + 1)} />
      <DocumentTable refreshSignal={refreshSignal} />
    </div>
  );
}
