import uuid
from datetime import UTC, datetime

import factory
from app.auth import hash_password
from app.models.enums import PlatformType, ScoringType
from app.models.league import League
from app.models.platform_account import PlatformAccount
from app.models.user import User


class UserFactory(factory.Factory):
    class Meta:
        model = User

    id = factory.LazyFunction(uuid.uuid4)
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    hashed_password = factory.LazyFunction(lambda: hash_password("password123"))
    display_name = factory.Faker("name")
    created_at = factory.LazyFunction(lambda: datetime.now(UTC))
    updated_at = factory.LazyFunction(lambda: datetime.now(UTC))


class PlatformAccountFactory(factory.Factory):
    class Meta:
        model = PlatformAccount

    id = factory.LazyFunction(uuid.uuid4)
    user_id = factory.LazyFunction(uuid.uuid4)
    platform_type = PlatformType.sleeper
    platform_username = factory.Faker("user_name")
    platform_user_id = factory.LazyFunction(lambda: str(uuid.uuid4().int)[:18])
    created_at = factory.LazyFunction(lambda: datetime.now(UTC))
    updated_at = factory.LazyFunction(lambda: datetime.now(UTC))


class LeagueFactory(factory.Factory):
    class Meta:
        model = League

    id = factory.LazyFunction(uuid.uuid4)
    platform_type = PlatformType.sleeper
    platform_league_id = factory.LazyFunction(lambda: str(uuid.uuid4().int)[:18])
    name = factory.Sequence(lambda n: f"Test League {n}")
    season = 2025
    roster_size = 15
    scoring_type = ScoringType.ppr
    created_at = factory.LazyFunction(lambda: datetime.now(UTC))
    updated_at = factory.LazyFunction(lambda: datetime.now(UTC))
