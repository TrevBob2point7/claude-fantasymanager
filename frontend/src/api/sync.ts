import { get, post } from "./client";
import type { SyncResult, SyncLogEntry } from "./types";
import { getCurrentNflSeason } from "./season";

export function triggerSync(
  accountId: string,
  season: number = getCurrentNflSeason(),
): Promise<SyncResult> {
  return post<SyncResult>(`/sync/${accountId}?season=${season}`);
}

export function getSyncLog(limit?: number): Promise<SyncLogEntry[]> {
  const query = limit != null ? `?limit=${limit}` : "";
  return get<SyncLogEntry[]>(`/sync/log${query}`);
}
