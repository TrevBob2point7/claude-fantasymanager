import { get, post } from "./client";
import type { DiscoveredLeague, League, LeagueDetail } from "./types";

export function getLeagues(season?: number): Promise<League[]> {
  const query = season != null ? `?season=${season}` : "";
  return get<League[]>(`/leagues${query}`);
}

export function getLeagueDetail(leagueId: string): Promise<LeagueDetail> {
  return get<LeagueDetail>(`/leagues/${leagueId}`);
}

export function discoverLeagues(
  platformAccountId: string,
  season: number,
): Promise<DiscoveredLeague[]> {
  return post<DiscoveredLeague[]>("/leagues/discover", {
    platform_account_id: platformAccountId,
    season,
  });
}
