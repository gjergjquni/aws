interface LoadingStateProps {
  label?: string;
  fullScreen?: boolean;
}

export default function LoadingState({
  label = "Loading…",
  fullScreen = false,
}: LoadingStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center gap-3 text-[var(--muted-foreground)] ${
        fullScreen ? "min-h-screen" : "py-16"
      }`}
      role="status"
      aria-live="polite"
    >
      <svg
        className="animate-spin text-[var(--primary)]"
        width="24"
        height="24"
        viewBox="0 0 24 24"
        fill="none"
        aria-hidden
      >
        <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2" strokeDasharray="40 20" />
      </svg>
      <span className="text-sm">{label}</span>
    </div>
  );
}
