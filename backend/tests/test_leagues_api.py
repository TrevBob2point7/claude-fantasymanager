"""Integration tests for the leagues API endpoints."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from app.models import (
    League,
    PlatformAccount,
    PlatformType,
    Player,
    PlayerStatus,
    Position,
    Roster,
    ScoringType,
    UserLeague,
)
from app.platforms.schemas import PlatformLeague
from httpx import AsyncClient


class TestDiscoverLeagues:
    """POST /api/leagues/discover"""

    async def test_discover_success(
        self, authenticated_client: AsyncClient, db_session
    ):
        user = authenticated_client.test_user  # type: ignore[attr-defined]
        account = PlatformAccount(
            user_id=user.id,
            platform_type=PlatformType.sleeper,
            platform_username="testuser",
            platform_user_id="123456789",
        )
        db_session.add(account)
        await db_session.commit()
        await db_session.refresh(account)

        mock_adapter = AsyncMock()
        mock_adapter.get_leagues.return_value = [
            PlatformLeague(
                league_id="lg1",
                name="Dynasty League",
                season=2025,
                roster_size=15,
                scoring_type="ppr",
            )
        ]

        with patch(
            "app.api.leagues.get_adapter", return_value=mock_adapter
        ):
            response = await authenticated_client.post(
                "/api/leagues/discover",
                json={
                    "platform_account_id": str(account.id),
                    "season": 2025,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Dynasty League"
        assert data[0]["platform_league_id"] == "lg1"
        assert data[0]["already_linked"] is False

    async def test_discover_account_not_found(
        self, authenticated_client: AsyncClient
    ):
        response = await authenticated_client.post(
            "/api/leagues/discover",
            json={
                "platform_account_id": str(uuid.uuid4()),
                "season": 2025,
            },
        )
        assert response.status_code == 404

    async def test_discover_unauthenticated(self, client: AsyncClient):
        response = await client.post(
            "/api/leagues/discover",
            json={
                "platform_account_id": str(uuid.uuid4()),
                "season": 2025,
            },
        )
        assert response.status_code == 401


class TestListLeagues:
    """GET /api/leagues"""

    async def test_list_leagues_success(
        self, authenticated_client: AsyncClient, db_session
    ):
        user = authenticated_client.test_user  # type: ignore[attr-defined]

        league = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg1",
            name="My League",
            season=datetime.now().year,
            scoring_type=ScoringType.ppr,
        )
        db_session.add(league)
        await db_session.flush()
        await db_session.refresh(league)

        ul = UserLeague(
            user_id=user.id,
            league_id=league.id,
            team_name="My Team",
            platform_team_id="1",
        )
        db_session.add(ul)
        await db_session.commit()

        response = await authenticated_client.get("/api/leagues")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "My League"
        assert data[0]["team_name"] == "My Team"

    async def test_list_leagues_filter_by_season(
        self, authenticated_client: AsyncClient, db_session
    ):
        user = authenticated_client.test_user  # type: ignore[attr-defined]

        for season in [2024, 2025]:
            league = League(
                platform_type=PlatformType.sleeper,
                platform_league_id=f"lg_{season}",
                name=f"League {season}",
                season=season,
            )
            db_session.add(league)
            await db_session.flush()
            await db_session.refresh(league)
            ul = UserLeague(
                user_id=user.id, league_id=league.id,
                platform_team_id=f"1_{season}",
            )
            db_session.add(ul)

        await db_session.commit()

        response = await authenticated_client.get("/api/leagues?season=2025")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["season"] == 2025

    async def test_list_leagues_empty(self, authenticated_client: AsyncClient):
        response = await authenticated_client.get("/api/leagues")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_leagues_unauthenticated(self, client: AsyncClient):
        response = await client.get("/api/leagues")
        assert response.status_code == 401


class TestGetLeagueDetail:
    """GET /api/leagues/{league_id}"""

    async def test_get_league_detail_success(
        self, authenticated_client: AsyncClient, db_session
    ):
        user = authenticated_client.test_user  # type: ignore[attr-defined]

        league = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg1",
            name="Detail League",
            season=2025,
            scoring_type=ScoringType.ppr,
        )
        db_session.add(league)
        await db_session.flush()
        await db_session.refresh(league)

        ul = UserLeague(
            user_id=user.id,
            league_id=league.id,
            team_name="My Team",
            platform_team_id="1",
        )
        db_session.add(ul)
        await db_session.commit()

        response = await authenticated_client.get(f"/api/leagues/{league.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Detail League"
        assert data["team_name"] == "My Team"
        assert "standings" in data
        assert "roster" in data
        assert "recent_matchups" in data
        assert "recent_transactions" in data

    async def test_get_league_detail_not_found(
        self, authenticated_client: AsyncClient
    ):
        response = await authenticated_client.get(
            f"/api/leagues/{uuid.uuid4()}"
        )
        assert response.status_code == 404

    async def test_get_league_detail_unauthenticated(self, client: AsyncClient):
        response = await client.get(f"/api/leagues/{uuid.uuid4()}")
        assert response.status_code == 401

    async def test_league_detail_includes_roster_status(
        self, authenticated_client: AsyncClient, db_session
    ):
        """Roster entries include status field (from player model)."""
        user = authenticated_client.test_user  # type: ignore[attr-defined]

        league = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_status",
            name="Status League",
            season=2025,
            scoring_type=ScoringType.ppr,
        )
        db_session.add(league)
        await db_session.flush()
        await db_session.refresh(league)

        ul = UserLeague(
            user_id=user.id,
            league_id=league.id,
            team_name="My Team",
            platform_team_id="1",
        )
        db_session.add(ul)
        await db_session.flush()
        await db_session.refresh(ul)

        player = Player(
            full_name="Patrick Mahomes",
            position=Position.QB,
            team="KC",
            sleeper_id="pm_status_test",
            status=PlayerStatus.questionable,
        )
        db_session.add(player)
        await db_session.flush()
        await db_session.refresh(player)

        roster = Roster(
            user_league_id=ul.id,
            player_id=player.id,
            slot="QB",
        )
        db_session.add(roster)
        await db_session.commit()

        response = await authenticated_client.get(f"/api/leagues/{league.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["roster"]) >= 1
        roster_entry = data["roster"][0]
        assert "status" in roster_entry
        assert roster_entry["status"] == "questionable"

    async def test_league_detail_includes_bye_week(
        self, authenticated_client: AsyncClient, db_session
    ):
        """Roster entries include bye_week field (joined from team_bye_weeks)."""
        user = authenticated_client.test_user  # type: ignore[attr-defined]

        league = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_bye",
            name="Bye Week League",
            season=2025,
            scoring_type=ScoringType.ppr,
        )
        db_session.add(league)
        await db_session.flush()
        await db_session.refresh(league)

        ul = UserLeague(
            user_id=user.id,
            league_id=league.id,
            team_name="My Team",
            platform_team_id="1",
        )
        db_session.add(ul)
        await db_session.flush()
        await db_session.refresh(ul)

        player = Player(
            full_name="Travis Kelce",
            position=Position.TE,
            team="KC",
            sleeper_id="tk_bye_test",
        )
        db_session.add(player)
        await db_session.flush()
        await db_session.refresh(player)

        roster = Roster(
            user_league_id=ul.id,
            player_id=player.id,
            slot="TE",
        )
        db_session.add(roster)

        # Insert bye week data for KC
        from app.models.team_bye_week import TeamByeWeek

        bye = TeamByeWeek(season=2025, team="KC", bye_week=6)
        db_session.add(bye)
        await db_session.commit()

        response = await authenticated_client.get(f"/api/leagues/{league.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["roster"]) >= 1
        roster_entry = data["roster"][0]
        assert "bye_week" in roster_entry
        assert roster_entry["bye_week"] == 6

    async def test_league_detail_includes_current_week(
        self, authenticated_client: AsyncClient, db_session
    ):
        """Response includes current_week field."""
        user = authenticated_client.test_user  # type: ignore[attr-defined]

        league = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_week",
            name="Current Week League",
            season=2025,
            scoring_type=ScoringType.ppr,
            settings_json={"leg": 8},
        )
        db_session.add(league)
        await db_session.flush()
        await db_session.refresh(league)

        ul = UserLeague(
            user_id=user.id,
            league_id=league.id,
            team_name="My Team",
            platform_team_id="1",
        )
        db_session.add(ul)
        await db_session.commit()

        response = await authenticated_client.get(f"/api/leagues/{league.id}")
        assert response.status_code == 200
        data = response.json()
        assert "current_week" in data
        assert data["current_week"] == 8

    async def test_league_detail_roster_has_slot_labels(
        self, authenticated_client: AsyncClient, db_session
    ):
        """Roster entries have slot values like 'QB', 'FLEX' (not 'STARTER')."""
        user = authenticated_client.test_user  # type: ignore[attr-defined]

        league = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_slots",
            name="Slot Labels League",
            season=2025,
            scoring_type=ScoringType.ppr,
            settings_json={
                "roster_positions": ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "BN", "BN"]
            },
        )
        db_session.add(league)
        await db_session.flush()
        await db_session.refresh(league)

        ul = UserLeague(
            user_id=user.id,
            league_id=league.id,
            team_name="My Team",
            platform_team_id="1",
        )
        db_session.add(ul)
        await db_session.flush()
        await db_session.refresh(ul)

        # Create a player with a QB slot
        player = Player(
            full_name="Josh Allen",
            position=Position.QB,
            team="BUF",
            sleeper_id="ja_slot_test",
        )
        db_session.add(player)
        await db_session.flush()
        await db_session.refresh(player)

        roster = Roster(
            user_league_id=ul.id,
            player_id=player.id,
            slot="QB",
        )
        db_session.add(roster)
        await db_session.commit()

        response = await authenticated_client.get(f"/api/leagues/{league.id}")
        assert response.status_code == 200
        data = response.json()
        slots = [r["slot"] for r in data["roster"] if r["slot"] is not None]
        # No slot should be "STARTER" — they should be actual position labels
        assert "STARTER" not in slots
        assert "QB" in slots


@pytest.mark.asyncio(loop_scope="session")
class TestGetLeagueSeasons:
    """GET /api/leagues/{league_id}/seasons"""

    async def test_get_league_seasons_returns_group(
        self, authenticated_client: AsyncClient, db_session
    ):
        """Returns all seasons in the same league_group_id, sorted desc."""
        user = authenticated_client.test_user  # type: ignore[attr-defined]
        shared_group = uuid.uuid4()

        league_2023 = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_chain_2023",
            name="Chain League 2023",
            season=2023,
            league_group_id=shared_group,
        )
        db_session.add(league_2023)
        await db_session.flush()
        await db_session.refresh(league_2023)

        league_2024 = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_chain_2024",
            name="Chain League 2024",
            season=2024,
            league_group_id=shared_group,
        )
        db_session.add(league_2024)
        await db_session.flush()
        await db_session.refresh(league_2024)

        league_2025 = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_chain_2025",
            name="Chain League 2025",
            season=2025,
            league_group_id=shared_group,
        )
        db_session.add(league_2025)
        await db_session.flush()
        await db_session.refresh(league_2025)

        # Link user to all leagues
        for i, lg in enumerate([league_2023, league_2024, league_2025], start=1):
            ul = UserLeague(
                user_id=user.id, league_id=lg.id,
                platform_team_id=str(i),
            )
            db_session.add(ul)
        await db_session.commit()

        response = await authenticated_client.get(
            f"/api/leagues/{league_2025.id}/seasons"
        )
        assert response.status_code == 200
        data = response.json()

        # Should return all 3 seasons sorted desc
        seasons = data["seasons"]
        assert len(seasons) == 3
        assert seasons[0]["season"] == 2025
        assert seasons[1]["season"] == 2024
        assert seasons[2]["season"] == 2023

        # Each entry should have league_id, season, and platform_type
        for entry in seasons:
            assert "league_id" in entry
            assert "season" in entry
            assert "platform_type" in entry

    async def test_get_league_seasons_single_season(
        self, authenticated_client: AsyncClient, db_session
    ):
        """League with no league_group_id returns single-entry list."""
        user = authenticated_client.test_user  # type: ignore[attr-defined]

        league = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_single",
            name="Single Season League",
            season=2025,
        )
        db_session.add(league)
        await db_session.flush()
        await db_session.refresh(league)

        ul = UserLeague(
            user_id=user.id, league_id=league.id,
            platform_team_id="1",
        )
        db_session.add(ul)
        await db_session.commit()

        response = await authenticated_client.get(
            f"/api/leagues/{league.id}/seasons"
        )
        assert response.status_code == 200
        data = response.json()

        seasons = data["seasons"]
        assert len(seasons) == 1
        assert seasons[0]["season"] == 2025
        assert seasons[0]["league_id"] == str(league.id)


@pytest.mark.asyncio(loop_scope="session")
class TestGetLeagueSeasonsAccessControl:
    """GET /api/leagues/{league_id}/seasons — access control with league_group_id."""

    async def test_group_returns_all_seasons_regardless_of_user_league(
        self, authenticated_client: AsyncClient, db_session
    ):
        """All seasons in a group are returned even if user only has user_league for one."""
        user = authenticated_client.test_user  # type: ignore[attr-defined]
        shared_group = uuid.uuid4()

        league_2023 = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_acl_2023",
            name="ACL League 2023",
            season=2023,
            league_group_id=shared_group,
        )
        db_session.add(league_2023)
        await db_session.flush()
        await db_session.refresh(league_2023)

        league_2024 = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_acl_2024",
            name="ACL League 2024",
            season=2024,
            league_group_id=shared_group,
        )
        db_session.add(league_2024)
        await db_session.flush()
        await db_session.refresh(league_2024)

        league_2025 = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_acl_2025",
            name="ACL League 2025",
            season=2025,
            league_group_id=shared_group,
        )
        db_session.add(league_2025)
        await db_session.flush()
        await db_session.refresh(league_2025)

        # Only link user to the middle season (2024)
        ul = UserLeague(
            user_id=user.id, league_id=league_2024.id,
            platform_team_id="acl_1",
        )
        db_session.add(ul)
        await db_session.commit()

        response = await authenticated_client.get(
            f"/api/leagues/{league_2024.id}/seasons"
        )
        assert response.status_code == 200
        seasons = response.json()["seasons"]

        # With league_group_id, ALL seasons in the group are returned
        assert len(seasons) == 3
        season_years = [s["season"] for s in seasons]
        assert 2023 in season_years
        assert 2024 in season_years
        assert 2025 in season_years

    async def test_no_group_id_returns_single_season(
        self, authenticated_client: AsyncClient, db_session
    ):
        """League without league_group_id returns only itself."""
        user = authenticated_client.test_user  # type: ignore[attr-defined]

        league_a = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_partial_2023",
            name="Partial 2023",
            season=2023,
        )
        db_session.add(league_a)
        await db_session.flush()
        await db_session.refresh(league_a)

        ul = UserLeague(
            user_id=user.id, league_id=league_a.id,
            platform_team_id="partial_1",
        )
        db_session.add(ul)
        await db_session.commit()

        response = await authenticated_client.get(
            f"/api/leagues/{league_a.id}/seasons"
        )
        assert response.status_code == 200
        seasons = response.json()["seasons"]

        # No league_group_id means just this one season
        assert len(seasons) == 1
        assert seasons[0]["season"] == 2023


@pytest.mark.asyncio(loop_scope="session")
class TestListLeaguesLatest:
    """GET /api/leagues?latest=true — DISTINCT ON league_group_id filtering."""

    async def test_latest_returns_newest_in_group(
        self, authenticated_client: AsyncClient, db_session
    ):
        """Only the newest season in each league group is returned."""
        user = authenticated_client.test_user  # type: ignore[attr-defined]
        shared_group = uuid.uuid4()

        league_old = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_latest_2024",
            name="Latest Chain 2024",
            season=2024,
            league_group_id=shared_group,
        )
        db_session.add(league_old)
        await db_session.flush()
        await db_session.refresh(league_old)

        league_new = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_latest_2025",
            name="Latest Chain 2025",
            season=2025,
            league_group_id=shared_group,
        )
        db_session.add(league_new)
        await db_session.flush()
        await db_session.refresh(league_new)

        for i, lg in enumerate([league_old, league_new], start=1):
            ul = UserLeague(
                user_id=user.id, league_id=lg.id,
                platform_team_id=f"latest_{i}",
            )
            db_session.add(ul)
        await db_session.commit()

        response = await authenticated_client.get("/api/leagues?latest=true")
        assert response.status_code == 200
        data = response.json()

        # Only 2025 should appear (newest in group)
        returned_ids = [d["platform_league_id"] for d in data]
        assert "lg_latest_2025" in returned_ids
        assert "lg_latest_2024" not in returned_ids

    async def test_latest_cross_platform_separate_groups(
        self, authenticated_client: AsyncClient, db_session
    ):
        """Different platform groups are returned independently."""
        user = authenticated_client.test_user  # type: ignore[attr-defined]
        sleeper_group = uuid.uuid4()
        mfl_group = uuid.uuid4()

        sleeper_old = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="shared_id",
            name="Sleeper 2024",
            season=2024,
            league_group_id=sleeper_group,
        )
        db_session.add(sleeper_old)
        await db_session.flush()
        await db_session.refresh(sleeper_old)

        sleeper_new = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="shared_id_s",
            name="Sleeper 2025",
            season=2025,
            league_group_id=sleeper_group,
        )
        db_session.add(sleeper_new)
        await db_session.flush()
        await db_session.refresh(sleeper_new)

        mfl_league = League(
            platform_type=PlatformType.mfl,
            platform_league_id="shared_id",
            name="MFL League",
            season=2025,
            league_group_id=mfl_group,
        )
        db_session.add(mfl_league)
        await db_session.flush()
        await db_session.refresh(mfl_league)

        for i, lg in enumerate([sleeper_old, sleeper_new, mfl_league], start=1):
            ul = UserLeague(
                user_id=user.id, league_id=lg.id,
                platform_team_id=f"xplat_{i}",
            )
            db_session.add(ul)
        await db_session.commit()

        response = await authenticated_client.get("/api/leagues?latest=true")
        assert response.status_code == 200
        data = response.json()

        returned = {(d["platform_type"], d["platform_league_id"]) for d in data}
        assert ("sleeper", "shared_id_s") in returned  # sleeper newest
        assert ("mfl", "shared_id") in returned  # mfl standalone
        assert ("sleeper", "shared_id") not in returned  # sleeper old filtered out


@pytest.mark.asyncio(loop_scope="session")
class TestLinkLeagues:
    """POST /api/leagues/{league_id}/link"""

    async def test_link_leagues_merges_groups(
        self, authenticated_client: AsyncClient, db_session
    ):
        """Linking two leagues merges their league groups."""
        user = authenticated_client.test_user  # type: ignore[attr-defined]
        group_a = uuid.uuid4()
        group_b = uuid.uuid4()

        league_a1 = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_link_a1",
            name="Group A 2024",
            season=2024,
            league_group_id=group_a,
        )
        league_a2 = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_link_a2",
            name="Group A 2025",
            season=2025,
            league_group_id=group_a,
        )
        league_b1 = League(
            platform_type=PlatformType.mfl,
            platform_league_id="lg_link_b1",
            name="Group B 2023",
            season=2023,
            league_group_id=group_b,
        )

        for lg in [league_a1, league_a2, league_b1]:
            db_session.add(lg)
            await db_session.flush()
            await db_session.refresh(lg)

        for i, lg in enumerate([league_a1, league_a2, league_b1], start=1):
            ul = UserLeague(
                user_id=user.id, league_id=lg.id,
                platform_team_id=f"link_{i}",
            )
            db_session.add(ul)
        await db_session.commit()

        response = await authenticated_client.post(
            f"/api/leagues/{league_a1.id}/link",
            json={"target_league_id": str(league_b1.id)},
        )
        assert response.status_code == 200
        data = response.json()

        # Should return all 3 seasons merged into one group
        seasons = data["seasons"]
        assert len(seasons) == 3
        season_years = sorted([s["season"] for s in seasons], reverse=True)
        assert season_years == [2025, 2024, 2023]

    async def test_link_leagues_source_no_group(
        self, authenticated_client: AsyncClient, db_session
    ):
        """Source league without league_group_id gets one assigned."""
        user = authenticated_client.test_user  # type: ignore[attr-defined]

        league_src = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_link_nogrp_src",
            name="No Group Source",
            season=2024,
        )
        league_tgt = League(
            platform_type=PlatformType.mfl,
            platform_league_id="lg_link_nogrp_tgt",
            name="No Group Target",
            season=2025,
        )

        for lg in [league_src, league_tgt]:
            db_session.add(lg)
            await db_session.flush()
            await db_session.refresh(lg)

        for i, lg in enumerate([league_src, league_tgt], start=1):
            ul = UserLeague(
                user_id=user.id, league_id=lg.id,
                platform_team_id=f"link_nogrp_{i}",
            )
            db_session.add(ul)
        await db_session.commit()

        response = await authenticated_client.post(
            f"/api/leagues/{league_src.id}/link",
            json={"target_league_id": str(league_tgt.id)},
        )
        assert response.status_code == 200
        seasons = response.json()["seasons"]
        assert len(seasons) == 2

    async def test_link_leagues_not_found(
        self, authenticated_client: AsyncClient, db_session
    ):
        """Linking to a non-existent league returns 404."""
        user = authenticated_client.test_user  # type: ignore[attr-defined]

        league = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_link_404",
            name="Link 404",
            season=2025,
        )
        db_session.add(league)
        await db_session.flush()
        await db_session.refresh(league)

        ul = UserLeague(
            user_id=user.id, league_id=league.id,
            platform_team_id="link_404",
        )
        db_session.add(ul)
        await db_session.commit()

        response = await authenticated_client.post(
            f"/api/leagues/{league.id}/link",
            json={"target_league_id": str(uuid.uuid4())},
        )
        assert response.status_code == 404

    async def test_link_leagues_unauthenticated(self, client: AsyncClient):
        """Unauthenticated request returns 401."""
        response = await client.post(
            f"/api/leagues/{uuid.uuid4()}/link",
            json={"target_league_id": str(uuid.uuid4())},
        )
        assert response.status_code == 401


@pytest.mark.asyncio(loop_scope="session")
class TestUnlinkLeagues:
    """POST /api/leagues/{league_id}/unlink"""

    async def test_unlink_splits_by_platform(
        self, authenticated_client: AsyncClient, db_session
    ):
        """Unlinking by platform_type splits leagues into separate groups."""
        user = authenticated_client.test_user  # type: ignore[attr-defined]
        shared_group = uuid.uuid4()

        sleeper_league = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_unlink_sleeper",
            name="Unlink Sleeper 2025",
            season=2025,
            league_group_id=shared_group,
        )
        mfl_league = League(
            platform_type=PlatformType.mfl,
            platform_league_id="lg_unlink_mfl",
            name="Unlink MFL 2024",
            season=2024,
            league_group_id=shared_group,
        )

        for lg in [sleeper_league, mfl_league]:
            db_session.add(lg)
            await db_session.flush()
            await db_session.refresh(lg)

        for i, lg in enumerate([sleeper_league, mfl_league], start=1):
            ul = UserLeague(
                user_id=user.id, league_id=lg.id,
                platform_team_id=f"unlink_{i}",
            )
            db_session.add(ul)
        await db_session.commit()

        # Unlink MFL from the group
        response = await authenticated_client.post(
            f"/api/leagues/{sleeper_league.id}/unlink",
            json={"platform_type": "mfl"},
        )
        assert response.status_code == 200

        # The response should show the sleeper league's group (just sleeper now)
        # Since we requested from the sleeper league's perspective, and MFL was split off

        # Verify the groups are now separate
        await db_session.refresh(sleeper_league)
        await db_session.refresh(mfl_league)
        assert sleeper_league.league_group_id != mfl_league.league_group_id

    async def test_unlink_unauthenticated(self, client: AsyncClient):
        """Unauthenticated request returns 401."""
        response = await client.post(
            f"/api/leagues/{uuid.uuid4()}/unlink",
            json={"platform_type": "mfl"},
        )
        assert response.status_code == 401


@pytest.mark.asyncio(loop_scope="session")
class TestListLeaguesCurrentSeason:
    """GET /api/leagues — current season filtering."""

    async def test_list_leagues_filters_current_season(
        self, authenticated_client: AsyncClient, db_session
    ):
        """GET /api/leagues only returns leagues matching current year (no season param)."""
        user = authenticated_client.test_user  # type: ignore[attr-defined]

        current_year = datetime.now().year

        # Create a past-season league and a current-season league
        old_league = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_old_filter",
            name="Old League",
            season=current_year - 1,
        )
        db_session.add(old_league)
        await db_session.flush()
        await db_session.refresh(old_league)

        current_league = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_current_filter",
            name="Current League",
            season=current_year,
        )
        db_session.add(current_league)
        await db_session.flush()
        await db_session.refresh(current_league)

        for i, lg in enumerate([old_league, current_league], start=1):
            ul = UserLeague(
                user_id=user.id, league_id=lg.id,
                platform_team_id=str(i),
            )
            db_session.add(ul)
        await db_session.commit()

        # Request without season param — should only return current year
        response = await authenticated_client.get("/api/leagues")
        assert response.status_code == 200
        data = response.json()

        # Should only include the current-season league
        seasons_returned = [d["season"] for d in data]
        assert current_year in seasons_returned
        assert (current_year - 1) not in seasons_returned
