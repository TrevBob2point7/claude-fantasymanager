import { get, post } from "./client";
import type { SyncResult, SyncLogEntry } from "./types";
import { getCurrentNflSeason } from "./season";

function syncOneSeason(
  accountId: string,
  season: number,
): Promise<SyncResult> {
  return post<SyncResult>(`/sync/${accountId}?season=${season}`);
}

export async function triggerSync(
  accountId: string,
  seasons?: number[],
): Promise<SyncResult> {
  const currentSeason = getCurrentNflSeason();
  const toSync = seasons ?? [currentSeason];

  const results = await Promise.all(
    toSync.map((s) => syncOneSeason(accountId, s)),
  );

  return {
    status: results.every((r) => r.status === "ok") ? "ok" : "partial",
    synced: results.flatMap((r) => r.synced),
    errors: results.flatMap((r) => r.errors),
  };
}

export function getSyncLog(limit?: number): Promise<SyncLogEntry[]> {
  const query = limit != null ? `?limit=${limit}` : "";
  return get<SyncLogEntry[]>(`/sync/log${query}`);
}
