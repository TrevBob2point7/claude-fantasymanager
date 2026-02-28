# Fantasy Manager User Guide

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose installed
- A [Sleeper](https://sleeper.com/) fantasy football account (free)

### Starting the App

```bash
# Clone the repo and start all services
make up
```

This starts three containers: PostgreSQL database, FastAPI backend, and the React frontend. Once running, open **http://localhost:3000** in your browser.

To stop the app:

```bash
make down
```

### First-Time Setup

On first launch, the database is empty. You'll need to run the migration to create the schema:

```bash
make migrate
```

---

## Creating an Account

1. Open **http://localhost:3000** — you'll be redirected to the login page.
2. Click **Register** (link below the login form).
3. Fill in:
   - **Email** — any valid email address
   - **Password** — minimum 8 characters
   - **Display Name** — how your name appears in the app (optional)
4. Click **Register**. You'll be automatically logged in and taken to the dashboard.

To log in later, use the same email and password on the login page.

---

## Linking Your Sleeper Account

Before you can view leagues, you need to connect your Sleeper account.

1. From the sidebar, click **Link Accounts**.
2. Under **Link Sleeper Account**, enter your **Sleeper username** (the one you use to log in to the Sleeper app).
3. Click **Link**.

Your Sleeper account will appear in the **Linked Accounts** list. No password is needed — the Sleeper API is public and read-only.

### Removing a Linked Account

On the Link Accounts page, click the **Remove** button next to any linked account to unlink it.

---

## Discovering and Syncing Leagues

Once your Sleeper account is linked, you can pull in your fantasy leagues.

### Discovering Leagues

1. On the **Link Accounts** page, click **Discover** next to your linked account.
2. The app fetches all your NFL fantasy leagues from Sleeper for the 2025 season.
3. Discovered leagues appear below with their name, season, scoring type, and roster size. Leagues already imported show a **Linked** badge.

### Syncing Data

Click **Sync** next to your linked account to import all league data:

- **Leagues** — league names, settings, and your team assignments
- **Rosters** — current player rosters for each team
- **Matchups** — weekly head-to-head matchup scores
- **Standings** — win/loss records and point totals
- **Transactions** — adds, drops, trades, and waiver claims

A confirmation message shows what was synced. After syncing, navigate to the **Dashboard** to see your leagues.

### Background Sync

The app automatically syncs all linked accounts every 30 minutes in the background. You can also trigger a manual sync at any time from the Link Accounts page.

---

## Dashboard

The dashboard is your home screen after logging in. It shows a grid of **league cards** for every league you've synced.

Each card displays:
- League name
- Season year
- Scoring format (PPR, Half PPR, Standard)
- Your team name

Click any league card to view its details.

### Empty State

If you haven't linked any accounts or synced any leagues yet, the dashboard shows a prompt with a link to the **Link Accounts** page to get started.

---

## League Detail

Click a league card on the dashboard to see the full league detail view. The page has four tabs:

### Roster

Your current roster displayed in a table with columns:
- **Player** — player name
- **Pos** — position (QB, RB, WR, TE, K, DEF, etc.)
- **Team** — NFL team abbreviation
- **Slot** — roster slot assignment

### Standings

League standings sorted by rank, showing:
- **Rank** — overall league position
- **Team** — team name
- **W / L / T** — wins, losses, ties
- **PF** — total points scored (green)
- **PA** — total points allowed

### Matchups

Recent weekly matchups displayed as cards, each showing:
- **Week number**
- **Home team** vs **Away team**
- **Scores** for each side

### Transactions

Recent league transactions including:
- **Adds** (green) — players picked up from free agency
- **Drops** (red) — players released
- **Trades** (orange) — player-for-player swaps
- **Waivers** — waiver wire claims

Each entry shows the player name and the teams involved.

---

## Navigation

### Desktop

A sidebar on the left provides navigation:
- **Dashboard** — your league overview
- **Link Accounts** — manage platform connections

Your display name and a **Logout** button appear in the header.

### Mobile

On smaller screens, the sidebar collapses into a **hamburger menu** in the top-left corner. Tap it to open a slide-out navigation drawer. Tapping a link or the backdrop closes the drawer.

---

## Logging Out

Click **Logout** in the header (desktop) or in the mobile navigation drawer. You'll be redirected to the login page. Your session token is cleared from the browser.

---

## Configuration

The app is configured via environment variables. Copy `.env.example` to `.env` and adjust as needed:

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_USER` | `fantasy` | Database username |
| `POSTGRES_PASSWORD` | `fantasy_dev_password` | Database password |
| `POSTGRES_DB` | `fantasy_manager` | Database name |
| `DATABASE_URL` | `postgresql+asyncpg://...` | Full database connection string |
| `SECRET_KEY` | `change-me-...` | JWT signing key (change in production) |
| `CORS_ORIGINS` | `http://localhost:3000,...` | Allowed frontend origins |
| `SYNC_INTERVAL_MINUTES` | `30` | Background sync frequency |
| `SYNC_ENABLED` | `true` | Enable/disable background sync |

---

## Troubleshooting

### "No leagues yet" on the dashboard
You need to link a Sleeper account and sync first. Go to **Link Accounts**, link your account, then click **Sync**.

### Sync completes but no leagues appear
Your Sleeper username may not have any NFL fantasy leagues for the 2025 season. Verify your username is correct and that you have active leagues on Sleeper.

### Login says "Invalid email or password"
Double-check your email and password. Passwords are case-sensitive and must be at least 8 characters. If you forgot your password, you'll need to register a new account (password reset is not yet implemented).

### App won't start
Make sure Docker is running, then try:
```bash
make down
make build
make up
make migrate
```
