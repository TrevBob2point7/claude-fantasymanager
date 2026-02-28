import { Link } from "react-router-dom";
import type { League } from "../api/types";

export default function LeagueCard({ league }: { league: League }) {
  return (
    <Link
      to={`/leagues/${league.id}`}
      className="block rounded-xl border border-border bg-surface p-5 transition-colors hover:bg-surface-hover"
    >
      <h3 className="font-heading text-lg font-semibold text-text-primary">
        {league.name}
      </h3>
      <p className="mt-1 text-sm text-text-secondary">
        {league.season} &middot; {league.scoring_type?.toUpperCase() ?? "—"} &middot;{" "}
        {league.roster_size ?? "—"} roster spots
      </p>
      <div className="mt-3 flex items-center justify-between">
        <span className="text-sm text-text-secondary">{league.team_name ?? "My Team"}</span>
        <span className="rounded-full bg-surface-hover px-2.5 py-0.5 text-xs text-text-secondary">
          {league.platform_type}
        </span>
      </div>
    </Link>
  );
}
