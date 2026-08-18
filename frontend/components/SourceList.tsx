import type { Source } from "@/lib/api";

export function SourceList({ sources }: { sources: Source[] }) {
  if (sources.length === 0) return null;

  return (
    <ul className="mt-3 flex flex-wrap gap-1.5">
      {sources.map((source, index) => (
        <li
          key={`${source.document_id}-${index}`}
          className="animate-stamp-in"
          style={{ animationDelay: `${index * 60}ms` }}
        >
          <details>
            <summary className="cursor-pointer list-none rounded-full border border-accent/30 bg-accent-muted px-2.5 py-0.5 font-mono text-[11px] font-medium uppercase tracking-[0.04em] text-accent transition-colors duration-120 hover:bg-accent/20 hover:border-accent/50">
              {source.filename}
            </summary>
            <p className="mt-1.5 max-w-xs rounded-lg border border-border bg-surface-raised p-2.5 text-xs leading-relaxed text-text-secondary">
              {source.chunk_preview}
            </p>
          </details>
        </li>
      ))}
    </ul>
  );
}
