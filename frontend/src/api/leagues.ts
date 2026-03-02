import { get, post } from "./client";
import type { DiscoveredLeague, League, LeagueDetail, LeagueSeason } from "./types";

export function getLeagues(opts?: { season?: number; latest?: boolean }): Promise<League[]> {
  const params = new URLSearchParams();
  if (opts?.latest) params.set("latest", "true");
  else if (opts?.season != null) params.set("season", String(opts.season));
  const query = params.toString() ? `?${params}` : "";
  return get<League[]>(`/leagues${query}`);
}

export function getLeagueDetail(leagueId: string): Promise<LeagueDetail> {
  return get<LeagueDetail>(`/leagues/${leagueId}`);
}

export function getLeagueSeasons(
  leagueId: string,
): Promise<{ seasons: LeagueSeason[] }> {
  return get<{ seasons: LeagueSeason[] }>(`/leagues/${leagueId}/seasons`);
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
