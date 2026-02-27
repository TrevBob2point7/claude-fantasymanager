import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { getLeagueDetail } from "../api/leagues";
import type { LeagueDetail } from "../api/types";

type Tab = "roster" | "standings" | "matchups" | "transactions";

const tabs: { key: Tab; label: string }[] = [
  { key: "roster", label: "Roster" },
  { key: "standings", label: "Standings" },
  { key: "matchups", label: "Matchups" },
  { key: "transactions", label: "Transactions" },
];

export default function LeagueDetailPage() {
  const { leagueId } = useParams<{ leagueId: string }>();
  const [league, setLeague] = useState<LeagueDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("roster");

  useEffect(() => {
    if (!leagueId) return;
    setLoading(true);
    getLeagueDetail(leagueId)
      .then(setLeague)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load league"),
      )
      .finally(() => setLoading(false));
  }, [leagueId]);

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

  return (
    <div>
      <Link to="/" className="text-sm text-accent hover:underline">
        &larr; Back to Dashboard
      </Link>

      {/* Header */}
      <div className="mt-4">
        <h1 className="font-heading text-2xl font-bold text-text-primary">
          {league.name}
        </h1>
        <p className="mt-1 text-text-secondary">
          {league.season} &middot; {league.scoring_type.toUpperCase()} &middot;{" "}
          {league.roster_size} roster spots &middot; {league.team_name}
        </p>
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
        {activeTab === "roster" && <RosterTab roster={league.roster} />}
        {activeTab === "standings" && <StandingsTab standings={league.standings} />}
        {activeTab === "matchups" && <MatchupsTab matchups={league.recent_matchups} />}
        {activeTab === "transactions" && (
          <TransactionsTab transactions={league.recent_transactions} />
        )}
      </div>
    </div>
  );
}

function RosterTab({ roster }: { roster: LeagueDetail["roster"] }) {
  if (roster.length === 0) {
    return <p className="py-8 text-center text-text-secondary">No roster data available.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-surface">
            <th className="px-4 py-3 text-left font-medium text-text-secondary">Player</th>
            <th className="px-4 py-3 text-left font-medium text-text-secondary">Pos</th>
            <th className="px-4 py-3 text-left font-medium text-text-secondary">Team</th>
            <th className="px-4 py-3 text-left font-medium text-text-secondary">Slot</th>
          </tr>
        </thead>
        <tbody>
          {roster.map((player) => (
            <tr key={player.id} className="border-b border-border last:border-0">
              <td className="px-4 py-3 font-medium text-text-primary">{player.player_name}</td>
              <td className="px-4 py-3 text-text-secondary">{player.position}</td>
              <td className="px-4 py-3 text-text-secondary">{player.team}</td>
              <td className="px-4 py-3 text-text-secondary">{player.slot}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

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
            <tr key={s.id} className="border-b border-border last:border-0">
              <td className="px-4 py-3 font-score text-lg font-semibold text-accent">{s.rank}</td>
              <td className="px-4 py-3 font-medium text-text-primary">{s.team_name}</td>
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

function MatchupsTab({ matchups }: { matchups: LeagueDetail["recent_matchups"] }) {
  if (matchups.length === 0) {
    return <p className="py-8 text-center text-text-secondary">No matchup data available.</p>;
  }

  return (
    <div className="space-y-3">
      {matchups.map((m) => (
        <div
          key={m.id}
          className="rounded-xl border border-border bg-surface p-4"
        >
          <p className="mb-2 text-xs font-medium text-text-secondary">Week {m.week}</p>
          <div className="flex items-center justify-between">
            <div className="flex-1">
              <p className="font-medium text-text-primary">{m.home_team_name}</p>
              <p className="font-score text-xl font-semibold text-accent">{m.home_score}</p>
            </div>
            <span className="px-4 text-sm text-text-secondary">vs</span>
            <div className="flex-1 text-right">
              <p className="font-medium text-text-primary">{m.away_team_name}</p>
              <p className="font-score text-xl font-semibold text-accent">{m.away_score}</p>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function TransactionsTab({ transactions }: { transactions: LeagueDetail["recent_transactions"] }) {
  if (transactions.length === 0) {
    return <p className="py-8 text-center text-text-secondary">No transaction data available.</p>;
  }

  function typeLabel(type: string) {
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
              <span className={`text-xs font-semibold uppercase ${typeLabel(t.type)}`}>
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
