import { useState, useEffect } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { getPlayerADPHistory, type PlayerADPHistory } from "../api/adp";

const SOURCE_COLORS: Record<string, string> = {
  sleeper: "#4f8ff7",
  dynastyprocess: "#f59e0b",
  ffc: "#10b981",
  espn: "#ef4444",
  yahoo: "#8b5cf6",
};

function getSourceColor(source: string, index: number): string {
  const fallback = ["#6366f1", "#ec4899", "#14b8a6", "#f97316", "#84cc16"];
  return SOURCE_COLORS[source] ?? fallback[index % fallback.length];
}

interface PlayerADPModalProps {
  playerId: string;
  playerName: string;
  position: string;
  team: string;
  onClose: () => void;
}

export default function PlayerADPModal({
  playerId,
  playerName,
  position,
  team,
  onClose,
}: PlayerADPModalProps) {
  const [history, setHistory] = useState<PlayerADPHistory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getPlayerADPHistory(playerId)
      .then(setHistory)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load ADP history"),
      )
      .finally(() => setLoading(false));
  }, [playerId]);

  // Group data by season, with one key per source
  const sources = [...new Set(history.map((h) => h.source))];
  const bySeason = new Map<number, Record<string, number>>();
  for (const entry of history) {
    const row = bySeason.get(entry.season) ?? {};
    row[entry.source] = parseFloat(entry.adp);
    bySeason.set(entry.season, row);
  }
  const chartData = [...bySeason.entries()]
    .sort(([a], [b]) => a - b)
    .map(([season, values]) => ({ season: String(season), ...values }));

  // Compute Y-axis domain (inverted — lower ADP = higher on chart)
  const allAdp = history.map((h) => parseFloat(h.adp));
  const maxAdp = allAdp.length > 0 ? Math.ceil(Math.max(...allAdp) / 10) * 10 : 300;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      <div
        className="mx-4 w-full max-w-2xl rounded-xl border border-border bg-surface p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h2 className="font-heading text-xl font-bold text-text-primary">
              {playerName}
            </h2>
            <p className="text-sm text-text-secondary">
              {position} &middot; {team}
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-text-secondary transition-colors hover:text-text-primary"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Content */}
        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          </div>
        )}

        {error && (
          <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        )}

        {!loading && !error && chartData.length === 0 && (
          <p className="py-8 text-center text-text-secondary">
            No ADP history available for this player.
          </p>
        )}

        {!loading && !error && chartData.length > 0 && (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border, #333)" />
              <XAxis
                dataKey="season"
                stroke="var(--color-text-secondary, #888)"
                tick={{ fontSize: 12 }}
              />
              <YAxis
                reversed
                domain={[1, maxAdp]}
                stroke="var(--color-text-secondary, #888)"
                tick={{ fontSize: 12 }}
                label={{
                  value: "ADP",
                  angle: -90,
                  position: "insideLeft",
                  style: { fill: "var(--color-text-secondary, #888)", fontSize: 12 },
                }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "var(--color-surface, #1a1a2e)",
                  border: "1px solid var(--color-border, #333)",
                  borderRadius: "8px",
                  fontSize: "12px",
                }}
              />
              <Legend />
              {sources.map((source, i) => (
                <Line
                  key={source}
                  type="monotone"
                  dataKey={source}
                  name={source.charAt(0).toUpperCase() + source.slice(1)}
                  stroke={getSourceColor(source, i)}
                  strokeWidth={2}
                  dot={{ r: 4 }}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
