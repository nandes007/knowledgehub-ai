"use client";

import { useState } from "react";
import { UploadDropzone } from "@/components/UploadDropzone";
import { DocumentTable } from "@/components/DocumentTable";

export default function KnowledgePage() {
  const [refreshSignal, setRefreshSignal] = useState(0);

  return (
    <div className="flex flex-1 flex-col gap-6 overflow-y-auto bg-paper px-4 pb-6 pt-16 md:px-6 md:pt-6">
      <div>
        <h1 className="font-serif text-lg font-semibold text-ink">Knowledge base</h1>
        <p className="mt-1 text-sm text-ink-muted">Every deposit, catalogued and searchable.</p>
      </div>
      <UploadDropzone onUploaded={() => setRefreshSignal((s) => s + 1)} />
      <DocumentTable refreshSignal={refreshSignal} />
    </div>
  );
}
