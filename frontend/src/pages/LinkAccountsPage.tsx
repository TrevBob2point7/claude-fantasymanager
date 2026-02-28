import { useState, useEffect, type FormEvent } from "react";
import { getPlatformAccounts, createPlatformAccount, deletePlatformAccount } from "../api/platforms";
import { discoverLeagues } from "../api/leagues";
import { triggerSync } from "../api/sync";
import type { PlatformAccount, DiscoveredLeague } from "../api/types";

export default function LinkAccountsPage() {
  const [accounts, setAccounts] = useState<PlatformAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Link form state
  const [username, setUsername] = useState("");
  const [linking, setLinking] = useState(false);
  const [linkError, setLinkError] = useState<string | null>(null);

  // Discover state
  const [discovering, setDiscovering] = useState<string | null>(null);
  const [discovered, setDiscovered] = useState<DiscoveredLeague[]>([]);
  const [discoverError, setDiscoverError] = useState<string | null>(null);

  // Sync state
  const [syncingAccount, setSyncingAccount] = useState<string | null>(null);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);

  useEffect(() => {
    loadAccounts();
  }, []);

  function loadAccounts() {
    setLoading(true);
    getPlatformAccounts()
      .then(setAccounts)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load accounts"),
      )
      .finally(() => setLoading(false));
  }

  async function handleLink(e: FormEvent) {
    e.preventDefault();
    setLinking(true);
    setLinkError(null);
    try {
      await createPlatformAccount({
        platform_type: "sleeper",
        platform_username: username,
      });
      setUsername("");
      loadAccounts();
    } catch (err) {
      setLinkError(err instanceof Error ? err.message : "Failed to link account");
    } finally {
      setLinking(false);
    }
  }

  async function handleDelete(accountId: string) {
    try {
      await deletePlatformAccount(accountId);
      loadAccounts();
      if (discovering === accountId) {
        setDiscovered([]);
        setDiscovering(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove account");
    }
  }

  async function handleDiscover(accountId: string) {
    setDiscovering(accountId);
    setDiscoverError(null);
    setDiscovered([]);
    try {
      const leagues = await discoverLeagues(accountId, 2025);
      setDiscovered(leagues);
    } catch (err) {
      setDiscoverError(
        err instanceof Error ? err.message : "Failed to discover leagues",
      );
    }
  }

  async function handleSync(accountId: string) {
    setSyncingAccount(accountId);
    setSyncMessage(null);
    try {
      const result = await triggerSync(accountId);
      setSyncMessage(
        `Sync ${result.status}: ${result.synced.join(", ")}`,
      );
      loadAccounts();
    } catch (err) {
      setSyncMessage(err instanceof Error ? err.message : "Sync failed");
    } finally {
      setSyncingAccount(null);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="font-heading text-2xl font-bold text-text-primary">
        Link Accounts
      </h1>
      <p className="mt-1 text-text-secondary">
        Connect your fantasy football platform accounts.
      </p>

      {error && (
        <p className="mt-4 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      {/* Link form */}
      <form
        onSubmit={handleLink}
        className="mt-6 rounded-xl border border-border bg-surface p-4"
      >
        <h2 className="mb-3 font-heading text-lg font-semibold text-text-primary">
          Link Sleeper Account
        </h2>
        {linkError && (
          <p className="mb-3 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {linkError}
          </p>
        )}
        <div className="flex flex-col gap-3 sm:flex-row">
          <label htmlFor="sleeper-username" className="sr-only">
            Sleeper Username
          </label>
          <input
            id="sleeper-username"
            type="text"
            required
            placeholder="Sleeper username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="h-11 flex-1 rounded-md border border-border bg-surface px-3 text-text-primary outline-none placeholder:text-text-secondary focus:ring-2 focus:ring-accent"
          />
          <button
            type="submit"
            disabled={linking}
            className="h-11 rounded-md bg-accent px-4 font-semibold text-background transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {linking ? "Linking…" : "Link"}
          </button>
        </div>
      </form>

      {/* Linked accounts */}
      {accounts.length > 0 && (
        <div className="mt-6 space-y-3">
          <h2 className="font-heading text-lg font-semibold text-text-primary">
            Linked Accounts
          </h2>
          {accounts.map((account) => (
            <div
              key={account.id}
              className="rounded-xl border border-border bg-surface p-4"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-text-primary">
                    {account.platform_username}
                  </p>
                  <p className="text-sm text-text-secondary">
                    {account.platform_type}
                  </p>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  onClick={() => handleDiscover(account.id)}
                  disabled={discovering === account.id}
                  className="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary transition-colors hover:bg-surface-hover"
                >
                  Discover
                </button>
                <button
                  onClick={() => handleSync(account.id)}
                  disabled={syncingAccount === account.id}
                  className="rounded-md bg-accent px-3 py-2 text-sm font-semibold text-background transition-opacity hover:opacity-90 disabled:opacity-50"
                >
                  {syncingAccount === account.id ? "Syncing…" : "Sync"}
                </button>
                <button
                  onClick={() => handleDelete(account.id)}
                  className="rounded-md border border-destructive px-3 py-2 text-sm text-destructive transition-colors hover:bg-destructive/10"
                >
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {syncMessage && (
        <p className="mt-4 rounded-md bg-accent-green/10 px-3 py-2 text-sm text-accent-green">
          {syncMessage}
        </p>
      )}

      {/* Discovered leagues */}
      {discovered.length > 0 && (
        <div className="mt-6 space-y-3">
          <h2 className="font-heading text-lg font-semibold text-text-primary">
            Discovered Leagues
          </h2>
          {discovered.map((league) => (
            <div
              key={league.platform_league_id}
              className="flex items-center justify-between rounded-xl border border-border bg-surface p-4"
            >
              <div>
                <p className="font-medium text-text-primary">{league.name}</p>
                <p className="text-sm text-text-secondary">
                  {league.season} &middot; {league.scoring_type?.toUpperCase() ?? "—"} &middot;{" "}
                  {league.roster_size ?? "—"} roster spots
                </p>
              </div>
              {league.already_linked && (
                <span className="rounded-full bg-accent-green/10 px-3 py-1 text-xs font-medium text-accent-green">
                  Linked
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      {discoverError && (
        <p className="mt-4 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {discoverError}
        </p>
      )}
    </div>
  );
}
