import { useLeagues } from "../hooks/useLeagues";
import LeagueCard from "../components/LeagueCard";
import EmptyState from "../components/EmptyState";

export default function DashboardPage() {
  const { leagues, loading, error } = useLeagues();

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      </div>
    );
  }

  if (error) {
    return (
      <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
        {error}
      </p>
    );
  }

  if (leagues.length === 0) {
    return (
      <EmptyState
        title="No leagues yet"
        description="Link a platform account and sync your leagues to get started."
        actionLabel="Link Account"
        actionTo="/link-accounts"
      />
    );
  }

  return (
    <div>
      <h1 className="font-heading text-2xl font-bold text-text-primary">
        My Leagues
      </h1>
      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {leagues.map((league) => (
          <LeagueCard key={league.id} league={league} />
        ))}
      </div>
    </div>
  );
}
