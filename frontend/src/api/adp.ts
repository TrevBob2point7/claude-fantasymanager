import { get, post } from "./client";

export interface ADPSyncResult {
  synced: number;
  skipped: number;
  errored: number;
}

export function syncADP(season?: number): Promise<ADPSyncResult> {
  const query = season ? `?season=${season}` : "";
  return post<ADPSyncResult>(`/adp/sync${query}`);
}

export interface PlayerADPHistory {
  id: string;
  player_id: string;
  source: string;
  format: string;
  season: number;
  adp: string;
  position_rank: number | null;
}

export function getRosterADP(
  playerIds: string[],
  season: number,
  format?: string,
): Promise<Record<string, string | null>> {
  return post<Record<string, string | null>>("/adp/batch", {
    player_ids: playerIds,
    season,
    format: format || undefined,
  });
}

export function getPlayerADPHistory(
  playerId: string,
  format?: string,
): Promise<PlayerADPHistory[]> {
  const query = format ? `?format=${format}` : "";
  return get<PlayerADPHistory[]>(`/adp/players/${playerId}/history${query}`);
}
