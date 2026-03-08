from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    DataType,
    League,
    Matchup,
    PlatformAccount,
    PlatformType,
    Roster,
    Standing,
    SyncLog,
    SyncStatus,
    Transaction,
    TransactionType,
    UserLeague,
)
from app.models.team_bye_week import TeamByeWeek
from app.platforms.registry import get_adapter
from app.platforms.schemas import PlatformMatchup as PlatformMatchupSchema
from app.sync.bye_weeks import sync_bye_weeks
from app.sync.player_import import (
    get_or_create_player_by_mfl_id,
    get_or_create_player_by_sleeper_id,
)

logger = logging.getLogger(__name__)


class SyncEngine:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _get_or_create_player(
        self,
        platform_type: PlatformType,
        player_id: str,
        pdata: dict,
    ):
        """Resolve a platform player ID to a Player record, platform-aware."""
        if platform_type == PlatformType.mfl:
            full_name = pdata.get("name") or "Unknown Player"
            return await get_or_create_player_by_mfl_id(
                self.db,
                player_id,
                full_name=full_name,
                position=pdata.get("position"),
                team=pdata.get("team"),
            )
        else:
            full_name = (
                f"{pdata.get('first_name', '')} {pdata.get('last_name', '')}".strip()
                or pdata.get("full_name", "Unknown Player")
            )
            return await get_or_create_player_by_sleeper_id(
                self.db,
                player_id,
                full_name=full_name,
                position=pdata.get("position"),
                team=pdata.get("team"),
            )

    async def _log_start(
        self, user_id: UUID, platform_type: PlatformType, data_type: DataType
    ) -> SyncLog:
        log = SyncLog(
            user_id=user_id,
            platform_type=platform_type,
            data_type=data_type,
            status=SyncStatus.in_progress,
            started_at=datetime.now(UTC),
        )
        self.db.add(log)
        await self.db.flush()
        return log

    async def _log_complete(self, log: SyncLog) -> None:
        log.status = SyncStatus.completed
        log.completed_at = datetime.now(UTC)
        await self.db.flush()

    async def _log_error(self, log: SyncLog, error: str) -> None:
        try:
            log.status = SyncStatus.failed
            log.completed_at = datetime.now(UTC)
            log.error_message = error
            await self.db.flush()
        except Exception:
            # Session may be in failed state; rollback and retry
            await self.db.rollback()
            new_log = SyncLog(
                user_id=log.user_id,
                platform_type=log.platform_type,
                data_type=log.data_type,
                status=SyncStatus.failed,
                started_at=log.started_at,
                completed_at=datetime.now(UTC),
                error_message=error,
            )
            self.db.add(new_log)
            await self.db.flush()

    async def sync_leagues(
        self, user_id: UUID, platform_account: PlatformAccount, season: int
    ) -> list[League]:
        """Discover and upsert leagues for a platform account."""
        log = await self._log_start(user_id, platform_account.platform_type, DataType.leagues)
        try:
            adapter = get_adapter(
                platform_account.platform_type,
                credentials_json=platform_account.credentials_json,
            )

            platform_user_id = platform_account.platform_user_id

            # Resolve username to numeric user ID if needed (Sleeper only —
            # MFL uses the username directly as the user ID).
            if (
                platform_account.platform_type != PlatformType.mfl
                and platform_account.platform_username
                and (not platform_user_id or not platform_user_id.isdigit())
            ):
                user_info = await adapter.get_user(platform_account.platform_username)
                platform_user_id = user_info.user_id
                platform_account.platform_user_id = platform_user_id
                await self.db.flush()

            if not platform_user_id:
                raise ValueError("No platform user ID or username available")

            platform_leagues = await adapter.get_leagues(platform_user_id, season)

            # MFL's get_leagues (myleagues) returns minimal data — enrich
            # each league with full metadata from get_league.
            if platform_account.platform_type == PlatformType.mfl:
                enriched = []
                for idx, pl in enumerate(platform_leagues, 1):
                    logger.info(
                        "MFL enriching league %d/%d: %s",
                        idx, len(platform_leagues), pl.league_id,
                    )
                    full = await adapter.get_league(pl.league_id)
                    full.user_franchise_id = pl.user_franchise_id
                    enriched.append(full)
                platform_leagues = enriched

            leagues = []
            for pl in platform_leagues:
                # Merge roster_positions and user_franchise_id into settings_json
                settings_json = {**(pl.settings or {})}
                if pl.roster_positions is not None:
                    settings_json["roster_positions"] = pl.roster_positions
                if pl.user_franchise_id:
                    settings_json["user_franchise_id"] = pl.user_franchise_id

                # Upsert league
                stmt = (
                    pg_insert(League)
                    .values(
                        platform_type=platform_account.platform_type,
                        platform_league_id=pl.league_id,
                        name=pl.name,
                        season=pl.season,
                        roster_size=pl.roster_size,
                        scoring_type=pl.scoring_type,
                        league_type=pl.league_type,
                        settings_json=settings_json,
                        previous_league_id=pl.previous_league_id,
                    )
                    .on_conflict_do_update(
                        index_elements=["platform_type", "platform_league_id", "season"],
                        set_={
                            "name": pl.name,
                            "roster_size": pl.roster_size,
                            "scoring_type": pl.scoring_type,
                            "league_type": pl.league_type,
                            "settings_json": settings_json,
                            "previous_league_id": pl.previous_league_id,
                        },
                    )
                    .returning(League)
                )
                result = await self.db.execute(stmt)
                league = result.scalar_one()
                # Expire to ensure we see the updated values from the upsert
                await self.db.refresh(league)
                leagues.append(league)

            # Auto-assign league_group_id.
            # For MFL, the same platform_league_id spans multiple seasons,
            # so we group by platform_league_id first, then walk the
            # previous_league_id chain for cross-ID grouping (Sleeper).
            #
            # Step 1: Group leagues that share a platform_league_id (MFL)
            # or are linked via previous_league_id chains.
            by_plat_id: dict[str, list[League]] = {}
            for lg in leagues:
                by_plat_id.setdefault(lg.platform_league_id, []).append(lg)

            # For each group of same-platform_league_id leagues, unify
            # their league_group_id (pick existing or create new).
            for siblings in by_plat_id.values():
                # Also check DB for other seasons of the same league
                existing_group = None
                for lg in siblings:
                    if lg.league_group_id:
                        existing_group = lg.league_group_id
                        break
                if not existing_group:
                    plat_id = siblings[0].platform_league_id
                    result = await self.db.execute(
                        select(League.league_group_id).where(
                            League.platform_type == platform_account.platform_type,
                            League.platform_league_id == plat_id,
                            League.league_group_id.isnot(None),
                        ).limit(1)
                    )
                    existing_group = result.scalar_one_or_none()

                group_id = existing_group or uuid4()
                for lg in siblings:
                    lg.league_group_id = group_id

            # Step 2: Walk previous_league_id chains to merge groups
            # across different platform_league_ids (e.g. Sleeper).
            batch_lookup = {
                lg.platform_league_id: lg for lg in leagues
            }
            # Map current group_id -> canonical group_id for merging
            group_remap: dict[UUID, UUID] = {}

            for league in leagues:
                prev_id = league.previous_league_id
                if not prev_id or prev_id == league.platform_league_id:
                    continue  # same-ID grouping already handled above

                # Find the group of the previous league
                prev_league = batch_lookup.get(prev_id)
                prev_group = prev_league.league_group_id if prev_league else None
                if not prev_group:
                    result = await self.db.execute(
                        select(League.league_group_id).where(
                            League.platform_type == platform_account.platform_type,
                            League.platform_league_id == prev_id,
                            League.league_group_id.isnot(None),
                        ).limit(1)
                    )
                    prev_group = result.scalar_one_or_none()

                if prev_group and prev_group != league.league_group_id:
                    # Merge: map league's current group to prev_group
                    old_group = league.league_group_id
                    if old_group:
                        group_remap[old_group] = prev_group

            # Apply remaps
            if group_remap:
                for lg in leagues:
                    if lg.league_group_id in group_remap:
                        lg.league_group_id = group_remap[lg.league_group_id]

            # Also update DB rows that share remapped group IDs
            for old_gid, new_gid in group_remap.items():
                await self.db.execute(
                    sa.update(League)
                    .where(League.league_group_id == old_gid)
                    .values(league_group_id=new_gid)
                )

            await self.db.flush()
            await self._log_complete(log)
            return leagues
        except Exception as e:
            await self._log_error(log, str(e))
            raise

    async def _sync_user_leagues(
        self,
        league: League,
        user_id: UUID | None,
        platform_user_id: str | None,
        credentials_json: dict | None = None,
        adapter: object | None = None,
    ) -> None:
        """Create user_league entries for ALL teams in a league.

        Fetches rosters and league users from the platform, then upserts a
        user_league row per roster using roster_id as platform_team_id.
        Only the roster owned by the current app user gets user_id set;
        all other teams get user_id=NULL.
        """
        if adapter is None:
            adapter = get_adapter(league.platform_type, credentials_json=credentials_json)
        platform_rosters = await adapter.get_rosters(league.platform_league_id)
        league_users = await adapter.get_league_users(league.platform_league_id)

        # Build owner_id -> league user info lookup
        user_info_by_owner = {lu.user_id: lu for lu in league_users}

        # For MFL, match via franchise_id stored in settings_json
        effective_user_id = platform_user_id
        if league.platform_type == PlatformType.mfl:
            settings = league.settings_json or {}
            effective_user_id = settings.get("user_franchise_id") or platform_user_id

        for pr in platform_rosters:
            # Determine if this roster belongs to the current app user
            is_current_user = (
                effective_user_id and pr.owner_id == effective_user_id and user_id is not None
            )
            row_user_id = user_id if is_current_user else None

            # Get team name from league users data
            lu = user_info_by_owner.get(pr.owner_id)
            team_name = None
            if lu:
                team_name = lu.team_name or lu.display_name

            stmt = (
                pg_insert(UserLeague)
                .values(
                    user_id=row_user_id,
                    league_id=league.id,
                    platform_team_id=pr.roster_id,
                    team_name=team_name,
                )
                .on_conflict_do_update(
                    index_elements=["league_id", "platform_team_id"],
                    set_={
                        "user_id": row_user_id,
                        "team_name": team_name,
                    },
                )
            )
            await self.db.execute(stmt)

        await self.db.flush()

    async def sync_rosters(
        self,
        league: League,
        user_id: UUID,
        players_map: dict[str, dict] | None = None,
        credentials_json: dict | None = None,
        adapter: object | None = None,
    ) -> None:
        """Sync rosters for a league."""
        log = await self._log_start(user_id, league.platform_type, DataType.rosters)
        try:
            if adapter is None:
                adapter = get_adapter(league.platform_type, credentials_json=credentials_json)
            platform_rosters = await adapter.get_rosters(league.platform_league_id)

            # Fetch player data if not provided
            if players_map is None:
                try:
                    players_map = await adapter.get_players_map()
                except Exception:
                    logger.warning("Could not fetch players map, using stubs")
                    players_map = {}

            # Get user_leagues for this league keyed by platform_team_id
            result = await self.db.execute(
                select(UserLeague).where(UserLeague.league_id == league.id)
            )
            user_leagues = result.scalars().all()
            ul_by_platform_id = {
                ul.platform_team_id: ul for ul in user_leagues if ul.platform_team_id
            }

            # Collect user_league IDs that will be refreshed
            ul_ids_to_refresh = []
            for pr in platform_rosters:
                ul = ul_by_platform_id.get(pr.roster_id)
                if ul is not None:
                    ul_ids_to_refresh.append(ul.id)

            # Delete existing roster rows for affected user_leagues
            if ul_ids_to_refresh:
                await self.db.execute(
                    sa.delete(Roster).where(Roster.user_league_id.in_(ul_ids_to_refresh))
                )

            # Get roster_positions from league settings_json for slot inference
            roster_positions = (
                league.settings_json.get("roster_positions", []) if league.settings_json else []
            )
            starter_slots = [pos for pos in roster_positions if pos not in ("BN", "IR")]

            for pr in platform_rosters:
                ul = ul_by_platform_id.get(pr.roster_id)
                if ul is None:
                    continue

                # Build starter → slot mapping using position order
                starter_slot_map: dict[str, str] = {}
                for i, player_id in enumerate(pr.starters):
                    if i < len(starter_slots):
                        starter_slot_map[player_id] = starter_slots[i]

                for player_id_str in pr.player_ids:
                    pdata = players_map.get(player_id_str, {})
                    player = await self._get_or_create_player(
                        league.platform_type,
                        player_id_str,
                        pdata,
                    )
                    slot = None
                    if starter_slots and player_id_str in starter_slot_map:
                        slot = starter_slot_map[player_id_str]
                    elif not starter_slots and player_id_str in pr.starters:
                        slot = "STARTER"
                    elif player_id_str in pr.taxi:
                        slot = "TAXI"

                    self.db.add(
                        Roster(
                            user_league_id=ul.id,
                            player_id=player.id,
                            slot=slot,
                        )
                    )

            await self.db.flush()
            await self._log_complete(log)
        except Exception as e:
            await self._log_error(log, str(e))
            raise

    def _build_starters_json(
        self,
        pm: PlatformMatchupSchema,
        players_map: dict[str, dict],
        starter_slots: list[str] | None = None,
        platform_type: PlatformType | None = None,
    ) -> list[dict] | None:
        """Build starters JSON from a PlatformMatchup's starters data."""
        if not pm.starters:
            return None
        result = []
        for i, pid in enumerate(pm.starters):
            pdata = players_map.get(pid, {})
            if platform_type == PlatformType.mfl:
                name = pdata.get("name") or "Unknown"
            else:
                name = (
                    f"{pdata.get('first_name', '')} {pdata.get('last_name', '')}".strip()
                    or pdata.get("full_name", "Unknown")
                )
            slot = starter_slots[i] if starter_slots and i < len(starter_slots) else None
            result.append(
                {
                    "player_id": pid,
                    "name": name,
                    "position": pdata.get("position"),
                    "points": pm.starters_points.get(pid),
                    "slot": slot,
                }
            )
        return result

    async def sync_matchups(
        self,
        league: League,
        user_id: UUID,
        week: int,
        players_map: dict[str, dict] | None = None,
        credentials_json: dict | None = None,
        adapter: object | None = None,
    ) -> None:
        """Sync matchups for a league week."""
        log = await self._log_start(user_id, league.platform_type, DataType.matchups)
        try:
            if adapter is None:
                adapter = get_adapter(league.platform_type, credentials_json=credentials_json)
            platform_matchups = await adapter.get_matchups(league.platform_league_id, week)

            if players_map is None:
                players_map = {}

            # Extract starter slot labels from league settings
            roster_positions = (
                league.settings_json.get("roster_positions", []) if league.settings_json else []
            )
            starter_slots = [pos for pos in roster_positions if pos not in ("BN", "IR")]

            # Get user_leagues for this league
            result = await self.db.execute(
                select(UserLeague).where(UserLeague.league_id == league.id)
            )
            user_leagues = result.scalars().all()
            ul_by_platform_id = {
                ul.platform_team_id: ul for ul in user_leagues if ul.platform_team_id
            }

            # Group matchups by matchup_id
            groups: dict[int, list] = {}
            for m in platform_matchups:
                groups.setdefault(m.matchup_id, []).append(m)

            for _matchup_id, entries in groups.items():
                if len(entries) < 2:
                    continue
                entries.sort(key=lambda e: e.roster_id)
                home = entries[0]
                away = entries[1]

                home_ul = ul_by_platform_id.get(home.roster_id)
                away_ul = ul_by_platform_id.get(away.roster_id)
                if not home_ul or not away_ul:
                    continue

                home_starters = self._build_starters_json(
                    home,
                    players_map,
                    starter_slots or None,
                    platform_type=league.platform_type,
                )
                away_starters = self._build_starters_json(
                    away,
                    players_map,
                    starter_slots or None,
                    platform_type=league.platform_type,
                )

                # Check if matchup already exists
                existing = await self.db.execute(
                    select(Matchup).where(
                        Matchup.league_id == league.id,
                        Matchup.week == week,
                        or_(
                            and_(
                                Matchup.home_user_league_id == home_ul.id,
                                Matchup.away_user_league_id == away_ul.id,
                            ),
                            and_(
                                Matchup.home_user_league_id == away_ul.id,
                                Matchup.away_user_league_id == home_ul.id,
                            ),
                        ),
                    )
                )
                matchup = existing.scalar_one_or_none()
                if matchup:
                    matchup.home_score = home.points
                    matchup.away_score = away.points
                    matchup.home_starters_json = home_starters
                    matchup.away_starters_json = away_starters
                else:
                    matchup = Matchup(
                        league_id=league.id,
                        week=week,
                        home_user_league_id=home_ul.id,
                        away_user_league_id=away_ul.id,
                        home_score=home.points,
                        away_score=away.points,
                        home_starters_json=home_starters,
                        away_starters_json=away_starters,
                    )
                    self.db.add(matchup)

            await self.db.flush()
            await self._log_complete(log)
        except Exception as e:
            await self._log_error(log, str(e))
            raise

    async def sync_standings(
        self, league: League, user_id: UUID, credentials_json: dict | None = None,
        adapter: object | None = None,
    ) -> None:
        """Calculate standings from matchups, or use platform-provided standings."""
        log = await self._log_start(user_id, league.platform_type, DataType.standings)
        try:
            if adapter is None:
                adapter = get_adapter(league.platform_type, credentials_json=credentials_json)
            platform_standings = await adapter.get_standings(league.platform_league_id)

            result = await self.db.execute(
                select(UserLeague).where(UserLeague.league_id == league.id)
            )
            user_leagues = result.scalars().all()

            if platform_standings is not None:
                # Use platform-provided standings directly
                ul_by_platform_id = {
                    ul.platform_team_id: ul for ul in user_leagues if ul.platform_team_id
                }

                # Sort by wins desc, then points_for desc for ranking
                platform_standings.sort(
                    key=lambda ps: (ps.wins, ps.points_for),
                    reverse=True,
                )

                for rank, ps in enumerate(platform_standings, start=1):
                    ul = ul_by_platform_id.get(ps.franchise_id)
                    if ul is None:
                        continue
                    stmt = (
                        pg_insert(Standing)
                        .values(
                            league_id=league.id,
                            user_league_id=ul.id,
                            wins=ps.wins,
                            losses=ps.losses,
                            ties=ps.ties,
                            points_for=round(ps.points_for, 2),
                            points_against=round(ps.points_against, 2),
                            rank=rank,
                        )
                        .on_conflict_do_update(
                            index_elements=["league_id", "user_league_id"],
                            set_={
                                "wins": ps.wins,
                                "losses": ps.losses,
                                "ties": ps.ties,
                                "points_for": round(ps.points_for, 2),
                                "points_against": round(ps.points_against, 2),
                                "rank": rank,
                            },
                        )
                    )
                    await self.db.execute(stmt)
            else:
                # Compute standings from matchups
                result = await self.db.execute(
                    select(Matchup).where(Matchup.league_id == league.id)
                )
                matchups = result.scalars().all()

                # Calculate W/L/T and points for each user_league
                stats: dict[UUID, dict] = {
                    ul.id: {"wins": 0, "losses": 0, "ties": 0, "pf": 0.0, "pa": 0.0}
                    for ul in user_leagues
                }

                for m in matchups:
                    if m.home_score is None or m.away_score is None:
                        continue
                    h_id = m.home_user_league_id
                    a_id = m.away_user_league_id
                    if h_id in stats:
                        stats[h_id]["pf"] += float(m.home_score)
                        stats[h_id]["pa"] += float(m.away_score)
                    if a_id in stats:
                        stats[a_id]["pf"] += float(m.away_score)
                        stats[a_id]["pa"] += float(m.home_score)

                    if m.home_score > m.away_score:
                        if h_id in stats:
                            stats[h_id]["wins"] += 1
                        if a_id in stats:
                            stats[a_id]["losses"] += 1
                    elif m.away_score > m.home_score:
                        if a_id in stats:
                            stats[a_id]["wins"] += 1
                        if h_id in stats:
                            stats[h_id]["losses"] += 1
                    else:
                        if h_id in stats:
                            stats[h_id]["ties"] += 1
                        if a_id in stats:
                            stats[a_id]["ties"] += 1

                # Sort by wins desc, then points_for desc for ranking
                sorted_ids = sorted(
                    stats.keys(),
                    key=lambda uid: (stats[uid]["wins"], stats[uid]["pf"]),
                    reverse=True,
                )

                for rank, ul_id in enumerate(sorted_ids, start=1):
                    s = stats[ul_id]
                    stmt = (
                        pg_insert(Standing)
                        .values(
                            league_id=league.id,
                            user_league_id=ul_id,
                            wins=s["wins"],
                            losses=s["losses"],
                            ties=s["ties"],
                            points_for=round(s["pf"], 2),
                            points_against=round(s["pa"], 2),
                            rank=rank,
                        )
                        .on_conflict_do_update(
                            index_elements=["league_id", "user_league_id"],
                            set_={
                                "wins": s["wins"],
                                "losses": s["losses"],
                                "ties": s["ties"],
                                "points_for": round(s["pf"], 2),
                                "points_against": round(s["pa"], 2),
                                "rank": rank,
                            },
                        )
                    )
                    await self.db.execute(stmt)

            await self.db.flush()
            await self._log_complete(log)
        except Exception as e:
            await self._log_error(log, str(e))
            raise

    async def sync_transactions(
        self,
        league: League,
        user_id: UUID,
        week: int,
        players_map: dict[str, dict] | None = None,
        credentials_json: dict | None = None,
        adapter: object | None = None,
    ) -> None:
        """Sync transactions for a league week."""
        log = await self._log_start(user_id, league.platform_type, DataType.transactions)
        try:
            if adapter is None:
                adapter = get_adapter(league.platform_type, credentials_json=credentials_json)
            platform_txns = await adapter.get_transactions(league.platform_league_id, week)
            if players_map is None:
                players_map = {}

            result = await self.db.execute(
                select(UserLeague).where(UserLeague.league_id == league.id)
            )
            user_leagues = result.scalars().all()
            ul_by_platform_id = {
                ul.platform_team_id: ul for ul in user_leagues if ul.platform_team_id
            }

            # Delete existing transactions for this league+week before re-inserting
            await self.db.execute(
                sa.delete(Transaction).where(
                    Transaction.league_id == league.id,
                    Transaction.week == week,
                )
            )

            for pt in platform_txns:
                tx_type = (
                    TransactionType(pt.type)
                    if pt.type in TransactionType.__members__
                    else TransactionType.add
                )

                # Process each added player as a separate transaction
                for player_id_str in pt.player_ids_added:
                    pdata = players_map.get(player_id_str, {})
                    player = await self._get_or_create_player(
                        league.platform_type,
                        player_id_str,
                        pdata,
                    )
                    to_ul = None
                    for rid in pt.roster_ids:
                        if rid in ul_by_platform_id:
                            to_ul = ul_by_platform_id[rid]
                            break

                    txn = Transaction(
                        league_id=league.id,
                        type=tx_type,
                        week=week,
                        player_id=player.id,
                        to_user_league_id=to_ul.id if to_ul else None,
                        timestamp=datetime.fromtimestamp(pt.timestamp / 1000, tz=UTC)
                        if pt.timestamp
                        else datetime.now(UTC),
                    )
                    self.db.add(txn)

                for player_id_str in pt.player_ids_dropped:
                    pdata = players_map.get(player_id_str, {})
                    player = await self._get_or_create_player(
                        league.platform_type,
                        player_id_str,
                        pdata,
                    )
                    from_ul = None
                    for rid in pt.roster_ids:
                        if rid in ul_by_platform_id:
                            from_ul = ul_by_platform_id[rid]
                            break

                    txn = Transaction(
                        league_id=league.id,
                        type=tx_type,
                        week=week,
                        player_id=player.id,
                        from_user_league_id=from_ul.id if from_ul else None,
                        timestamp=datetime.fromtimestamp(pt.timestamp / 1000, tz=UTC)
                        if pt.timestamp
                        else datetime.now(UTC),
                    )
                    self.db.add(txn)

            await self.db.flush()
            await self._log_complete(log)
        except Exception as e:
            await self._log_error(log, str(e))
            raise

    async def sync_historical_seasons(
        self,
        league: League,
        user_id: UUID,
        platform_account: PlatformAccount,
        players_map: dict[str, dict] | None = None,
        adapter: object | None = None,
    ) -> None:
        """Sync historical league seasons.

        For MFL, uses the history entries (same league_id, different years).
        For Sleeper, walks the previous_league_id chain.
        Only syncs league metadata, user_leagues, and standings.
        Matchups and transactions are fetched lazily when the user views them.
        """
        if adapter is None:
            adapter = get_adapter(
                platform_account.platform_type,
                credentials_json=platform_account.credentials_json,
            )
        credentials_json = platform_account.credentials_json

        if platform_account.platform_type == PlatformType.mfl:
            await self._sync_mfl_historical(
                league, user_id, platform_account,
                credentials_json, adapter, players_map,
            )
        else:
            await self._sync_chain_historical(
                league, user_id, platform_account,
                credentials_json, adapter, players_map,
            )

    async def _sync_mfl_historical(
        self,
        league: League,
        user_id: UUID,
        platform_account: PlatformAccount,
        credentials_json: dict | None,
        adapter: object,
        players_map: dict[str, dict] | None = None,
    ) -> None:
        """Sync MFL historical seasons using the league history entries.

        MFL reuses the same league_id across years, so we fetch
        the history list and sync each past season directly.
        """
        # Get all historical years from the platform
        year_adapter = get_adapter(
            platform_account.platform_type,
            credentials_json=credentials_json,
            year=league.season,
        )
        all_years = await year_adapter.get_history_years(
            league.platform_league_id,
        )
        # Only sync years before the current season
        years = [y for y in all_years if y < league.season]

        if not years:
            return

        for year in years:
            # Check if already synced
            result = await self.db.execute(
                select(League).where(
                    League.platform_type == platform_account.platform_type,
                    League.platform_league_id == league.platform_league_id,
                    League.season == year,
                )
            )
            if result.scalar_one_or_none() is not None:
                continue

            await asyncio.sleep(0.05)

            year_adapter = get_adapter(
                platform_account.platform_type,
                credentials_json=credentials_json,
                year=year,
            )
            past_league = await year_adapter.get_league(
                league.platform_league_id,
            )

            db_league = await self._upsert_historical_league(
                past_league, league, platform_account,
            )
            await self._sync_historical_league_data(
                db_league, user_id, platform_account,
                credentials_json, year_adapter,
                players_map=players_map,
            )

            logger.info(
                "Synced historical league %s season %d",
                league.platform_league_id, year,
            )

    async def _sync_chain_historical(
        self,
        league: League,
        user_id: UUID,
        platform_account: PlatformAccount,
        credentials_json: dict | None,
        adapter: object,
        players_map: dict[str, dict] | None = None,
    ) -> None:
        """Sync historical seasons by walking previous_league_id chain.

        Used by Sleeper and other platforms where each season has a
        different league ID linked via previous_league_id.
        """
        prev_league_id = league.previous_league_id

        while prev_league_id:
            result = await self.db.execute(
                select(League).where(
                    League.platform_type == platform_account.platform_type,
                    League.platform_league_id == prev_league_id,
                )
            )
            existing_league = result.scalar_one_or_none()
            if existing_league is not None:
                prev_league_id = existing_league.previous_league_id
                continue

            await asyncio.sleep(0.05)
            past_league = await adapter.get_league(prev_league_id)

            db_league = await self._upsert_historical_league(
                past_league, league, platform_account,
            )
            await self._sync_historical_league_data(
                db_league, user_id, platform_account,
                credentials_json, adapter,
                players_map=players_map,
            )

            logger.info(
                "Synced historical league %s season %d",
                past_league.league_id, past_league.season,
            )

            prev_league_id = past_league.previous_league_id

    async def _upsert_historical_league(
        self,
        past_league,
        parent_league: League,
        platform_account: PlatformAccount,
    ) -> League:
        """Upsert a historical league and assign it to the parent's group."""
        settings_json = {**(past_league.settings or {})}
        if past_league.roster_positions is not None:
            settings_json["roster_positions"] = past_league.roster_positions
        # Carry over user_franchise_id from the parent so owner matching works
        parent_settings = parent_league.settings_json or {}
        if "user_franchise_id" in parent_settings:
            settings_json["user_franchise_id"] = parent_settings["user_franchise_id"]

        stmt = (
            pg_insert(League)
            .values(
                platform_type=platform_account.platform_type,
                platform_league_id=past_league.league_id,
                name=past_league.name,
                season=past_league.season,
                roster_size=past_league.roster_size,
                scoring_type=past_league.scoring_type,
                league_type=past_league.league_type,
                settings_json=settings_json,
                previous_league_id=past_league.previous_league_id,
            )
            .on_conflict_do_update(
                index_elements=[
                    "platform_type", "platform_league_id", "season",
                ],
                set_={
                    "name": past_league.name,
                    "roster_size": past_league.roster_size,
                    "scoring_type": past_league.scoring_type,
                    "league_type": past_league.league_type,
                    "settings_json": settings_json,
                    "previous_league_id": past_league.previous_league_id,
                },
            )
            .returning(League)
        )
        result = await self.db.execute(stmt)
        db_league = result.scalar_one()

        if db_league.league_group_id != parent_league.league_group_id:
            db_league.league_group_id = parent_league.league_group_id

        await self.db.flush()
        return db_league

    async def _sync_historical_league_data(
        self,
        db_league: League,
        user_id: UUID,
        platform_account: PlatformAccount,
        credentials_json: dict | None,
        adapter: object,
        players_map: dict[str, dict] | None = None,
    ) -> None:
        """Sync user_leagues and standings for a historical league.

        Rosters are not synced here — they are fetched when the user
        triggers a per-league sync on a specific season.
        """
        await self._sync_user_leagues(
            db_league,
            user_id,
            platform_account.platform_user_id,
            credentials_json=credentials_json,
            adapter=adapter,
        )

        try:
            await self.sync_standings(
                db_league, user_id,
                credentials_json=credentials_json,
                adapter=adapter,
            )
        except Exception:
            logger.exception(
                "Failed to sync standings for historical league %s",
                db_league.platform_league_id,
            )

        await self.db.flush()

    async def sync_all(self, user_id: UUID, platform_account: PlatformAccount, season: int) -> dict:
        """Orchestrate a full sync for a platform account.

        Only syncs league metadata, user_leagues, rosters, and standings.
        Matchups and transactions are fetched lazily when the user views them.
        """
        synced: list[str] = []
        errors: list[str] = []

        # 1. Sync leagues
        try:
            leagues = await self.sync_leagues(user_id, platform_account, season)
            synced.append("leagues")
        except Exception as e:
            errors.append(f"leagues: {e}")
            logger.exception("Failed to sync leagues")
            status = "completed" if synced else "failed"
            return {"status": status, "synced": synced, "errors": errors}

        # 2. Fetch player data once for use across all leagues
        players_map: dict[str, dict] = {}
        credentials_json = platform_account.credentials_json
        adapter = get_adapter(
            platform_account.platform_type, credentials_json=credentials_json
        )
        try:
            players_map = await adapter.get_players_map()
            logger.info("Fetched %d players from platform", len(players_map))
        except Exception:
            logger.warning("Could not fetch players map, will use stubs")

        # 3. For each league, sync user_leagues, rosters, standings
        for league in leagues:
            try:
                await self._sync_user_leagues(
                    league,
                    user_id,
                    platform_account.platform_user_id,
                    credentials_json=credentials_json,
                    adapter=adapter,
                )
            except Exception as e:
                logger.exception("Failed to sync user_leagues for league %s", league.id)
                errors.append(f"user_leagues({league.name}): {e}")

            try:
                await self.sync_rosters(
                    league, user_id, players_map=players_map,
                    credentials_json=credentials_json, adapter=adapter,
                )
                if "rosters" not in synced:
                    synced.append("rosters")
            except Exception as e:
                errors.append(f"rosters({league.name}): {e}")
                logger.exception("Failed to sync rosters for league %s", league.id)

            try:
                await self.sync_standings(
                    league, user_id, credentials_json=credentials_json, adapter=adapter,
                )
                if "standings" not in synced:
                    synced.append("standings")
            except Exception as e:
                errors.append(f"standings({league.name}): {e}")
                logger.exception("Failed to sync standings for league %s", league.id)

        # 4. Sync historical seasons for leagues with previous_league_id
        for league in leagues:
            if league.previous_league_id:
                try:
                    await self.sync_historical_seasons(
                        league, user_id, platform_account,
                        players_map=players_map, adapter=adapter,
                    )
                    if "historical_seasons" not in synced:
                        synced.append("historical_seasons")
                except Exception as e:
                    errors.append(f"historical({league.name}): {e}")
                    logger.exception("Failed to sync historical seasons for league %s", league.id)

        # Sync bye weeks if no data exists for this season
        try:
            existing = await self.db.execute(
                select(TeamByeWeek).where(TeamByeWeek.season == season).limit(1)
            )
            if existing.scalar_one_or_none() is None:
                await sync_bye_weeks(self.db, season)
                synced.append("bye_weeks")
        except Exception as e:
            errors.append(f"bye_weeks: {e}")
            logger.exception("Failed to sync bye weeks for season %d", season)

        await self.db.commit()
        return {
            "status": "completed",
            "synced": synced,
            "errors": errors,
        }
