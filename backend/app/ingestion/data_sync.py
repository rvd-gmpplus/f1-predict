"""Orchestrates data fetching from all sources and persists to the database."""

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.f1 import Driver, RaceWeekend, Team
from app.models.training_data import SessionData, DriverSessionStats
from app.models.prediction import ActualResult
from app.ingestion.jolyon_client import JolyonClient
from app.ingestion.fastf1_client import FastF1Client, FastF1Error
from app.ingestion.weather_client import WeatherClient, WeatherAPIError

logger = logging.getLogger(__name__)


class DataSyncService:
    """Fetches session data from external APIs and writes to the database."""

    def __init__(self, db: Session):
        self.db = db
        self.jolyon = JolyonClient()
        self.fastf1 = FastF1Client()
        self.weather = WeatherClient()

    async def sync_session(self, race_weekend_id: int, session_type: str) -> bool:
        """
        Fetch and store all data for a specific session.

        Args:
            race_weekend_id: The RaceWeekend database ID.
            session_type: One of fp1, fp2, fp3, quali, race, sprint.

        Returns:
            True if data was successfully synced, False otherwise.
        """
        race = self.db.get(RaceWeekend, race_weekend_id)
        if not race:
            logger.error("RaceWeekend %s not found", race_weekend_id)
            return False

        # Check if already synced
        existing = self.db.query(SessionData).filter(
            SessionData.race_weekend_id == race_weekend_id,
            SessionData.session_type == session_type,
        ).first()
        if existing:
            logger.info("Session data already exists for race %s session %s", race_weekend_id, session_type)
            return True

        # Fetch FastF1 data
        try:
            driver_stats, weather = self.fastf1.get_session_data(race.season, race.round, session_type)
        except FastF1Error as e:
            logger.error("FastF1 fetch failed for race %s %s: %s", race_weekend_id, session_type, e)
            return False

        # Build driver code → DB ID mapping
        driver_map = self._get_driver_code_map()

        # Store session data
        session_data = SessionData(
            race_weekend_id=race_weekend_id,
            session_type=session_type,
            weather_data={
                "air_temp": weather.air_temp,
                "track_temp": weather.track_temp,
                "humidity": weather.humidity,
                "wind_speed": weather.wind_speed,
                "rainfall": weather.rainfall,
            },
            track_temp=weather.track_temp,
            air_temp=weather.air_temp,
            rainfall=weather.rainfall,
        )
        self.db.add(session_data)
        self.db.flush()  # get the ID

        # Store per-driver stats
        for stats in driver_stats:
            driver_id = driver_map.get(stats.driver_code)
            if not driver_id:
                logger.warning("Unknown driver code: %s", stats.driver_code)
                continue

            driver_session = DriverSessionStats(
                session_data_id=session_data.id,
                driver_id=driver_id,
                best_lap_time=stats.best_lap_time,
                avg_lap_time=stats.avg_lap_time,
                best_sector1=stats.best_sector1,
                best_sector2=stats.best_sector2,
                best_sector3=stats.best_sector3,
                long_run_pace=stats.long_run_pace,
                long_run_degradation=stats.long_run_degradation,
                stint_data=stats.stint_data,
                top_speed=stats.top_speed,
                position=stats.position,
                laps_completed=stats.laps_completed,
                is_dnf=stats.is_dnf,
                tire_compounds_used=",".join(stats.tire_compounds_used),
                pit_stops=stats.pit_stops,
                pit_times=stats.pit_times,
            )
            self.db.add(driver_session)

        self.db.commit()
        logger.info("Synced session data for race %s session %s (%d drivers)", race_weekend_id, session_type, len(driver_stats))
        return True

    async def sync_race_results(self, race_weekend_id: int) -> bool:
        """
        Fetch race results from Jolyon API and store as ActualResult rows.
        Called after the race session is complete.
        """
        race = self.db.get(RaceWeekend, race_weekend_id)
        if not race:
            return False

        driver_map = self._get_driver_code_map()
        team_map = self._get_team_name_map()

        try:
            # Race results → RACE_TOP5 + FASTEST_LAP + DNF + TEAMMATE_BATTLE
            race_results = await self.jolyon.get_race_results(race.season, race.round)
            if not race_results:
                logger.warning("No race results from Jolyon for race %s", race_weekend_id)
                return False

            # Clear existing results for this race
            self.db.query(ActualResult).filter(ActualResult.race_weekend_id == race_weekend_id).delete()

            # Race top 5
            for result in race_results[:5]:
                driver_id = driver_map.get(result.driver_code)
                if driver_id:
                    self.db.add(ActualResult(
                        race_weekend_id=race_weekend_id,
                        category="race_top5",
                        position=result.position,
                        driver_id=driver_id,
                    ))

            # Fastest lap
            fl_driver = next((r for r in race_results if r.fastest_lap), None)
            if fl_driver:
                driver_id = driver_map.get(fl_driver.driver_code)
                team_id = team_map.get(fl_driver.team_name)
                if driver_id:
                    self.db.add(ActualResult(
                        race_weekend_id=race_weekend_id,
                        category="fastest_lap",
                        driver_id=driver_id,
                        team_id=team_id,
                    ))

            # DNFs
            for result in race_results:
                if result.status not in ("Finished", "") and "Lap" not in result.status:
                    driver_id = driver_map.get(result.driver_code)
                    if driver_id:
                        self.db.add(ActualResult(
                            race_weekend_id=race_weekend_id,
                            category="dnf",
                            driver_id=driver_id,
                        ))

            # Constructor points: team with most combined points
            team_points: dict[str, float] = {}
            for result in race_results:
                team_points[result.team_name] = team_points.get(result.team_name, 0) + result.points
            sorted_teams = sorted(team_points.items(), key=lambda x: x[1], reverse=True)
            for pos, (team_name, _) in enumerate(sorted_teams[:2], 1):
                team_id = team_map.get(team_name)
                if team_id:
                    self.db.add(ActualResult(
                        race_weekend_id=race_weekend_id,
                        category="constructor_points",
                        position=pos,
                        team_id=team_id,
                    ))

            # Teammate battles: compare finishing positions within each team
            team_drivers: dict[str, list] = {}
            for result in race_results:
                team_drivers.setdefault(result.team_name, []).append(result)
            for team_name, drivers in team_drivers.items():
                if len(drivers) >= 2:
                    winner = min(drivers, key=lambda d: d.position)
                    team_id = team_map.get(team_name)
                    driver_id = driver_map.get(winner.driver_code)
                    if team_id and driver_id:
                        self.db.add(ActualResult(
                            race_weekend_id=race_weekend_id,
                            category="teammate_battle",
                            team_id=team_id,
                            driver_id=driver_id,
                        ))

            # Pit stops
            pit_stops = await self.jolyon.get_pit_stops(race.season, race.round)
            if pit_stops:
                # Fastest pit stop by team
                team_best: dict[str, float] = {}
                for ps in pit_stops:
                    # Enrich team from race results
                    matching_result = next((r for r in race_results if r.driver_code == ps.driver_code), None)
                    if matching_result:
                        team_name = matching_result.team_name
                        if team_name not in team_best or ps.duration < team_best[team_name]:
                            team_best[team_name] = ps.duration

                if team_best:
                    fastest_team = min(team_best, key=team_best.get)
                    team_id = team_map.get(fastest_team)
                    if team_id:
                        self.db.add(ActualResult(
                            race_weekend_id=race_weekend_id,
                            category="quickest_pitstop",
                            team_id=team_id,
                            value=str(team_best[fastest_team]),
                        ))

                # Tire strategy: winner's pit stop count
                winner = race_results[0] if race_results else None
                if winner:
                    winner_stops = sum(1 for ps in pit_stops if ps.driver_code == winner.driver_code)
                    self.db.add(ActualResult(
                        race_weekend_id=race_weekend_id,
                        category="tire_strategy",
                        position=winner_stops,
                    ))

            # Qualifying results
            quali_results = await self.jolyon.get_qualifying_results(race.season, race.round)
            for qr in quali_results[:5]:
                driver_id = driver_map.get(qr.driver_code)
                if driver_id:
                    self.db.add(ActualResult(
                        race_weekend_id=race_weekend_id,
                        category="qualifying_top5",
                        position=qr.position,
                        driver_id=driver_id,
                    ))

            # Safety car: stored manually or via a secondary source (not in Jolyon)
            # For now we skip automated SC detection — it will be set via admin endpoint

            self.db.commit()
            logger.info("Synced race results for race %s", race_weekend_id)
            return True

        except Exception as e:
            logger.error("Failed to sync race results for race %s: %s", race_weekend_id, e)
            self.db.rollback()
            return False

    def _get_driver_code_map(self) -> dict[str, int]:
        """Map driver code (e.g., 'VER') to database ID."""
        drivers = self.db.query(Driver).filter(Driver.active.is_(True)).all()
        return {d.code: d.id for d in drivers}

    def _get_team_name_map(self) -> dict[str, int]:
        """Map team name to database ID. Handles common name variations."""
        teams = self.db.query(Team).filter(Team.active.is_(True)).all()
        team_map = {}
        for t in teams:
            team_map[t.name] = t.id
            team_map[t.short_name] = t.id
        return team_map
