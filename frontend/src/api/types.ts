export interface User {
  id: string;
  email: string;
  display_name: string;
  created_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  display_name?: string;
}

export interface PlatformAccount {
  id: string;
  platform_type: string;
  platform_username: string;
  platform_user_id: string;
  created_at: string;
}

export interface CreatePlatformAccountRequest {
  platform_type: string;
  platform_username?: string;
  platform_user_id?: string;
  credentials_json?: Record<string, unknown>;
}

export interface DiscoveredLeague {
  platform_league_id: string;
  name: string;
  season: number;
  roster_size: number | null;
  scoring_type: string | null;
  already_linked: boolean;
}

export interface League {
  id: string;
  platform_type: string;
  platform_league_id: string;
  name: string;
  season: number;
  roster_size: number | null;
  scoring_type: string | null;
  league_type: string | null;
  team_name: string | null;
  created_at: string;
}

export interface Standing {
  id: string;
  team_name: string | null;
  wins: number;
  losses: number;
  ties: number;
  points_for: string;
  points_against: string;
  rank: number;
}

export interface RosterPlayer {
  id: string;
  player_id: string;
  player_name: string;
  position: string;
  team: string;
  slot: string | null;
  status: string | null;
  bye_week: number | null;
}

export interface Matchup {
  id: string;
  week: number;
  home_team_name: string | null;
  away_team_name: string | null;
  home_score: string;
  away_score: string;
}

export interface Transaction {
  id: string;
  type: string;
  player_name: string;
  from_team_name: string | null;
  to_team_name: string | null;
  timestamp: string;
}

export interface LeagueDetail extends League {
  standings: Standing[];
  roster: RosterPlayer[];
  recent_matchups: Matchup[];
  recent_transactions: Transaction[];
  current_week: number | null;
}

export interface LeagueSeason {
  season: number;
  league_id: string;
}

export interface SyncResult {
  status: string;
  synced: string[];
  errors: string[];
}

export interface SyncLogEntry {
  id: string;
  platform_type: string;
  data_type: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
  created_at: string;
}
