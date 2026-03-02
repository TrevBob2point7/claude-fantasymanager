import { useState, useEffect, useCallback } from "react";
import { getLeagues } from "../api/leagues";
import type { League } from "../api/types";

export function useLeagues(opts?: { season?: number; latest?: boolean }) {
  const [leagues, setLeagues] = useState<League[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const cacheKey = opts?.latest ? "latest" : String(opts?.season ?? "");

  const refresh = useCallback(() => {
    setLoading(true);
    setError(null);
    getLeagues(opts)
      .then(setLeagues)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load leagues"),
      )
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cacheKey]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { leagues, loading, error, refresh };
}
