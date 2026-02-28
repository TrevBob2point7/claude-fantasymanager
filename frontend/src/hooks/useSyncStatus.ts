import { useState, useCallback } from "react";
import { triggerSync } from "../api/sync";
import type { SyncResult } from "../api/types";

export function useSyncStatus() {
  const [syncing, setSyncing] = useState(false);
  const [result, setResult] = useState<SyncResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const sync = useCallback(async (accountId: string) => {
    setSyncing(true);
    setError(null);
    setResult(null);
    try {
      const data = await triggerSync(accountId);
      setResult(data);
      return data;
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Sync failed";
      setError(message);
      throw err;
    } finally {
      setSyncing(false);
    }
  }, []);

  return { syncing, result, error, sync };
}
