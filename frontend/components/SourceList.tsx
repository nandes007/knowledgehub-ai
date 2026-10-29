import type { Source } from "@/lib/api";

export function SourceList({ sources }: { sources: Source[] }) {
  if (sources.length === 0) return null;

  // One pill per document; RRF order is kept (Map preserves first-seen order).
  const groups = new Map<string, { filename: string; previews: string[] }>();
  for (const source of sources) {
    const group = groups.get(source.document_id) ?? { filename: source.filename, previews: [] };
    group.previews.push(source.chunk_preview);
    groups.set(source.document_id, group);
  }

  return (
    <ul className="mt-3 flex flex-wrap gap-1.5">
      {[...groups].map(([documentId, { filename, previews }], index) => (
        <li
          key={documentId}
          className="animate-stamp-in"
          style={{ animationDelay: `${index * 60}ms` }}
        >
          <details className="group">
            <summary className="cursor-pointer list-none rounded-full border border-gold/30 bg-gold-muted px-2.5 py-0.5 font-mono text-[11px] font-medium uppercase tracking-[0.04em] text-gold transition-colors duration-120 hover:border-gold/50 hover:bg-gold/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold">
              {filename}
              {previews.length > 1 && ` · ${previews.length} sections`}
            </summary>
            <div className="mt-1.5 max-w-md space-y-2 rounded-lg border border-border bg-surface-raised p-3 text-xs leading-relaxed text-text-secondary shadow-lg">
              {previews.map((preview, i) => (
                <p key={i}>{preview}</p>
              ))}
            </div>
          </details>
        </li>
      ))}
    </ul>
  );
}
