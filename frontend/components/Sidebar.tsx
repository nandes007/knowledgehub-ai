export type ConversationSummary = {
  id: string;
  title: string;
};

// Task 09 replaces this with real conversations fetched from GET /conversations.
const DUMMY_CONVERSATIONS: ConversationSummary[] = [
  { id: "1", title: "Vacation policy questions" },
  { id: "2", title: "Onboarding checklist" },
  { id: "3", title: "Q3 product roadmap" },
];

export function Sidebar() {
  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="p-3">
        <button
          type="button"
          className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-left text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-900"
        >
          + New chat
        </button>
      </div>
      <nav className="flex-1 overflow-y-auto px-2 pb-3">
        <ul className="space-y-1">
          {DUMMY_CONVERSATIONS.map((conversation, index) => (
            <li key={conversation.id}>
              <a
                href="#"
                className={`block truncate rounded-lg px-3 py-2 text-sm ${
                  index === 0
                    ? "bg-zinc-200 font-medium text-zinc-900 dark:bg-zinc-800 dark:text-zinc-50"
                    : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-900"
                }`}
              >
                {conversation.title}
              </a>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  );
}
