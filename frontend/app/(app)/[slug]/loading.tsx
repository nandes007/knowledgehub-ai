export default function AppLoading() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 text-text-tertiary">
      <div className="flex items-center gap-1.5" aria-label="Loading">
        <span className="thinking-dot" />
        <span className="thinking-dot" />
        <span className="thinking-dot" />
      </div>
    </div>
  );
}
