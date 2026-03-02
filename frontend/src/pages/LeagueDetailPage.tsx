import { useState, useEffect, useMemo } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { getLeagueDetail, getLeagueSeasons } from "../api/leagues";
import { getRosterADP } from "../api/adp";
import { getCurrentNflSeason } from "../api/season";
import type {
  LeagueDetail,
  LeagueSeason,
  RosterPlayer,
  Standing,
  Matchup,
  MatchupPlayer,
  Transaction,
} from "../api/types";
import PlayerADPModal from "../components/PlayerADPModal";

type Tab = "overview" | "roster" | "standings" | "matchups" | "transactions";

const tabs: { key: Tab; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "roster", label: "Roster" },
  { key: "standings", label: "Standings" },
  { key: "matchups", label: "Matchups" },
  { key: "transactions", label: "Transactions" },
];

const SCORING_FORMATS = [
  { value: "ppr", label: "PPR" },
  { value: "half_ppr", label: "Half PPR" },
  { value: "standard", label: "Standard" },
  { value: "superflex", label: "Superflex" },
  { value: "two_qb", label: "2QB" },
];

export default function LeagueDetailPage() {
  const { leagueId } = useParams<{ leagueId: string }>();
  const navigate = useNavigate();
  const [league, setLeague] = useState<LeagueDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [adpFormat, setAdpFormat] = useState<string | null>(null);
  const [adpMap, setAdpMap] = useState<Record<string, string | null>>({});
  const [seasons, setSeasons] = useState<LeagueSeason[]>([]);

  // Fetch league detail when leagueId changes
  useEffect(() => {
    if (!leagueId) return;
    setLoading(true);
    setAdpMap({});
    getLeagueDetail(leagueId)
      .then((data) => {
        setLeague(data);
        if (data.league_type === "dynasty") {
          setAdpFormat("dynasty");
        } else {
          const scoring = data.scoring_type ?? "";
          setAdpFormat(SCORING_FORMATS.some((f) => f.value === scoring) ? scoring : "ppr");
        }
      })
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load league"),
      )
      .finally(() => setLoading(false));

    // Fetch available seasons
    getLeagueSeasons(leagueId)
      .then((data) => setSeasons(data.seasons))
      .catch(() => setSeasons([]));
  }, [leagueId]);

  // Fetch ADP separately
  const playerIds = useMemo(
    () => league?.roster.map((p) => p.player_id) ?? [],
    [league?.roster],
  );

  useEffect(() => {
    if (playerIds.length === 0 || !league || adpFormat === null) return;
    getRosterADP(playerIds, league.season, adpFormat || undefined)
      .then(setAdpMap)
      .catch(() => setAdpMap({}));
  }, [playerIds, league?.season, adpFormat]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      </div>
    );
  }

  if (error || !league) {
    return (
      <div>
        <Link to="/" className="text-sm text-accent hover:underline">
          &larr; Back to Dashboard
        </Link>
        <p className="mt-4 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error ?? "League not found"}
        </p>
      </div>
    );
  }

  const isPastSeason = league.season < getCurrentNflSeason() || league.current_week === 0;
  const isCurrentSeason = !isPastSeason;

  return (
    <div>
      <Link to="/" className="text-sm text-accent hover:underline">
        &larr; Back to Dashboard
      </Link>

      {/* Header */}
      <div className="mt-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold text-text-primary">
            {league.name}
          </h1>
          <p className="mt-1 text-text-secondary">
            {league.season} &middot; {league.scoring_type?.toUpperCase() ?? "—"}
            {league.league_type && (
              <> &middot; <span className="capitalize">{league.league_type}</span></>
            )}
            {" "}&middot; {league.roster_size ?? "—"} roster spots &middot; {league.team_name ?? "My Team"}
          </p>
        </div>
        {seasons.length > 1 && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-text-secondary">Season:</span>
            <select
              value={leagueId}
              onChange={(e) => navigate(`/leagues/${e.target.value}`)}
              className="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary"
            >
              {seasons.map((s) => (
                <option key={s.league_id} value={s.league_id}>
                  {s.season}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="-mx-4 mt-6 overflow-x-auto border-b border-border px-4 md:mx-0 md:px-0">
        <div className="flex gap-1">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`whitespace-nowrap px-4 py-3 text-sm font-medium transition-colors ${
                activeTab === tab.key
                  ? "border-b-2 border-accent text-accent"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div className="mt-4">
        {activeTab === "overview" && (
          <OverviewTab
            league={league}
            adpMap={adpMap}
            isCurrentSeason={isCurrentSeason}
          />
        )}
        {activeTab === "roster" && (
          <RosterTab
            roster={league.roster}
            adpMap={adpMap}
            adpFormat={adpFormat ?? ""}
            isDynastyLeague={league.league_type === "dynasty"}
            onAdpFormatChange={setAdpFormat}
          />
        )}
        {activeTab === "standings" && <StandingsTab standings={league.standings} />}
        {activeTab === "matchups" && (
          <MatchupsTab matchups={league.recent_matchups} teamName={league.team_name} />
        )}
        {activeTab === "transactions" && (
          <TransactionsTab transactions={league.recent_transactions} />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Overview Tab (7.1)
// ---------------------------------------------------------------------------

function OverviewTab({
  league,
  adpMap,
  isCurrentSeason,
}: {
  league: LeagueDetail;
  adpMap: Record<string, string | null>;
  isCurrentSeason: boolean;
}) {
  const [adpPlayer, setAdpPlayer] = useState<RosterPlayer | null>(null);

  const userStanding = league.standings.find((s) => s.is_me) ?? null;

  const starters = sortBySlot(
    league.roster.filter((p) => p.slot != null && p.slot !== "TAXI"),
  );

  const recentTransactions = league.recent_transactions.slice(0, 5);

  return (
    <>
      {/* Top row: Record & Matchup + Roster Alerts */}
      <div className="grid gap-4 lg:grid-cols-2">
        <RecordMatchupCard
          standing={userStanding}
          matchups={league.recent_matchups}
          leagueSize={league.standings.length}
          isCurrentSeason={isCurrentSeason}
          teamName={league.team_name}
        />
        {isCurrentSeason && (
          <RosterAlerts
            starters={starters}
            currentWeek={league.current_week}
          />
        )}
      </div>

      {/* Starting Lineup */}
      <div className="mt-6">
        <h2 className="mb-3 font-heading text-lg font-semibold text-text-primary">
          Starting Lineup
        </h2>
        <StartingLineupTable
          starters={starters}
          adpMap={adpMap}
          onPlayerClick={setAdpPlayer}
        />
      </div>

      {/* Recent Activity */}
      {(isCurrentSeason || recentTransactions.length > 0) && (
        <div className="mt-6">
          <h2 className="mb-3 font-heading text-lg font-semibold text-text-primary">
            Recent Activity
          </h2>
          <RecentActivity transactions={recentTransactions} />
        </div>
      )}

      {adpPlayer && (
        <PlayerADPModal
          playerId={adpPlayer.player_id}
          playerName={adpPlayer.player_name}
          position={adpPlayer.position}
          team={adpPlayer.team}
          format={league.league_type === "dynasty" ? "dynasty" : league.scoring_type ?? undefined}
          onClose={() => setAdpPlayer(null)}
        />
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Record & Matchup Card (7.2)
// ---------------------------------------------------------------------------

function RecordMatchupCard({
  standing,
  matchups,
  leagueSize,
  isCurrentSeason,
  teamName,
}: {
  standing: Standing | null;
  matchups: Matchup[];
  leagueSize: number;
  isCurrentSeason: boolean;
  teamName: string | null;
}) {
  const userMatchups = matchups.filter((m) => m.is_user_matchup);
  const lastMatchup = userMatchups.length > 0 ? userMatchups[0] : null;
  // Next matchup would be the first future matchup; for now we don't have a
  // separate "upcoming" matchup in the API, so we skip it until the API
  // provides that data. We show the last completed matchup.

  return (
    <div className="rounded-xl border border-border bg-surface p-5">
      <h2 className="mb-3 font-heading text-lg font-semibold text-text-primary">
        Record & Matchup
      </h2>

      {standing ? (
        <div className="space-y-2">
          <div className="flex items-baseline gap-3">
            <span className="font-score text-2xl font-bold text-text-primary">
              {standing.wins}-{standing.losses}-{standing.ties}
            </span>
            <span className="text-sm text-text-secondary">
              {ordinal(standing.rank)} of {leagueSize}
            </span>
          </div>
          <div className="flex gap-6 text-sm">
            <span>
              <span className="text-text-secondary">PF: </span>
              <span className="font-score text-accent-green">
                {formatPoints(standing.points_for)}
              </span>
            </span>
            <span>
              <span className="text-text-secondary">PA: </span>
              <span className="font-score text-text-secondary">
                {formatPoints(standing.points_against)}
              </span>
            </span>
          </div>
        </div>
      ) : (
        <p className="text-sm text-text-secondary">—</p>
      )}

      <div className="mt-4 border-t border-border pt-3">
        {lastMatchup ? (
          <div className="space-y-1 text-sm">
            <MatchupLine label="Last" matchup={lastMatchup} teamName={teamName} />
          </div>
        ) : (
          <p className="text-sm text-text-secondary">No matchups yet</p>
        )}
        {isCurrentSeason && !lastMatchup && (
          <p className="mt-1 text-sm text-text-secondary">Season has not started</p>
        )}
      </div>
    </div>
  );
}

function MatchupLine({ label, matchup, teamName }: { label: string; matchup: Matchup; teamName: string | null }) {
  // Determine if user is home or away to show correct perspective
  const isHome = teamName != null && matchup.home_team_name === teamName;
  const myScore = isHome ? matchup.home_score : matchup.away_score;
  const oppScore = isHome ? matchup.away_score : matchup.home_score;
  const oppName = isHome ? matchup.away_team_name : matchup.home_team_name;
  const myScoreNum = parseFloat(myScore);
  const oppScoreNum = parseFloat(oppScore);
  const won = myScoreNum > oppScoreNum;
  const tied = myScoreNum === oppScoreNum;

  return (
    <p>
      <span className="text-text-secondary">{label}: </span>
      {!tied && (
        <span className={won ? "font-semibold text-accent-green" : "font-semibold text-destructive"}>
          {won ? "W" : "L"}{" "}
        </span>
      )}
      <span className="font-score text-text-primary">
        {myScore}
      </span>
      <span className="text-text-secondary"> vs </span>
      <span className="text-text-primary">{oppName ?? "TBD"}</span>
      <span className="text-text-secondary"> (Wk {matchup.week})</span>
    </p>
  );
}

// ---------------------------------------------------------------------------
// Roster Alerts (7.3)
// ---------------------------------------------------------------------------

const ALERT_SEVERITY: Record<string, number> = {
  out: 0,
  injured_reserve: 0,
  suspended: 0,
  doubtful: 1,
  bye: 2,
  questionable: 3,
};

const STATUS_LABELS: Record<string, string> = {
  out: "OUT",
  injured_reserve: "IR",
  suspended: "Suspended",
  doubtful: "Doubtful",
  questionable: "Questionable",
};

interface RosterAlert {
  playerName: string;
  alertType: string;
  label: string;
  severity: number;
}

function RosterAlerts({
  starters,
  currentWeek,
}: {
  starters: RosterPlayer[];
  currentWeek: number | null;
}) {
  const alerts: RosterAlert[] = [];

  for (const player of starters) {
    // Status-based alerts
    if (player.status && player.status !== "active" && STATUS_LABELS[player.status]) {
      alerts.push({
        playerName: player.player_name,
        alertType: player.status,
        label: STATUS_LABELS[player.status],
        severity: ALERT_SEVERITY[player.status] ?? 99,
      });
    }
    // Bye week alert
    if (currentWeek != null && player.bye_week != null && player.bye_week === currentWeek) {
      alerts.push({
        playerName: player.player_name,
        alertType: "bye",
        label: `BYE (Wk ${player.bye_week})`,
        severity: ALERT_SEVERITY.bye,
      });
    }
  }

  alerts.sort((a, b) => a.severity - b.severity);

  return (
    <div className="rounded-xl border border-border bg-surface p-5">
      <h2 className="mb-3 font-heading text-lg font-semibold text-text-primary">
        Roster Alerts
      </h2>
      {alerts.length === 0 ? (
        <p className="text-sm text-text-secondary">No roster alerts</p>
      ) : (
        <div className="space-y-2">
          {alerts.map((alert, i) => (
            <div
              key={`${alert.playerName}-${alert.alertType}-${i}`}
              className="flex items-center gap-2 text-sm"
            >
              <span className="text-accent-orange">&#9888;</span>
              <span className="font-medium text-text-primary">{alert.playerName}</span>
              <span className="text-text-secondary">&mdash;</span>
              <span className={
                alert.severity === 0 ? "font-semibold text-destructive" :
                alert.severity === 1 ? "font-semibold text-accent-orange" :
                "text-text-secondary"
              }>
                {alert.label}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Starting Lineup Table (7.4)
// ---------------------------------------------------------------------------

function StartingLineupTable({
  starters,
  adpMap,
  onPlayerClick,
}: {
  starters: RosterPlayer[];
  adpMap: Record<string, string | null>;
  onPlayerClick: (player: RosterPlayer) => void;
}) {
  if (starters.length === 0) {
    return <p className="py-8 text-center text-text-secondary">No roster data available.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full table-fixed text-sm">
        <colgroup>
          <col className="w-[12%]" />
          <col className="w-[35%]" />
          <col className="w-[13%]" />
          <col className="w-[20%]" />
          <col className="w-[20%]" />
        </colgroup>
        <thead>
          <tr className="border-b border-border bg-surface">
            <th className="px-4 py-3 text-left font-medium text-text-secondary">Slot</th>
            <th className="px-4 py-3 text-left font-medium text-text-secondary">Player</th>
            <th className="px-4 py-3 text-left font-medium text-text-secondary">Pos</th>
            <th className="px-4 py-3 text-left font-medium text-text-secondary">Team</th>
            <th className="px-4 py-3 text-right font-medium text-text-secondary">ADP</th>
          </tr>
        </thead>
        <tbody>
          {starters.map((player) => {
            const adp = adpMap[player.player_id];
            return (
              <tr key={player.id} className="border-b border-border last:border-0">
                <td className="px-4 py-3 text-xs font-semibold uppercase text-text-secondary">
                  {player.slot}
                </td>
                <td className="px-4 py-3 font-medium text-text-primary">
                  {player.player_name}
                </td>
                <td className="px-4 py-3 text-text-secondary">{player.position}</td>
                <td className="px-4 py-3 text-text-secondary">{player.team}</td>
                <td className="px-4 py-3 text-right">
                  {adp ? (
                    <button
                      onClick={() => onPlayerClick(player)}
                      className="font-score text-accent hover:underline"
                    >
                      {adp}
                    </button>
                  ) : (
                    <span className="text-text-secondary">&mdash;</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Recent Activity (7.5)
// ---------------------------------------------------------------------------

function RecentActivity({ transactions }: { transactions: Transaction[] }) {
  if (transactions.length === 0) {
    return <p className="text-sm text-text-secondary">No recent activity.</p>;
  }

  return (
    <div className="space-y-2">
      {transactions.map((t) => (
        <div
          key={t.id}
          className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-surface px-4 py-3 sm:justify-between"
        >
          <div className="flex items-center gap-3">
            <TransactionBadge type={t.type} />
            <span className="font-medium text-text-primary">{t.player_name}</span>
          </div>
          <div className="flex items-center gap-3 text-sm text-text-secondary">
            <span>
              {t.from_team_name && <>{t.from_team_name} &rarr; </>}
              {t.to_team_name ?? "Free Agent"}
            </span>
            <span>&middot;</span>
            <span>{relativeTime(t.timestamp)}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function TransactionBadge({ type }: { type: string }) {
  const styles: Record<string, string> = {
    add: "bg-accent-green/15 text-accent-green",
    drop: "bg-destructive/15 text-destructive",
    trade: "bg-accent-orange/15 text-accent-orange",
    waiver: "bg-accent/15 text-accent",
  };

  return (
    <span className={`rounded-md px-2 py-0.5 text-xs font-semibold uppercase ${styles[type] ?? "bg-surface-hover text-text-secondary"}`}>
      {type}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Roster Tab (existing, preserved)
// ---------------------------------------------------------------------------

const POSITION_ORDER: Record<string, number> = {
  QB: 0, RB: 1, WR: 2, TE: 3, DEF: 4, K: 5,
};

const SLOT_ORDER: Record<string, number> = {
  QB: 0, RB: 1, WR: 2, TE: 3, FLEX: 4, SUPERFLEX: 5, K: 6, PK: 6, DEF: 7,
};

function sortBySlot(players: RosterPlayer[]): RosterPlayer[] {
  return [...players].sort((a, b) => {
    const aOrder = SLOT_ORDER[a.slot ?? ""] ?? 99;
    const bOrder = SLOT_ORDER[b.slot ?? ""] ?? 99;
    return aOrder - bOrder;
  });
}

function sortByPosition(
  players: RosterPlayer[],
  adpMap: Record<string, string | null>,
): RosterPlayer[] {
  return [...players].sort((a, b) => {
    const aOrder = POSITION_ORDER[a.position] ?? 99;
    const bOrder = POSITION_ORDER[b.position] ?? 99;
    if (aOrder !== bOrder) return aOrder - bOrder;
    const aAdp = adpMap[a.player_id] ? parseFloat(adpMap[a.player_id]!) : Infinity;
    const bAdp = adpMap[b.player_id] ? parseFloat(adpMap[b.player_id]!) : Infinity;
    return aAdp - bAdp;
  });
}

function RosterTable({
  players,
  adpMap,
  onPlayerClick,
}: {
  players: RosterPlayer[];
  adpMap: Record<string, string | null>;
  onPlayerClick: (player: RosterPlayer) => void;
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full table-fixed text-sm">
        <colgroup>
          <col className="w-[45%]" />
          <col className="w-[15%]" />
          <col className="w-[20%]" />
          <col className="w-[20%]" />
        </colgroup>
        <thead>
          <tr className="border-b border-border bg-surface">
            <th className="px-4 py-3 text-left font-medium text-text-secondary">Player</th>
            <th className="px-4 py-3 text-left font-medium text-text-secondary">Pos</th>
            <th className="px-4 py-3 text-left font-medium text-text-secondary">Team</th>
            <th className="px-4 py-3 text-right font-medium text-text-secondary">ADP</th>
          </tr>
        </thead>
        <tbody>
          {players.map((player) => {
            const adp = adpMap[player.player_id];
            return (
              <tr key={player.id} className="border-b border-border last:border-0">
                <td className="px-4 py-3 font-medium text-text-primary">{player.player_name}</td>
                <td className="px-4 py-3 text-text-secondary">{player.position}</td>
                <td className="px-4 py-3 text-text-secondary">{player.team}</td>
                <td className="px-4 py-3 text-right">
                  {adp ? (
                    <button
                      onClick={() => onPlayerClick(player)}
                      className="font-score text-accent hover:underline"
                    >
                      {adp}
                    </button>
                  ) : (
                    <span className="text-text-secondary">&mdash;</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function RosterTab({
  roster,
  adpMap,
  adpFormat,
  isDynastyLeague,
  onAdpFormatChange,
}: {
  roster: LeagueDetail["roster"];
  adpMap: Record<string, string | null>;
  adpFormat: string;
  isDynastyLeague: boolean;
  onAdpFormatChange: (format: string) => void;
}) {
  const [adpPlayer, setAdpPlayer] = useState<RosterPlayer | null>(null);

  // Main roster: everyone except taxi — sort by position group + ADP
  const mainRoster = sortByPosition(
    roster.filter((p) => p.slot !== "TAXI"),
    adpMap,
  );
  // Taxi: slot === "TAXI" — sort by position group + ADP
  const taxiSquad = sortByPosition(
    roster.filter((p) => p.slot === "TAXI"),
    adpMap,
  );

  if (roster.length === 0) {
    return <p className="py-8 text-center text-text-secondary">No roster data available.</p>;
  }

  return (
    <>
      {/* ADP format picker */}
      <div className="mb-3 flex flex-wrap items-center gap-1.5">
        <span className="mr-1 text-sm text-text-secondary">ADP:</span>
        {(isDynastyLeague
          ? [{ value: "dynasty", label: "Dynasty" }, ...SCORING_FORMATS]
          : SCORING_FORMATS
        ).map((fmt) => (
          <button
            key={fmt.value}
            onClick={() => onAdpFormatChange(fmt.value)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
              adpFormat === fmt.value
                ? "bg-accent text-background"
                : "bg-surface-hover text-text-secondary hover:text-text-primary"
            }`}
          >
            {fmt.label}
          </button>
        ))}
      </div>

      {mainRoster.length > 0 && (
        <>
          <h3 className="mb-3 font-heading text-lg font-semibold text-text-primary">
            Roster
          </h3>
          <RosterTable players={mainRoster} adpMap={adpMap} onPlayerClick={setAdpPlayer} />
        </>
      )}

      {taxiSquad.length > 0 && (
        <>
          <h3 className="mt-6 mb-3 font-heading text-lg font-semibold text-text-primary">
            Taxi Squad
          </h3>
          <RosterTable players={taxiSquad} adpMap={adpMap} onPlayerClick={setAdpPlayer} />
        </>
      )}

      {adpPlayer && (
        <PlayerADPModal
          playerId={adpPlayer.player_id}
          playerName={adpPlayer.player_name}
          position={adpPlayer.position}
          team={adpPlayer.team}
          format={adpFormat}
          onClose={() => setAdpPlayer(null)}
        />
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Standings Tab (existing, preserved)
// ---------------------------------------------------------------------------

function StandingsTab({ standings }: { standings: LeagueDetail["standings"] }) {
  if (standings.length === 0) {
    return <p className="py-8 text-center text-text-secondary">No standings data available.</p>;
  }

  const sorted = [...standings].sort((a, b) => a.rank - b.rank);

  return (
    <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-surface">
            <th className="px-4 py-3 text-left font-medium text-text-secondary">Rank</th>
            <th className="px-4 py-3 text-left font-medium text-text-secondary">Team</th>
            <th className="px-4 py-3 text-right font-medium text-text-secondary">W</th>
            <th className="px-4 py-3 text-right font-medium text-text-secondary">L</th>
            <th className="px-4 py-3 text-right font-medium text-text-secondary">T</th>
            <th className="px-4 py-3 text-right font-medium text-text-secondary">PF</th>
            <th className="px-4 py-3 text-right font-medium text-text-secondary">PA</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((s) => (
            <tr key={s.id} className={`border-b border-border last:border-0${s.is_me ? " bg-accent/5" : ""}`}>
              <td className="px-4 py-3 font-score text-lg font-semibold text-accent">{s.rank}</td>
              <td className="px-4 py-3 font-medium text-text-primary">
                {s.team_name ?? "—"}
                {s.is_me && <span className="ml-2 text-xs text-accent">(You)</span>}
              </td>
              <td className="px-4 py-3 text-right text-text-primary">{s.wins}</td>
              <td className="px-4 py-3 text-right text-text-primary">{s.losses}</td>
              <td className="px-4 py-3 text-right text-text-secondary">{s.ties}</td>
              <td className="px-4 py-3 text-right font-score text-accent-green">{s.points_for}</td>
              <td className="px-4 py-3 text-right font-score text-text-secondary">{s.points_against}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Matchups Tab (existing, preserved)
// ---------------------------------------------------------------------------

function MatchupsTab({ matchups, teamName }: { matchups: LeagueDetail["recent_matchups"]; teamName: string | null }) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const userMatchups = matchups
    .filter((m) => m.is_user_matchup)
    .sort((a, b) => a.week - b.week);

  if (userMatchups.length === 0) {
    return <p className="py-8 text-center text-text-secondary">No matchup data available.</p>;
  }

  return (
    <div className="space-y-3">
      {userMatchups.map((m) => {
        const isHome = teamName != null && m.home_team_name === teamName;
        const myScore = parseFloat(isHome ? m.home_score : m.away_score);
        const oppScore = parseFloat(isHome ? m.away_score : m.home_score);
        const oppName = (isHome ? m.away_team_name : m.home_team_name) ?? "TBD";
        const won = myScore > oppScore;
        const tied = myScore === oppScore;
        const played = myScore > 0 || oppScore > 0;
        const expanded = expandedId === m.id;
        const hasStarters = m.home_starters != null || m.away_starters != null;

        return (
          <div
            key={m.id}
            className={`rounded-xl border bg-surface ${
              !played ? "border-border" :
              won ? "border-accent-green/30" :
              tied ? "border-border" :
              "border-destructive/30"
            }`}
          >
            <button
              type="button"
              className="w-full p-4 text-left"
              onClick={() => setExpandedId(expanded ? null : m.id)}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <p className="text-xs font-medium text-text-secondary">Week {m.week}</p>
                  {hasStarters && (
                    <span className="text-xs text-text-secondary">{expanded ? "▲" : "▼"}</span>
                  )}
                </div>
                {played && (
                  <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${
                    won ? "bg-accent-green/15 text-accent-green" :
                    tied ? "bg-surface-hover text-text-secondary" :
                    "bg-destructive/15 text-destructive"
                  }`}>
                    {won ? "W" : tied ? "T" : "L"}
                  </span>
                )}
              </div>
              <div className="mt-2 flex items-center justify-between">
                <div>
                  <p className="text-sm text-text-secondary">vs</p>
                  <p className="font-medium text-text-primary">{oppName}</p>
                </div>
                <div className="text-right">
                  <p className={`font-score text-xl font-bold ${
                    !played ? "text-text-secondary" :
                    won ? "text-accent-green" : tied ? "text-text-primary" : "text-destructive"
                  }`}>
                    {myScore.toFixed(1)}
                  </p>
                  <p className="font-score text-sm text-text-secondary">
                    {oppScore.toFixed(1)}
                  </p>
                </div>
              </div>
            </button>
            {expanded && hasStarters && (
              <MatchupStarters
                homeTeam={m.home_team_name}
                awayTeam={m.away_team_name}
                homeStarters={m.home_starters}
                awayStarters={m.away_starters}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

function MatchupStarters({
  homeTeam,
  awayTeam,
  homeStarters,
  awayStarters,
}: {
  homeTeam: string | null;
  awayTeam: string | null;
  homeStarters: MatchupPlayer[] | null;
  awayStarters: MatchupPlayer[] | null;
}) {
  return (
    <div className="border-t border-border px-4 pb-4 pt-3">
      <div className="grid gap-4 sm:grid-cols-2">
        <StarterColumn label={homeTeam ?? "Home"} starters={homeStarters} />
        <StarterColumn label={awayTeam ?? "Away"} starters={awayStarters} />
      </div>
    </div>
  );
}

function StarterColumn({
  label,
  starters,
}: {
  label: string;
  starters: MatchupPlayer[] | null;
}) {
  if (!starters || starters.length === 0) {
    return (
      <div>
        <p className="mb-2 text-xs font-semibold uppercase text-text-secondary">{label}</p>
        <p className="text-sm text-text-secondary">No starter data</p>
      </div>
    );
  }

  return (
    <div>
      <p className="mb-2 text-xs font-semibold uppercase text-text-secondary">{label}</p>
      <div className="space-y-1">
        {starters.map((s) => (
          <div key={s.player_id} className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2 min-w-0">
              {s.position && (
                <span className="w-7 shrink-0 text-xs font-semibold text-text-secondary">
                  {s.position}
                </span>
              )}
              <span className="truncate text-text-primary">{s.name}</span>
            </div>
            <span className="ml-2 shrink-0 font-score text-text-primary">
              {s.points != null ? s.points.toFixed(1) : "—"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Transactions Tab (existing, preserved)
// ---------------------------------------------------------------------------

function TransactionsTab({ transactions }: { transactions: LeagueDetail["recent_transactions"] }) {
  if (transactions.length === 0) {
    return <p className="py-8 text-center text-text-secondary">No transaction data available.</p>;
  }

  function typeColor(type: string) {
    switch (type) {
      case "add":
        return "text-accent-green";
      case "drop":
        return "text-destructive";
      case "trade":
        return "text-accent-orange";
      default:
        return "text-text-secondary";
    }
  }

  return (
    <div className="space-y-2">
      {transactions.map((t) => (
        <div
          key={t.id}
          className="rounded-xl border border-border bg-surface px-4 py-3"
        >
          <div className="flex flex-wrap items-center gap-2 sm:justify-between">
            <div className="flex items-center gap-3">
              <span className={`text-xs font-semibold uppercase ${typeColor(t.type)}`}>
                {t.type}
              </span>
              <span className="font-medium text-text-primary">{t.player_name}</span>
            </div>
            <div className="text-sm text-text-secondary">
              {t.from_team_name && <span>{t.from_team_name} &rarr; </span>}
              {t.to_team_name && <span>{t.to_team_name}</span>}
              {!t.from_team_name && !t.to_team_name && <span>Free Agent</span>}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function ordinal(n: number): string {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

function formatPoints(value: string): string {
  const num = parseFloat(value);
  if (isNaN(num)) return value;
  return num.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

function relativeTime(timestamp: string): string {
  const now = Date.now();
  const then = new Date(timestamp).getTime();
  const diffMs = now - then;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);
  const diffWeek = Math.floor(diffDay / 7);

  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;
  if (diffWeek < 4) return `${diffWeek}w ago`;
  return new Date(timestamp).toLocaleDateString();
}
