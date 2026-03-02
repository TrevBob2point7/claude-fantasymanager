import { useState, useEffect, useCallback } from "react";
import { getLeagues } from "../api/leagues";
import type { League } from "../api/types";

export function useLeagues(opts?: { season?: number; latest?: boolean }) {
  const [leagues, setLeagues] = useState<League[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const season = opts?.season;
  const latest = opts?.latest ?? false;

  const refresh = useCallback(() => {
    setLoading(true);
    setError(null);
    getLeagues({ season, latest })
      .then(setLeagues)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load leagues"),
      )
      .finally(() => setLoading(false));
  }, [season, latest]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { leagues, loading, error, refresh };
}
