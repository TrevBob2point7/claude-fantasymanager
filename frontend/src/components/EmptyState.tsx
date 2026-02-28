import { Link } from "react-router-dom";

interface EmptyStateProps {
  title: string;
  description: string;
  actionLabel?: string;
  actionTo?: string;
}

export default function EmptyState({
  title,
  description,
  actionLabel,
  actionTo,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-border bg-surface px-6 py-16 text-center">
      <h2 className="font-heading text-xl font-semibold text-text-primary">
        {title}
      </h2>
      <p className="mt-2 max-w-md text-text-secondary">{description}</p>
      {actionLabel && actionTo && (
        <Link
          to={actionTo}
          className="mt-6 rounded-md bg-accent px-4 py-2 font-semibold text-background hover:opacity-90"
        >
          {actionLabel}
        </Link>
      )}
    </div>
  );
}
