"""Seeds the database with teams, drivers, race weekends, and historical data."""

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.f1 import Team, Driver, RaceWeekend
from app.ingestion.jolyon_client import JolyonClient
from app.ingestion.data_sync import DataSyncService

logger = logging.getLogger(__name__)

# 2026 F1 Teams with colors
TEAMS_2026 = [
    {"name": "Red Bull Racing", "short_name": "RBR", "color_hex": "#3671C6", "country": "Austrian"},
    {"name": "McLaren", "short_name": "MCL", "color_hex": "#FF8000", "country": "British"},
    {"name": "Ferrari", "short_name": "FER", "color_hex": "#E80020", "country": "Italian"},
    {"name": "Mercedes", "short_name": "MER", "color_hex": "#27F4D2", "country": "German"},
    {"name": "Aston Martin", "short_name": "AMR", "color_hex": "#229971", "country": "British"},
    {"name": "Alpine", "short_name": "ALP", "color_hex": "#0093CC", "country": "French"},
    {"name": "Williams", "short_name": "WIL", "color_hex": "#64C4FF", "country": "British"},
    {"name": "RB", "short_name": "RB", "color_hex": "#6692FF", "country": "Italian"},
    {"name": "Kick Sauber", "short_name": "SAU", "color_hex": "#52E252", "country": "Swiss"},
    {"name": "Haas F1 Team", "short_name": "HAA", "color_hex": "#B6BABD", "country": "American"},
]

# 2026 drivers — update as needed for actual 2026 grid
DRIVERS_2026 = [
    {"code": "VER", "full_name": "Max Verstappen", "number": 1, "team_short": "RBR", "country": "Dutch"},
    {"code": "LAW", "full_name": "Liam Lawson", "number": 30, "team_short": "RBR", "country": "New Zealand"},
    {"code": "NOR", "full_name": "Lando Norris", "number": 4, "team_short": "MCL", "country": "British"},
    {"code": "PIA", "full_name": "Oscar Piastri", "number": 81, "team_short": "MCL", "country": "Australian"},
    {"code": "LEC", "full_name": "Charles Leclerc", "number": 16, "team_short": "FER", "country": "Monegasque"},
    {"code": "HAM", "full_name": "Lewis Hamilton", "number": 44, "team_short": "FER", "country": "British"},
    {"code": "RUS", "full_name": "George Russell", "number": 63, "team_short": "MER", "country": "British"},
    {"code": "ANT", "full_name": "Kimi Antonelli", "number": 12, "team_short": "MER", "country": "Italian"},
    {"code": "ALO", "full_name": "Fernando Alonso", "number": 14, "team_short": "AMR", "country": "Spanish"},
    {"code": "STR", "full_name": "Lance Stroll", "number": 18, "team_short": "AMR", "country": "Canadian"},
    {"code": "GAS", "full_name": "Pierre Gasly", "number": 10, "team_short": "ALP", "country": "French"},
    {"code": "DOO", "full_name": "Jack Doohan", "number": 7, "team_short": "ALP", "country": "Australian"},
    {"code": "ALB", "full_name": "Alexander Albon", "number": 23, "team_short": "WIL", "country": "Thai"},
    {"code": "SAI", "full_name": "Carlos Sainz", "number": 55, "team_short": "WIL", "country": "Spanish"},
    {"code": "TSU", "full_name": "Yuki Tsunoda", "number": 22, "team_short": "RB", "country": "Japanese"},
    {"code": "HAD", "full_name": "Isack Hadjar", "number": 6, "team_short": "RB", "country": "French"},
    {"code": "HUL", "full_name": "Nico Hulkenberg", "number": 27, "team_short": "SAU", "country": "German"},
    {"code": "BOR", "full_name": "Gabriel Bortoleto", "number": 5, "team_short": "SAU", "country": "Brazilian"},
    {"code": "BEA", "full_name": "Oliver Bearman", "number": 87, "team_short": "HAA", "country": "British"},
    {"code": "OCO", "full_name": "Esteban Ocon", "number": 31, "team_short": "HAA", "country": "French"},
]


async def seed_teams_and_drivers(db: Session) -> dict[str, int]:
    """
    Seed teams and drivers into the database. Skips if already present.
    Returns dict mapping team short_name to team DB id.
    """
    team_id_map: dict[str, int] = {}

    for team_data in TEAMS_2026:
        existing = db.query(Team).filter(Team.short_name == team_data["short_name"]).first()
        if existing:
            team_id_map[team_data["short_name"]] = existing.id
            continue
        team = Team(**team_data)
        db.add(team)
        db.flush()
        team_id_map[team_data["short_name"]] = team.id
        logger.info("Added team: %s", team_data["name"])

    for driver_data in DRIVERS_2026:
        existing = db.query(Driver).filter(Driver.code == driver_data["code"]).first()
        if existing:
            continue
        team_id = team_id_map.get(driver_data["team_short"])
        if not team_id:
            logger.warning("Team not found for driver %s", driver_data["code"])
            continue
        driver = Driver(
            code=driver_data["code"],
            full_name=driver_data["full_name"],
            number=driver_data["number"],
            team_id=team_id,
            country=driver_data["country"],
        )
        db.add(driver)
        logger.info("Added driver: %s (%s)", driver_data["full_name"], driver_data["code"])

    db.commit()
    return team_id_map


async def seed_race_weekends_from_jolyon(db: Session, season: int) -> list[int]:
    """
    Fetch the schedule from Jolyon API and create RaceWeekend rows.
    Returns list of created RaceWeekend IDs.
    """
    client = JolyonClient()
    schedule = await client.get_schedule(season)
    created_ids = []

    for entry in schedule:
        existing = db.query(RaceWeekend).filter(
            RaceWeekend.season == season,
            RaceWeekend.round == entry.round_number,
        ).first()
        if existing:
            created_ids.append(existing.id)
            continue

        is_sprint = entry.sprint_date is not None

        race_weekend = RaceWeekend(
            season=season,
            round=entry.round_number,
            name=entry.race_name,
            circuit_id=entry.circuit_id,
            country=entry.country,
            is_sprint_weekend=is_sprint,
            fp1_time=_parse_date(entry.fp1_date),
            fp2_time=_parse_date(entry.fp2_date),
            fp3_time=_parse_date(entry.fp3_date),
            quali_time=_parse_date(entry.qualifying_date),
            race_time=_parse_date(entry.race_date),
            prediction_deadline=_parse_date(entry.qualifying_date),
            status="completed" if season < 2026 else "upcoming",
        )
        db.add(race_weekend)
        db.flush()
        created_ids.append(race_weekend.id)
        logger.info("Added race weekend: %s R%s %s", season, entry.round_number, entry.race_name)

    db.commit()
    return created_ids


async def backfill_historical_data(db: Session, season: int, rounds: list[int] | None = None) -> None:
    """
    Back-fill session data and race results for completed races.
    Used to populate 2025 training data.

    Args:
        db: Database session.
        season: Season year.
        rounds: Specific rounds to fill, or None for all.
    """
    sync_service = DataSyncService(db)

    races = db.query(RaceWeekend).filter(RaceWeekend.season == season)
    if rounds:
        races = races.filter(RaceWeekend.round.in_(rounds))
    races = races.order_by(RaceWeekend.round).all()

    for race in races:
        logger.info("Back-filling data for %s R%s: %s", season, race.round, race.name)

        # Sync each session type
        for session_type in ["fp1", "fp2", "fp3", "quali", "race"]:
            if session_type == "fp3" and race.is_sprint_weekend:
                continue  # Sprint weekends don't have FP3
            try:
                await sync_service.sync_session(race.id, session_type)
            except Exception as e:
                logger.warning("Failed to sync %s for race %s: %s", session_type, race.id, e)

        # Sync race results (ActualResult rows)
        try:
            await sync_service.sync_race_results(race.id)
        except Exception as e:
            logger.warning("Failed to sync results for race %s: %s", race.id, e)


async def run_full_seed(db: Session) -> None:
    """
    Run the complete seeding process:
    1. Seed teams and drivers
    2. Seed 2025 race weekends from Jolyon
    3. Seed 2026 race weekends from Jolyon
    4. Back-fill 2025 session data for ML training
    """
    logger.info("Starting full database seed...")

    # Step 1: Teams and drivers
    await seed_teams_and_drivers(db)

    # Step 2: 2025 season schedule
    race_ids_2025 = await seed_race_weekends_from_jolyon(db, 2025)
    logger.info("Seeded %d race weekends for 2025", len(race_ids_2025))

    # Step 3: 2026 season schedule
    race_ids_2026 = await seed_race_weekends_from_jolyon(db, 2026)
    logger.info("Seeded %d race weekends for 2026", len(race_ids_2026))

    # Step 4: Mark 2026 Australia (R1) and China (R2) as completed if past
    for race in db.query(RaceWeekend).filter(
        RaceWeekend.season == 2026,
        RaceWeekend.round.in_([1, 2]),
    ).all():
        if race.race_time and race.race_time < datetime.utcnow():
            race.status = "completed"
    db.commit()

    # Step 5: Back-fill 2025 historical data
    logger.info("Back-filling 2025 session data (this may take a while)...")
    await backfill_historical_data(db, 2025)

    # Step 6: Back-fill 2026 completed races
    completed_2026 = db.query(RaceWeekend).filter(
        RaceWeekend.season == 2026,
        RaceWeekend.status == "completed",
    ).all()
    if completed_2026:
        rounds = [r.round for r in completed_2026]
        logger.info("Back-filling 2026 completed races: rounds %s", rounds)
        await backfill_historical_data(db, 2026, rounds=rounds)

    logger.info("Full seed complete.")


def _parse_date(date_str: str | None) -> datetime | None:
    """Parse ISO date string to datetime, returning None on failure."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, AttributeError):
            return None
