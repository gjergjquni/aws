interface EmptyStateProps {
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export default function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-20 px-6 text-center">
      <div className="w-12 h-12 rounded-full bg-[var(--muted)] flex items-center justify-center mb-4 text-[var(--muted-foreground)]">
        <svg width="22" height="22" viewBox="0 0 22 22" fill="none" aria-hidden>
          <rect x="3" y="4" width="16" height="14" rx="2" stroke="currentColor" strokeWidth="1.4" />
          <line x1="7" y1="9" x2="15" y2="9" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
          <line x1="7" y1="12" x2="11" y2="12" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
        </svg>
      </div>
      <p className="text-sm font-medium text-[var(--foreground)] mb-1">{title}</p>
      {description && (
        <p className="text-xs text-[var(--muted-foreground)] mb-5 max-w-sm">{description}</p>
      )}
      {action}
    </div>
  );
}
