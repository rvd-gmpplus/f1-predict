"""Client for the Jolyon F1 API — race results, standings, schedules, pit stops."""

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30.0


@dataclass
class RaceResult:
    position: int
    driver_code: str
    driver_name: str
    team_name: str
    grid_position: int
    status: str  # "Finished", "+1 Lap", "Retired", etc.
    points: float
    fastest_lap: bool = False
    fastest_lap_time: str | None = None


@dataclass
class QualifyingResult:
    position: int
    driver_code: str
    driver_name: str
    team_name: str
    q1_time: str | None = None
    q2_time: str | None = None
    q3_time: str | None = None


@dataclass
class PitStop:
    driver_code: str
    lap: int
    stop_number: int
    duration: float  # seconds
    team_name: str


@dataclass
class StandingEntry:
    position: int
    driver_code: str | None = None
    driver_name: str | None = None
    team_name: str | None = None
    points: float = 0.0
    wins: int = 0


@dataclass
class ScheduleEntry:
    round_number: int
    race_name: str
    circuit_id: str
    country: str
    fp1_date: str | None = None
    fp2_date: str | None = None
    fp3_date: str | None = None
    qualifying_date: str | None = None
    sprint_date: str | None = None
    race_date: str | None = None


@dataclass
class DriverInfo:
    code: str
    full_name: str
    number: int
    team_name: str
    country: str


@dataclass
class TeamInfo:
    name: str
    country: str
    drivers: list[str] = field(default_factory=list)


class JolyonAPIError(Exception):
    """Raised when the Jolyon API returns an error or is unreachable."""
    pass


class JolyonClient:
    """Async client for the Jolyon F1 data API."""

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.jolyon_api_base_url).rstrip("/")

    async def _get(self, path: str) -> Any:
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error("Jolyon API HTTP error %s for %s", e.response.status_code, url)
            raise JolyonAPIError(f"HTTP {e.response.status_code}: {url}") from e
        except httpx.RequestError as e:
            logger.error("Jolyon API request failed for %s: %s", url, e)
            raise JolyonAPIError(f"Request failed: {url}") from e

    async def get_race_results(self, season: int, round_num: int) -> list[RaceResult]:
        """Fetch race results for a specific round."""
        data = await self._get(f"/{season}/{round_num}/results")
        results = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
        if not results:
            return []

        race = results[0]
        parsed = []
        for r in race.get("Results", []):
            driver = r.get("Driver", {})
            constructor = r.get("Constructor", {})
            fastest_lap = r.get("FastestLap", {})
            parsed.append(RaceResult(
                position=int(r.get("position", 0)),
                driver_code=driver.get("code", ""),
                driver_name=f"{driver.get('givenName', '')} {driver.get('familyName', '')}".strip(),
                team_name=constructor.get("name", ""),
                grid_position=int(r.get("grid", 0)),
                status=r.get("status", ""),
                points=float(r.get("points", 0)),
                fastest_lap=fastest_lap.get("rank") == "1",
                fastest_lap_time=fastest_lap.get("Time", {}).get("time"),
            ))
        return parsed

    async def get_qualifying_results(self, season: int, round_num: int) -> list[QualifyingResult]:
        """Fetch qualifying results for a specific round."""
        data = await self._get(f"/{season}/{round_num}/qualifying")
        results = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
        if not results:
            return []

        race = results[0]
        parsed = []
        for r in race.get("QualifyingResults", []):
            driver = r.get("Driver", {})
            constructor = r.get("Constructor", {})
            parsed.append(QualifyingResult(
                position=int(r.get("position", 0)),
                driver_code=driver.get("code", ""),
                driver_name=f"{driver.get('givenName', '')} {driver.get('familyName', '')}".strip(),
                team_name=constructor.get("name", ""),
                q1_time=r.get("Q1"),
                q2_time=r.get("Q2"),
                q3_time=r.get("Q3"),
            ))
        return parsed

    async def get_pit_stops(self, season: int, round_num: int) -> list[PitStop]:
        """Fetch pit stop data for a specific round."""
        data = await self._get(f"/{season}/{round_num}/pitstops")
        results = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
        if not results:
            return []

        race = results[0]
        parsed = []
        for p in race.get("PitStops", []):
            parsed.append(PitStop(
                driver_code=p.get("driverId", ""),
                lap=int(p.get("lap", 0)),
                stop_number=int(p.get("stop", 0)),
                duration=_parse_pit_duration(p.get("duration", "0")),
                team_name="",  # pit stop endpoint doesn't include team; enriched later
            ))
        return parsed

    async def get_driver_standings(self, season: int) -> list[StandingEntry]:
        """Fetch current driver standings for a season."""
        data = await self._get(f"/{season}/driverStandings")
        lists = data.get("MRData", {}).get("StandingsTable", {}).get("StandingsLists", [])
        if not lists:
            return []

        standings = lists[0]
        parsed = []
        for s in standings.get("DriverStandings", []):
            driver = s.get("Driver", {})
            constructors = s.get("Constructors", [])
            team_name = constructors[0].get("name", "") if constructors else ""
            parsed.append(StandingEntry(
                position=int(s.get("position", 0)),
                driver_code=driver.get("code", ""),
                driver_name=f"{driver.get('givenName', '')} {driver.get('familyName', '')}".strip(),
                team_name=team_name,
                points=float(s.get("points", 0)),
                wins=int(s.get("wins", 0)),
            ))
        return parsed

    async def get_constructor_standings(self, season: int) -> list[StandingEntry]:
        """Fetch current constructor standings for a season."""
        data = await self._get(f"/{season}/constructorStandings")
        lists = data.get("MRData", {}).get("StandingsTable", {}).get("StandingsLists", [])
        if not lists:
            return []

        standings = lists[0]
        parsed = []
        for s in standings.get("ConstructorStandings", []):
            constructor = s.get("Constructor", {})
            parsed.append(StandingEntry(
                position=int(s.get("position", 0)),
                team_name=constructor.get("name", ""),
                points=float(s.get("points", 0)),
                wins=int(s.get("wins", 0)),
            ))
        return parsed

    async def get_schedule(self, season: int) -> list[ScheduleEntry]:
        """Fetch the full race schedule for a season."""
        data = await self._get(f"/{season}")
        races = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
        parsed = []
        for race in races:
            circuit = race.get("Circuit", {})
            location = circuit.get("Location", {})
            parsed.append(ScheduleEntry(
                round_number=int(race.get("round", 0)),
                race_name=race.get("raceName", ""),
                circuit_id=circuit.get("circuitId", ""),
                country=location.get("country", ""),
                fp1_date=race.get("FirstPractice", {}).get("date"),
                fp2_date=race.get("SecondPractice", {}).get("date"),
                fp3_date=race.get("ThirdPractice", {}).get("date"),
                qualifying_date=race.get("Qualifying", {}).get("date"),
                sprint_date=race.get("Sprint", {}).get("date"),
                race_date=race.get("date"),
            ))
        return parsed

    async def get_drivers(self, season: int) -> list[DriverInfo]:
        """Fetch all drivers for a season."""
        data = await self._get(f"/{season}/drivers")
        drivers = data.get("MRData", {}).get("DriverTable", {}).get("Drivers", [])
        parsed = []
        for d in drivers:
            parsed.append(DriverInfo(
                code=d.get("code", ""),
                full_name=f"{d.get('givenName', '')} {d.get('familyName', '')}".strip(),
                number=int(d.get("permanentNumber", 0)),
                team_name="",  # enriched from standings or constructor endpoint
                country=d.get("nationality", ""),
            ))
        return parsed

    async def get_constructors(self, season: int) -> list[TeamInfo]:
        """Fetch all constructors for a season."""
        data = await self._get(f"/{season}/constructors")
        constructors = data.get("MRData", {}).get("ConstructorTable", {}).get("Constructors", [])
        parsed = []
        for c in constructors:
            parsed.append(TeamInfo(
                name=c.get("name", ""),
                country=c.get("nationality", ""),
            ))
        return parsed


def _parse_pit_duration(duration_str: str) -> float:
    """Parse pit stop duration string (e.g., '23.456' or '1:23.456') to seconds."""
    try:
        if ":" in duration_str:
            parts = duration_str.split(":")
            return float(parts[0]) * 60 + float(parts[1])
        return float(duration_str)
    except (ValueError, IndexError):
        return 0.0
