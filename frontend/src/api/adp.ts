import { get } from "./client";

export interface PlayerADPHistory {
  id: string;
  player_id: string;
  source: string;
  format: string;
  season: number;
  adp: string;
  position_rank: number | null;
}

export function getPlayerADPHistory(
  playerId: string,
  format?: string,
): Promise<PlayerADPHistory[]> {
  const query = format ? `?format=${format}` : "";
  return get<PlayerADPHistory[]>(`/adp/players/${playerId}/history${query}`);
}
