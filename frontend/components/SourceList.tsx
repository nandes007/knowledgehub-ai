import type { Source } from "@/lib/api";

export function SourceList({ sources }: { sources: Source[] }) {
  if (sources.length === 0) return null;

  return (
    <ul className="mt-2 flex flex-wrap gap-1.5">
      {sources.map((source, index) => (
        <li
          key={`${source.document_id}-${index}`}
          className="animate-stamp-in"
          style={{ animationDelay: `${index * 60}ms` }}
        >
          <details>
            <summary className="cursor-pointer list-none rounded-[2px] border border-brass/50 bg-paper px-2 py-0.5 font-mono text-[11px] font-medium uppercase tracking-[0.04em] text-brass-strong hover:bg-brass/10">
              {source.filename}
            </summary>
            <p className="mt-1 max-w-xs rounded-sm border border-rule bg-paper p-2 text-xs text-ink-muted">
              {source.chunk_preview}
            </p>
          </details>
        </li>
      ))}
    </ul>
  );
}
