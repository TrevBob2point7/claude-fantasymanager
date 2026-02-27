import { useSyncStatus } from "../hooks/useSyncStatus";

interface SyncButtonProps {
  accountId: string;
  onSyncComplete?: () => void;
}

export default function SyncButton({ accountId, onSyncComplete }: SyncButtonProps) {
  const { syncing, error, sync } = useSyncStatus();

  async function handleSync() {
    try {
      await sync(accountId);
      onSyncComplete?.();
    } catch {
      // error is set in hook
    }
  }

  return (
    <div className="inline-flex items-center gap-2">
      <button
        onClick={handleSync}
        disabled={syncing}
        className="rounded-md bg-accent px-3 py-1.5 text-sm font-semibold text-background transition-opacity hover:opacity-90 disabled:opacity-50"
      >
        {syncing ? "Syncing…" : "Sync"}
      </button>
      {error && <span className="text-sm text-destructive">{error}</span>}
    </div>
  );
}
