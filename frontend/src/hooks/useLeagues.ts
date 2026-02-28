import { useState, useEffect, useCallback } from "react";
import { getLeagues } from "../api/leagues";
import type { League } from "../api/types";

export function useLeagues(season?: number) {
  const [leagues, setLeagues] = useState<League[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    setLoading(true);
    setError(null);
    getLeagues(season)
      .then(setLeagues)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load leagues"),
      )
      .finally(() => setLoading(false));
  }, [season]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { leagues, loading, error, refresh };
}
