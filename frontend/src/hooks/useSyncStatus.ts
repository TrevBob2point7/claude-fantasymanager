import { useState, useCallback } from "react";
import { triggerSync } from "../api/sync";
import type { SyncEvent } from "../api/sync";

export function useSyncStatus() {
  const [syncing, setSyncing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const sync = useCallback(async (accountId: string) => {
    setSyncing(true);
    setError(null);
    setMessage(null);
    try {
      await triggerSync(accountId, (event: SyncEvent) => {
        if (event.type === "progress") {
          setMessage(event.message ?? "Syncing...");
        } else if (event.type === "done") {
          setMessage("Sync complete");
        } else if (event.type === "error") {
          setError(event.message ?? "Sync failed");
        }
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Sync failed";
      setError(msg);
      throw err;
    } finally {
      setSyncing(false);
    }
  }, []);

  return { syncing, message, error, sync };
}
