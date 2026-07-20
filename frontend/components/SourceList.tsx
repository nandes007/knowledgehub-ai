import type { Source } from "@/lib/api";

export function SourceList({ sources }: { sources: Source[] }) {
  if (sources.length === 0) return null;

  return (
    <ul className="mt-2 flex flex-wrap gap-1.5">
      {sources.map((source, index) => (
        <li key={`${source.document_id}-${index}`}>
          <details>
            <summary className="cursor-pointer list-none rounded-full bg-zinc-200 px-2 py-0.5 text-xs font-medium text-zinc-600 hover:bg-zinc-300 dark:bg-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-600">
              {source.filename}
            </summary>
            <p className="mt-1 max-w-xs rounded-lg bg-zinc-50 p-2 text-xs text-zinc-600 dark:bg-zinc-900 dark:text-zinc-400">
              {source.chunk_preview}
            </p>
          </details>
        </li>
      ))}
    </ul>
  );
}
