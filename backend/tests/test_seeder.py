import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from app.services.seeder import (
    seed_teams_and_drivers,
    seed_race_weekends_from_jolyon,
    _parse_date,
    TEAMS_2026,
    DRIVERS_2026,
)


def test_parse_date_iso():
    result = _parse_date("2025-03-15T14:00:00Z")
    assert result is not None
    assert result.year == 2025
    assert result.month == 3


def test_parse_date_simple():
    result = _parse_date("2025-03-15")
    assert result is not None
    assert result.day == 15


def test_parse_date_none():
    assert _parse_date(None) is None
    assert _parse_date("") is None


def test_teams_data_completeness():
    assert len(TEAMS_2026) == 10
    for team in TEAMS_2026:
        assert "name" in team
        assert "short_name" in team
        assert "color_hex" in team
        assert team["color_hex"].startswith("#")


def test_drivers_data_completeness():
    assert len(DRIVERS_2026) == 20
    codes = [d["code"] for d in DRIVERS_2026]
    assert len(set(codes)) == 20  # all unique
    team_shorts = set(d["team_short"] for d in DRIVERS_2026)
    team_defined = set(t["short_name"] for t in TEAMS_2026)
    assert team_shorts.issubset(team_defined)  # all driver teams exist


@pytest.mark.asyncio
async def test_seed_teams_and_drivers(db):
    """Integration test: seed teams and drivers into a test database."""
    team_map = await seed_teams_and_drivers(db)
    assert len(team_map) == 10

    from app.models.f1 import Team, Driver
    teams = db.query(Team).all()
    drivers = db.query(Driver).all()
    assert len(teams) == 10
    assert len(drivers) == 20

    # Idempotent: running again should not duplicate
    team_map2 = await seed_teams_and_drivers(db)
    assert len(team_map2) == 10
    assert db.query(Team).count() == 10
