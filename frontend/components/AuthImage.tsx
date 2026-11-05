"use client";

import { useEffect, useState } from "react";
import { fetchProtectedFile } from "@/lib/api";

// Loads an image that sits behind auth (document images, chat attachments) through an
// authenticated fetch, since a plain <img src> can't send the Bearer header.
export function AuthImage({ src, alt, className = "" }: { src: string; alt: string; className?: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    fetchProtectedFile(src)
      .then((u) => {
        objectUrl = u;
        if (cancelled) URL.revokeObjectURL(u);
        else setUrl(u);
      })
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [src]);

  if (failed) {
    return (
      <span className="my-3 inline-block rounded-lg border border-dashed border-border px-3 py-2 text-xs text-text-tertiary">
        Image no longer available
      </span>
    );
  }
  if (!url) {
    return <span role="img" aria-label={alt} className={`inline-block animate-pulse rounded-lg bg-surface-raised ${className}`} />;
  }
  // eslint-disable-next-line @next/next/no-img-element -- blob URLs can't go through next/image
  return <img src={url} alt={alt} className={className} />;
}
