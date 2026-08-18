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
          <details className="group">
            <summary className="cursor-pointer list-none rounded-full border border-gold/30 bg-gold-muted px-2.5 py-0.5 font-mono text-[11px] font-medium uppercase tracking-[0.04em] text-gold transition-colors duration-120 hover:border-gold/50 hover:bg-gold/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold">
              {source.filename}
            </summary>
            <p className="mt-1.5 max-w-md rounded-lg border border-border bg-surface-raised p-3 text-xs leading-relaxed text-text-secondary shadow-lg">
              {source.chunk_preview}
            </p>
          </details>
        </li>
      ))}
    </ul>
  );
}
