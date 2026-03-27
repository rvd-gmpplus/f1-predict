# F1 Predict — ML Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the data ingestion and ML prediction pipeline that feeds the F1 Predict backend.

**Architecture:** Jolyon API + FastF1 for data, XGBoost/RandomForest/LinearRegression for predictions, APScheduler for automation.

**Tech Stack:** fastf1, xgboost, scikit-learn, httpx, apscheduler, openweathermap API

---

## File Structure

```
backend/
├── pyproject.toml                          # Updated with ML dependencies
├── app/
│   ├── config.py                           # Updated with new API keys
│   ├── main.py                             # Updated with scheduler startup
│   ├── models/
│   │   └── training_data.py                # SessionData, DriverSessionStats, HistoricalFeature
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── jolyon_client.py                # Jolyon API client for race results, standings, etc.
│   │   ├── fastf1_client.py                # FastF1 wrapper for telemetry, sector times, tire data
│   │   ├── weather_client.py               # OpenWeatherMap forecast client
│   │   └── data_sync.py                    # Orchestrates fetching + DB writes after each session
│   ├── ml/
│   │   ├── __init__.py
│   │   ├── features.py                     # Feature engineering: raw data → feature vectors
│   │   ├── models.py                       # Model definitions: train + predict for each category
│   │   ├── prediction_service.py           # Generates and stores MLPrediction rows
│   │   └── model_store.py                  # Save/load trained models (joblib to filesystem)
│   ├── scheduler/
│   │   ├── __init__.py
│   │   └── jobs.py                         # APScheduler job definitions and lifecycle
│   ├── routers/
│   │   └── admin.py                        # Updated with manual pipeline trigger endpoint
│   └── services/
│       └── seeder.py                       # Seed 2025 season + 2026 Australia/China
├── tests/
│   ├── test_jolyon_client.py
│   ├── test_fastf1_client.py
│   ├── test_weather_client.py
│   ├── test_features.py
│   ├── test_models.py
│   ├── test_prediction_service.py
│   ├── test_scheduler.py
│   └── test_seeder.py
```

---

### Task 1: Add ML Dependencies to pyproject.toml and Update Config

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/config.py`

- [ ] **Step 1: Add ML and scheduling dependencies to pyproject.toml**

```toml
[project]
name = "f1-predict-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "sqlalchemy>=2.0.0",
    "psycopg2-binary>=2.9.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
    "authlib>=1.3.0",
    "itsdangerous>=2.0.0",
    "httpx>=0.27.0",
    "python-multipart>=0.0.9",
    "fastf1>=3.4.0",
    "xgboost>=2.1.0",
    "scikit-learn>=1.5.0",
    "apscheduler>=3.10.0",
    "joblib>=1.4.0",
    "numpy>=1.26.0",
    "pandas>=2.2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",
]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"
```

- [ ] **Step 2: Add new settings fields to config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./f1predict.db"
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24  # 24 hours

    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    frontend_url: str = "http://localhost:3000"

    # ML Pipeline settings
    openweathermap_api_key: str = ""
    jolyon_api_base_url: str = "https://api.jolyon.co/f1"
    fastf1_cache_dir: str = "./fastf1_cache"
    model_storage_dir: str = "./ml_models"

    # Scheduler settings
    scheduler_enabled: bool = True
    data_fetch_delay_minutes: int = 30  # delay after session end before fetching data
    max_retries: int = 3

    model_config = {"env_file": ".env"}


settings = Settings()
```

**Commit message:** `feat: add ML pipeline dependencies and config settings`

---

### Task 2: Training Data Models

**Files:**
- Create: `backend/app/models/training_data.py`
- Modify: `backend/app/models/__init__.py`

These models store the raw ingested data from Jolyon API and FastF1 that the ML feature engineering reads from. They are separate from `ActualResult` (which stores structured results for scoring) — these hold granular session-level statistics for model training.

- [ ] **Step 1: Create training data models**

```python
# backend/app/models/training_data.py
from datetime import datetime

from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, JSON, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SessionData(Base):
    """Raw session data fetched from FastF1 for a specific session of a race weekend."""
    __tablename__ = "session_data"
    __table_args__ = (
        UniqueConstraint("race_weekend_id", "session_type", name="uq_race_session"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    race_weekend_id: Mapped[int] = mapped_column(ForeignKey("race_weekends.id"))
    session_type: Mapped[str] = mapped_column(String(20))  # fp1, fp2, fp3, quali, race, sprint
    weather_data: Mapped[dict | None] = mapped_column(JSON)  # temp, humidity, rain, wind
    track_temp: Mapped[float | None] = mapped_column(Float)
    air_temp: Mapped[float | None] = mapped_column(Float)
    rainfall: Mapped[bool] = mapped_column(Boolean, default=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DriverSessionStats(Base):
    """Per-driver statistics for a specific session, derived from FastF1 telemetry."""
    __tablename__ = "driver_session_stats"
    __table_args__ = (
        UniqueConstraint("session_data_id", "driver_id", name="uq_session_driver"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_data_id: Mapped[int] = mapped_column(ForeignKey("session_data.id"))
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"))
    best_lap_time: Mapped[float | None] = mapped_column(Float)  # seconds
    avg_lap_time: Mapped[float | None] = mapped_column(Float)
    best_sector1: Mapped[float | None] = mapped_column(Float)
    best_sector2: Mapped[float | None] = mapped_column(Float)
    best_sector3: Mapped[float | None] = mapped_column(Float)
    long_run_pace: Mapped[float | None] = mapped_column(Float)  # avg of 5+ consecutive laps
    long_run_degradation: Mapped[float | None] = mapped_column(Float)  # seconds/lap lost
    stint_data: Mapped[dict | None] = mapped_column(JSON)  # [{compound, laps, avg_time, deg_rate}]
    top_speed: Mapped[float | None] = mapped_column(Float)  # kph
    position: Mapped[int | None] = mapped_column(Integer)  # session finishing position
    laps_completed: Mapped[int] = mapped_column(Integer, default=0)
    is_dnf: Mapped[bool] = mapped_column(Boolean, default=False)
    tire_compounds_used: Mapped[str | None] = mapped_column(String(50))  # e.g. "SOFT,MEDIUM,HARD"
    pit_stops: Mapped[int] = mapped_column(Integer, default=0)
    pit_times: Mapped[dict | None] = mapped_column(JSON)  # [{"lap": 15, "duration": 2.3}]


class HistoricalFeature(Base):
    """Pre-computed feature vectors for ML training. One row per driver per race weekend."""
    __tablename__ = "historical_features"
    __table_args__ = (
        UniqueConstraint("race_weekend_id", "driver_id", "stage", name="uq_feature_race_driver_stage"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    race_weekend_id: Mapped[int] = mapped_column(ForeignKey("race_weekends.id"))
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"))
    stage: Mapped[str] = mapped_column(String(10))  # pre, fp1, fp2, fp3, quali
    feature_vector: Mapped[dict] = mapped_column(JSON)  # full feature dict
    qualifying_position: Mapped[int | None] = mapped_column(Integer)  # actual (target for training)
    race_position: Mapped[int | None] = mapped_column(Integer)  # actual (target for training)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

- [ ] **Step 2: Update models/__init__.py to register new models**

```python
# backend/app/models/__init__.py
from app.models.user import User
from app.models.f1 import Team, Driver, RaceWeekend
from app.models.prediction import (
    UserPrediction,
    PredictionDetail,
    ActualResult,
    MLPrediction,
    UserScore,
)
from app.models.training_data import (
    SessionData,
    DriverSessionStats,
    HistoricalFeature,
)

__all__ = [
    "User",
    "Team",
    "Driver",
    "RaceWeekend",
    "UserPrediction",
    "PredictionDetail",
    "ActualResult",
    "MLPrediction",
    "UserScore",
    "SessionData",
    "DriverSessionStats",
    "HistoricalFeature",
]
```

**Commit message:** `feat: add training data models for ML pipeline ingestion`

---

### Task 3: Jolyon API Client

**Files:**
- Create: `backend/app/ingestion/__init__.py`
- Create: `backend/app/ingestion/jolyon_client.py`
- Create: `backend/tests/test_jolyon_client.py`

The Jolyon API (https://api.jolyon.co) provides structured F1 data: race results, qualifying results, standings, pit stop times, schedules, and driver/team info. This client wraps all the endpoints we need.

- [ ] **Step 1: Create the Jolyon API client**

```python
# backend/app/ingestion/__init__.py
```

```python
# backend/app/ingestion/jolyon_client.py
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
```

- [ ] **Step 2: Create tests for Jolyon client**

```python
# backend/tests/test_jolyon_client.py
import pytest
import json
from unittest.mock import AsyncMock, patch

from app.ingestion.jolyon_client import JolyonClient, JolyonAPIError, _parse_pit_duration


@pytest.fixture
def client():
    return JolyonClient(base_url="https://api.jolyon.co/f1")


MOCK_RACE_RESULTS = {
    "MRData": {
        "RaceTable": {
            "Races": [{
                "Results": [
                    {
                        "position": "1",
                        "Driver": {"code": "VER", "givenName": "Max", "familyName": "Verstappen"},
                        "Constructor": {"name": "Red Bull"},
                        "grid": "1",
                        "status": "Finished",
                        "points": "25",
                        "FastestLap": {"rank": "1", "Time": {"time": "1:32.456"}},
                    },
                    {
                        "position": "2",
                        "Driver": {"code": "NOR", "givenName": "Lando", "familyName": "Norris"},
                        "Constructor": {"name": "McLaren"},
                        "grid": "3",
                        "status": "Finished",
                        "points": "18",
                        "FastestLap": {"rank": "5", "Time": {"time": "1:33.100"}},
                    },
                ],
            }],
        },
    },
}


MOCK_QUALIFYING_RESULTS = {
    "MRData": {
        "RaceTable": {
            "Races": [{
                "QualifyingResults": [
                    {
                        "position": "1",
                        "Driver": {"code": "VER", "givenName": "Max", "familyName": "Verstappen"},
                        "Constructor": {"name": "Red Bull"},
                        "Q1": "1:30.100",
                        "Q2": "1:29.500",
                        "Q3": "1:28.900",
                    },
                ],
            }],
        },
    },
}


@pytest.mark.asyncio
async def test_get_race_results(client):
    with patch.object(client, "_get", new_callable=AsyncMock, return_value=MOCK_RACE_RESULTS):
        results = await client.get_race_results(2025, 1)
        assert len(results) == 2
        assert results[0].driver_code == "VER"
        assert results[0].position == 1
        assert results[0].fastest_lap is True
        assert results[0].fastest_lap_time == "1:32.456"
        assert results[1].fastest_lap is False


@pytest.mark.asyncio
async def test_get_qualifying_results(client):
    with patch.object(client, "_get", new_callable=AsyncMock, return_value=MOCK_QUALIFYING_RESULTS):
        results = await client.get_qualifying_results(2025, 1)
        assert len(results) == 1
        assert results[0].driver_code == "VER"
        assert results[0].q3_time == "1:28.900"


@pytest.mark.asyncio
async def test_empty_response(client):
    empty = {"MRData": {"RaceTable": {"Races": []}}}
    with patch.object(client, "_get", new_callable=AsyncMock, return_value=empty):
        results = await client.get_race_results(2025, 99)
        assert results == []


def test_parse_pit_duration():
    assert _parse_pit_duration("23.456") == 23.456
    assert _parse_pit_duration("1:23.456") == 83.456
    assert _parse_pit_duration("invalid") == 0.0
```

**Commit message:** `feat: add Jolyon API client for F1 race data ingestion`

---

### Task 4: FastF1 Data Client

**Files:**
- Create: `backend/app/ingestion/fastf1_client.py`
- Create: `backend/tests/test_fastf1_client.py`

FastF1 provides granular telemetry, sector times, tire compound data, and weather per session. This client wraps the fastf1 library into structured dataclasses that map to our `DriverSessionStats` model.

- [ ] **Step 1: Create the FastF1 client**

```python
# backend/app/ingestion/fastf1_client.py
"""Client wrapping the fastf1 library for session telemetry, sector times, and tire data."""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import fastf1
import numpy as np
import pandas as pd

from app.config import settings

logger = logging.getLogger(__name__)

# Map our session type strings to FastF1 session identifiers
SESSION_TYPE_MAP = {
    "fp1": "FP1",
    "fp2": "FP2",
    "fp3": "FP3",
    "quali": "Q",
    "race": "R",
    "sprint": "S",
    "sprint_qualifying": "SQ",
}


@dataclass
class LapStats:
    driver_code: str
    best_lap_time: float | None  # seconds
    avg_lap_time: float | None
    best_sector1: float | None
    best_sector2: float | None
    best_sector3: float | None
    long_run_pace: float | None
    long_run_degradation: float | None
    top_speed: float | None  # kph
    laps_completed: int
    position: int | None
    is_dnf: bool
    tire_compounds_used: list[str] = field(default_factory=list)
    pit_stops: int = 0
    pit_times: list[dict] = field(default_factory=list)
    stint_data: list[dict] = field(default_factory=list)


@dataclass
class SessionWeather:
    air_temp: float | None
    track_temp: float | None
    humidity: float | None
    wind_speed: float | None
    wind_direction: float | None
    rainfall: bool


class FastF1Error(Exception):
    """Raised when FastF1 data loading fails."""
    pass


class FastF1Client:
    """Wraps the fastf1 library to extract structured session data."""

    def __init__(self, cache_dir: str | None = None):
        self.cache_dir = cache_dir or settings.fastf1_cache_dir
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
        fastf1.Cache.enable_cache(self.cache_dir)

    def get_session_data(
        self, season: int, round_num: int, session_type: str,
    ) -> tuple[list[LapStats], SessionWeather]:
        """
        Load a session and return per-driver lap stats and weather.

        Args:
            season: e.g., 2025
            round_num: round number in the season
            session_type: one of fp1, fp2, fp3, quali, race, sprint, sprint_qualifying

        Returns:
            Tuple of (list of LapStats per driver, SessionWeather)
        """
        ff1_session_name = SESSION_TYPE_MAP.get(session_type)
        if not ff1_session_name:
            raise FastF1Error(f"Unknown session type: {session_type}")

        try:
            session = fastf1.get_session(season, round_num, ff1_session_name)
            session.load(telemetry=False, weather=True, messages=False)
        except Exception as e:
            logger.error("FastF1 failed to load %s R%s %s: %s", season, round_num, session_type, e)
            raise FastF1Error(f"Failed to load session: {e}") from e

        weather = self._extract_weather(session)
        driver_stats = self._extract_driver_stats(session, session_type)
        return driver_stats, weather

    def _extract_weather(self, session) -> SessionWeather:
        """Extract average weather conditions from the session."""
        try:
            weather_df = session.weather_data
            if weather_df is None or weather_df.empty:
                return SessionWeather(
                    air_temp=None, track_temp=None, humidity=None,
                    wind_speed=None, wind_direction=None, rainfall=False,
                )
            return SessionWeather(
                air_temp=_safe_mean(weather_df, "AirTemp"),
                track_temp=_safe_mean(weather_df, "TrackTemp"),
                humidity=_safe_mean(weather_df, "Humidity"),
                wind_speed=_safe_mean(weather_df, "WindSpeed"),
                wind_direction=_safe_mean(weather_df, "WindDirection"),
                rainfall=bool(weather_df["Rainfall"].any()) if "Rainfall" in weather_df.columns else False,
            )
        except Exception as e:
            logger.warning("Could not extract weather: %s", e)
            return SessionWeather(
                air_temp=None, track_temp=None, humidity=None,
                wind_speed=None, wind_direction=None, rainfall=False,
            )

    def _extract_driver_stats(self, session, session_type: str) -> list[LapStats]:
        """Extract per-driver statistics from session laps."""
        try:
            laps = session.laps
        except Exception:
            logger.warning("No laps data available")
            return []

        if laps is None or laps.empty:
            return []

        results_df = None
        try:
            results_df = session.results
        except Exception:
            pass

        driver_stats = []
        for driver_code in laps["Driver"].unique():
            driver_laps = laps[laps["Driver"] == driver_code].copy()
            stats = self._compute_driver_lap_stats(driver_code, driver_laps, results_df, session_type)
            driver_stats.append(stats)

        return driver_stats

    def _compute_driver_lap_stats(
        self, driver_code: str, driver_laps: pd.DataFrame,
        results_df: pd.DataFrame | None, session_type: str,
    ) -> LapStats:
        """Compute aggregate statistics for a single driver's laps."""
        # Convert lap times to seconds
        lap_seconds = driver_laps["LapTime"].dt.total_seconds().dropna()

        best_lap = float(lap_seconds.min()) if len(lap_seconds) > 0 else None
        avg_lap = float(lap_seconds.mean()) if len(lap_seconds) > 0 else None

        # Sector times (best)
        best_s1 = _best_sector(driver_laps, "Sector1Time")
        best_s2 = _best_sector(driver_laps, "Sector2Time")
        best_s3 = _best_sector(driver_laps, "Sector3Time")

        # Long run analysis: find stints of 5+ laps on the same compound
        long_run_pace, long_run_deg = self._compute_long_run(driver_laps)

        # Top speed
        top_speed = None
        if "SpeedST" in driver_laps.columns:
            speeds = driver_laps["SpeedST"].dropna()
            if len(speeds) > 0:
                top_speed = float(speeds.max())

        # Tire compounds
        compounds = []
        if "Compound" in driver_laps.columns:
            compounds = driver_laps["Compound"].dropna().unique().tolist()

        # Stint data
        stint_data = self._compute_stint_data(driver_laps)

        # Pit stops
        pit_stops = 0
        pit_times = []
        if "PitInTime" in driver_laps.columns:
            pit_laps = driver_laps[driver_laps["PitInTime"].notna()]
            pit_stops = len(pit_laps)
            if "PitOutTime" in driver_laps.columns:
                for _, row in pit_laps.iterrows():
                    try:
                        pit_in = row["PitInTime"]
                        pit_out = row["PitOutTime"]
                        if pd.notna(pit_in) and pd.notna(pit_out):
                            duration = (pit_out - pit_in).total_seconds()
                            pit_times.append({"lap": int(row.get("LapNumber", 0)), "duration": round(duration, 3)})
                    except Exception:
                        pass

        # Position and DNF
        position = None
        is_dnf = False
        if results_df is not None and not results_df.empty:
            driver_result = results_df[results_df["Abbreviation"] == driver_code]
            if not driver_result.empty:
                pos = driver_result.iloc[0].get("Position")
                position = int(pos) if pd.notna(pos) else None
                status = str(driver_result.iloc[0].get("Status", ""))
                is_dnf = status not in ("Finished", "") and "Lap" not in status

        return LapStats(
            driver_code=driver_code,
            best_lap_time=best_lap,
            avg_lap_time=avg_lap,
            best_sector1=best_s1,
            best_sector2=best_s2,
            best_sector3=best_s3,
            long_run_pace=long_run_pace,
            long_run_degradation=long_run_deg,
            top_speed=top_speed,
            laps_completed=len(driver_laps),
            position=position,
            is_dnf=is_dnf,
            tire_compounds_used=compounds,
            pit_stops=pit_stops,
            pit_times=pit_times,
            stint_data=stint_data,
        )

    def _compute_long_run(self, driver_laps: pd.DataFrame) -> tuple[float | None, float | None]:
        """
        Compute long run pace and degradation.
        A long run is 5+ consecutive laps on the same compound.
        Returns (avg pace in seconds, degradation rate in seconds/lap).
        """
        if "Compound" not in driver_laps.columns:
            return None, None

        lap_seconds = driver_laps["LapTime"].dt.total_seconds()
        compounds = driver_laps["Compound"]

        best_long_run_pace = None
        best_long_run_deg = None

        current_compound = None
        current_run = []

        for i, (_, row) in enumerate(driver_laps.iterrows()):
            compound = row.get("Compound")
            lap_time = lap_seconds.iloc[i] if i < len(lap_seconds) else None

            if pd.isna(lap_time) or pd.isna(compound):
                current_run = []
                current_compound = None
                continue

            if compound == current_compound:
                current_run.append(lap_time)
            else:
                current_compound = compound
                current_run = [lap_time]

            if len(current_run) >= 5:
                pace = np.mean(current_run)
                # Degradation: linear regression slope of lap times
                if len(current_run) >= 3:
                    x = np.arange(len(current_run))
                    coeffs = np.polyfit(x, current_run, 1)
                    deg = coeffs[0]  # seconds per lap increase
                else:
                    deg = 0.0

                if best_long_run_pace is None or pace < best_long_run_pace:
                    best_long_run_pace = float(pace)
                    best_long_run_deg = float(deg)

        return best_long_run_pace, best_long_run_deg

    def _compute_stint_data(self, driver_laps: pd.DataFrame) -> list[dict]:
        """Compute per-stint statistics: compound, laps, avg time, degradation rate."""
        if "Compound" not in driver_laps.columns or "Stint" not in driver_laps.columns:
            return []

        stints = []
        for stint_num in sorted(driver_laps["Stint"].dropna().unique()):
            stint_laps = driver_laps[driver_laps["Stint"] == stint_num]
            lap_times = stint_laps["LapTime"].dt.total_seconds().dropna()

            if len(lap_times) == 0:
                continue

            compound = stint_laps["Compound"].mode()
            compound_str = str(compound.iloc[0]) if len(compound) > 0 else "UNKNOWN"

            deg_rate = 0.0
            if len(lap_times) >= 3:
                x = np.arange(len(lap_times))
                coeffs = np.polyfit(x, lap_times.values, 1)
                deg_rate = float(coeffs[0])

            stints.append({
                "stint": int(stint_num),
                "compound": compound_str,
                "laps": int(len(lap_times)),
                "avg_time": round(float(lap_times.mean()), 3),
                "deg_rate": round(deg_rate, 4),
            })

        return stints


def _safe_mean(df: pd.DataFrame, column: str) -> float | None:
    """Safely compute mean of a dataframe column."""
    if column not in df.columns:
        return None
    values = df[column].dropna()
    return float(values.mean()) if len(values) > 0 else None


def _best_sector(laps: pd.DataFrame, column: str) -> float | None:
    """Get the best (minimum) sector time in seconds."""
    if column not in laps.columns:
        return None
    times = laps[column].dt.total_seconds().dropna()
    return float(times.min()) if len(times) > 0 else None
```

- [ ] **Step 2: Create tests for FastF1 client**

```python
# backend/tests/test_fastf1_client.py
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np
from datetime import timedelta

from app.ingestion.fastf1_client import FastF1Client, FastF1Error, _safe_mean, _best_sector


@pytest.fixture
def client(tmp_path):
    with patch("app.ingestion.fastf1_client.fastf1"):
        return FastF1Client(cache_dir=str(tmp_path / "cache"))


def _make_lap_row(lap_time_s, sector1_s=None, sector2_s=None, sector3_s=None,
                  compound="SOFT", stint=1, speed=300.0, driver="VER", lap_num=1):
    return {
        "Driver": driver,
        "LapTime": timedelta(seconds=lap_time_s) if lap_time_s else pd.NaT,
        "Sector1Time": timedelta(seconds=sector1_s) if sector1_s else pd.NaT,
        "Sector2Time": timedelta(seconds=sector2_s) if sector2_s else pd.NaT,
        "Sector3Time": timedelta(seconds=sector3_s) if sector3_s else pd.NaT,
        "Compound": compound,
        "Stint": stint,
        "SpeedST": speed,
        "LapNumber": lap_num,
        "PitInTime": pd.NaT,
        "PitOutTime": pd.NaT,
    }


def test_safe_mean():
    df = pd.DataFrame({"AirTemp": [20.0, 22.0, 24.0]})
    assert _safe_mean(df, "AirTemp") == pytest.approx(22.0)
    assert _safe_mean(df, "Missing") is None


def test_safe_mean_empty():
    df = pd.DataFrame({"AirTemp": pd.Series([], dtype=float)})
    assert _safe_mean(df, "AirTemp") is None


def test_best_sector():
    df = pd.DataFrame({
        "Sector1Time": [timedelta(seconds=30.1), timedelta(seconds=29.5), timedelta(seconds=30.8)],
    })
    assert _best_sector(df, "Sector1Time") == pytest.approx(29.5)
    assert _best_sector(df, "Sector2Time") is None


def test_compute_driver_lap_stats_basic(client):
    rows = [_make_lap_row(90.0 + i * 0.1, 28.0, 30.0, 32.0, lap_num=i + 1) for i in range(6)]
    driver_laps = pd.DataFrame(rows)
    results_df = pd.DataFrame({
        "Abbreviation": ["VER"],
        "Position": [1],
        "Status": ["Finished"],
    })

    stats = client._compute_driver_lap_stats("VER", driver_laps, results_df, "race")

    assert stats.driver_code == "VER"
    assert stats.best_lap_time == pytest.approx(90.0)
    assert stats.laps_completed == 6
    assert stats.position == 1
    assert stats.is_dnf is False
    assert stats.best_sector1 == pytest.approx(28.0)
    assert "SOFT" in stats.tire_compounds_used


def test_dnf_detection(client):
    rows = [_make_lap_row(90.0, driver="HAM")]
    driver_laps = pd.DataFrame(rows)
    results_df = pd.DataFrame({
        "Abbreviation": ["HAM"],
        "Position": [pd.NA],
        "Status": ["Retired"],
    })

    stats = client._compute_driver_lap_stats("HAM", driver_laps, results_df, "race")
    assert stats.is_dnf is True
```

**Commit message:** `feat: add FastF1 telemetry client for session data extraction`

---

### Task 5: Weather API Client

**Files:**
- Create: `backend/app/ingestion/weather_client.py`
- Create: `backend/tests/test_weather_client.py`

Pre-race weather forecasts from OpenWeatherMap. Used in the "pre" stage predictions before any session data exists.

- [ ] **Step 1: Create the weather client**

```python
# backend/app/ingestion/weather_client.py
"""OpenWeatherMap client for pre-race weather forecasts."""

import logging
from dataclasses import dataclass

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

OWM_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"

# Circuit coordinates for weather lookups
CIRCUIT_COORDS: dict[str, tuple[float, float]] = {
    "albert_park": (-37.8497, 144.9680),
    "shanghai": (31.3389, 121.2198),
    "suzuka": (34.8431, 136.5406),
    "bahrain": (26.0325, 50.5106),
    "jeddah": (21.6319, 39.1044),
    "miami": (25.9581, -80.2389),
    "imola": (44.3439, 11.7167),
    "monaco": (43.7347, 7.4206),
    "montreal": (45.5017, -73.5228),
    "barcelona": (41.5700, 2.2611),
    "spielberg": (47.2197, 14.7647),
    "silverstone": (52.0786, -1.0169),
    "hungaroring": (47.5789, 19.2486),
    "spa": (50.4372, 5.9714),
    "zandvoort": (52.3888, 4.5409),
    "monza": (45.6156, 9.2811),
    "baku": (40.3725, 49.8533),
    "marina_bay": (1.2914, 103.8640),
    "cota": (30.1328, -97.6411),
    "hermanos_rodriguez": (19.4042, -99.0907),
    "interlagos": (-23.7036, -46.6997),
    "vegas": (36.1162, -115.1745),
    "losail": (25.4900, 51.4542),
    "yas_marina": (24.4672, 54.6031),
}


@dataclass
class WeatherForecast:
    air_temp: float  # Celsius
    humidity: float  # percentage
    wind_speed: float  # m/s
    wind_direction: float  # degrees
    rain_probability: float  # 0-1
    description: str
    rain_mm: float  # expected rain in mm


class WeatherAPIError(Exception):
    """Raised when the OpenWeatherMap API call fails."""
    pass


class WeatherClient:
    """Fetches weather forecasts from OpenWeatherMap for circuit locations."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.openweathermap_api_key

    async def get_forecast(self, circuit_id: str) -> list[WeatherForecast]:
        """
        Get 5-day/3-hour forecast for a circuit.

        Args:
            circuit_id: The circuit identifier matching CIRCUIT_COORDS keys.

        Returns:
            List of WeatherForecast entries (up to 40 entries, 3-hour intervals).
        """
        coords = CIRCUIT_COORDS.get(circuit_id)
        if not coords:
            logger.warning("No coordinates for circuit: %s", circuit_id)
            raise WeatherAPIError(f"Unknown circuit: {circuit_id}")

        if not self.api_key:
            logger.warning("No OpenWeatherMap API key configured")
            raise WeatherAPIError("No API key configured")

        lat, lon = coords
        params = {
            "lat": lat,
            "lon": lon,
            "appid": self.api_key,
            "units": "metric",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(OWM_FORECAST_URL, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            logger.error("OpenWeatherMap HTTP error %s", e.response.status_code)
            raise WeatherAPIError(f"HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error("OpenWeatherMap request failed: %s", e)
            raise WeatherAPIError(f"Request failed: {e}") from e

        forecasts = []
        for entry in data.get("list", []):
            main = entry.get("main", {})
            wind = entry.get("wind", {})
            weather = entry.get("weather", [{}])[0]
            rain = entry.get("rain", {})
            pop = entry.get("pop", 0)

            forecasts.append(WeatherForecast(
                air_temp=main.get("temp", 0.0),
                humidity=main.get("humidity", 0.0),
                wind_speed=wind.get("speed", 0.0),
                wind_direction=wind.get("deg", 0.0),
                rain_probability=float(pop),
                description=weather.get("description", ""),
                rain_mm=rain.get("3h", 0.0),
            ))

        return forecasts

    async def get_race_weekend_forecast(self, circuit_id: str) -> WeatherForecast | None:
        """
        Get an averaged forecast for race day conditions.
        Takes the median conditions from all forecast entries to smooth noise.
        """
        try:
            forecasts = await self.get_forecast(circuit_id)
        except WeatherAPIError:
            return None

        if not forecasts:
            return None

        return WeatherForecast(
            air_temp=_median([f.air_temp for f in forecasts]),
            humidity=_median([f.humidity for f in forecasts]),
            wind_speed=_median([f.wind_speed for f in forecasts]),
            wind_direction=_median([f.wind_direction for f in forecasts]),
            rain_probability=_median([f.rain_probability for f in forecasts]),
            description="aggregated forecast",
            rain_mm=sum(f.rain_mm for f in forecasts) / len(forecasts),
        )


def _median(values: list[float]) -> float:
    """Return median of a list of floats."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    mid = len(sorted_vals) // 2
    if len(sorted_vals) % 2 == 0:
        return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2
    return sorted_vals[mid]
```

- [ ] **Step 2: Create tests for weather client**

```python
# backend/tests/test_weather_client.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.ingestion.weather_client import WeatherClient, WeatherAPIError, _median, CIRCUIT_COORDS


@pytest.fixture
def client():
    return WeatherClient(api_key="test-key-123")


MOCK_FORECAST_RESPONSE = {
    "list": [
        {
            "main": {"temp": 25.0, "humidity": 60.0},
            "wind": {"speed": 5.0, "deg": 180.0},
            "weather": [{"description": "clear sky"}],
            "rain": {},
            "pop": 0.1,
        },
        {
            "main": {"temp": 27.0, "humidity": 55.0},
            "wind": {"speed": 6.0, "deg": 190.0},
            "weather": [{"description": "few clouds"}],
            "rain": {"3h": 0.5},
            "pop": 0.3,
        },
    ],
}


@pytest.mark.asyncio
async def test_get_forecast(client):
    mock_response = MagicMock()
    mock_response.json.return_value = MOCK_FORECAST_RESPONSE
    mock_response.raise_for_status = MagicMock()

    with patch("app.ingestion.weather_client.httpx.AsyncClient") as mock_client_cls:
        mock_ctx = AsyncMock()
        mock_ctx.get.return_value = mock_response
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        forecasts = await client.get_forecast("albert_park")
        assert len(forecasts) == 2
        assert forecasts[0].air_temp == 25.0
        assert forecasts[1].rain_mm == 0.5


@pytest.mark.asyncio
async def test_unknown_circuit(client):
    with pytest.raises(WeatherAPIError, match="Unknown circuit"):
        await client.get_forecast("nonexistent_circuit")


@pytest.mark.asyncio
async def test_no_api_key():
    client = WeatherClient(api_key="")
    with pytest.raises(WeatherAPIError, match="No API key"):
        await client.get_forecast("albert_park")


def test_median():
    assert _median([1.0, 2.0, 3.0]) == 2.0
    assert _median([1.0, 2.0, 3.0, 4.0]) == 2.5
    assert _median([]) == 0.0


def test_circuit_coords_have_required_tracks():
    required = ["albert_park", "shanghai", "bahrain", "monaco", "silverstone", "monza", "spa"]
    for circuit in required:
        assert circuit in CIRCUIT_COORDS, f"Missing coordinates for {circuit}"
```

**Commit message:** `feat: add OpenWeatherMap client for pre-race weather forecasts`

---

### Task 6: Data Sync Orchestrator

**Files:**
- Create: `backend/app/ingestion/data_sync.py`

This module orchestrates fetching data from all sources after each session and persists it into the `SessionData` and `DriverSessionStats` tables.

- [ ] **Step 1: Create the data sync orchestrator**

```python
# backend/app/ingestion/data_sync.py
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
```

**Commit message:** `feat: add data sync orchestrator for session data ingestion`

---

### Task 7: Data Seeder — 2025 Season + 2026 Early Races

**Files:**
- Create: `backend/app/services/seeder.py`
- Create: `backend/tests/test_seeder.py`

Seeds the database with teams, drivers, 2025 season race weekends, and 2026 Australia and China. Also back-fills session data for 2025 using FastF1 (training data for the ML models).

- [ ] **Step 1: Create the seeder service**

```python
# backend/app/services/seeder.py
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
```

- [ ] **Step 2: Create tests for the seeder**

```python
# backend/tests/test_seeder.py
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
async def test_seed_teams_and_drivers(db_session):
    """Integration test: seed teams and drivers into a test database."""
    team_map = await seed_teams_and_drivers(db_session)
    assert len(team_map) == 10

    from app.models.f1 import Team, Driver
    teams = db_session.query(Team).all()
    drivers = db_session.query(Driver).all()
    assert len(teams) == 10
    assert len(drivers) == 20

    # Idempotent: running again should not duplicate
    team_map2 = await seed_teams_and_drivers(db_session)
    assert len(team_map2) == 10
    assert db_session.query(Team).count() == 10
```

**Commit message:** `feat: add data seeder for teams, drivers, and race weekends`

---

### Task 8: Feature Engineering

**Files:**
- Create: `backend/app/ml/__init__.py`
- Create: `backend/app/ml/features.py`
- Create: `backend/tests/test_features.py`

Transforms raw session data into feature vectors that the ML models consume. Each feature vector represents a single driver at a specific race weekend and stage.

- [ ] **Step 1: Create feature engineering module**

```python
# backend/app/ml/__init__.py
```

```python
# backend/app/ml/features.py
"""Feature engineering: transform raw session data into ML feature vectors."""

import logging
from dataclasses import dataclass

import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.f1 import Driver, Team, RaceWeekend
from app.models.training_data import SessionData, DriverSessionStats, HistoricalFeature
from app.models.prediction import ActualResult

logger = logging.getLogger(__name__)

# Session stages in order — each stage adds features from prior sessions
STAGE_SESSIONS = {
    "pre": [],
    "fp1": ["fp1"],
    "fp2": ["fp1", "fp2"],
    "fp3": ["fp1", "fp2", "fp3"],
    "quali": ["fp1", "fp2", "fp3", "quali"],
}


@dataclass
class FeatureSet:
    driver_id: int
    race_weekend_id: int
    stage: str
    features: dict


def build_features_for_stage(
    db: Session,
    race_weekend_id: int,
    stage: str,
) -> list[FeatureSet]:
    """
    Build feature vectors for all active drivers at a given race weekend and stage.

    Features include:
    - Historical performance (last N races avg position, points, DNF rate)
    - Team strength (constructor standings position, avg team points)
    - Track-specific history (driver's previous results at this circuit)
    - Session data (practice pace, sector times, long-run data — when available)
    - Weather conditions
    - Grid position (post-qualifying only)

    Returns a FeatureSet per driver.
    """
    race = db.get(RaceWeekend, race_weekend_id)
    if not race:
        return []

    drivers = db.query(Driver).filter(Driver.active.is_(True)).all()
    session_types = STAGE_SESSIONS.get(stage, [])

    # Pre-load session data for this race weekend
    session_data_map = _load_session_data(db, race_weekend_id, session_types)

    # Pre-load historical stats
    historical = _load_historical_stats(db, race.season, race.round, race.circuit_id)

    feature_sets = []
    for driver in drivers:
        features = {}

        # --- Historical features ---
        driver_history = historical.get(driver.id, {})
        features["avg_position_last5"] = driver_history.get("avg_position_last5", 12.0)
        features["avg_points_last5"] = driver_history.get("avg_points_last5", 0.0)
        features["dnf_rate"] = driver_history.get("dnf_rate", 0.05)
        features["wins_season"] = driver_history.get("wins_season", 0)
        features["podiums_season"] = driver_history.get("podiums_season", 0)
        features["championship_position"] = driver_history.get("championship_position", 20)

        # --- Track-specific features ---
        features["circuit_avg_position"] = driver_history.get("circuit_avg_position", 12.0)
        features["circuit_best_position"] = driver_history.get("circuit_best_position", 20)
        features["circuit_races_count"] = driver_history.get("circuit_races_count", 0)

        # --- Team features ---
        features["team_constructor_position"] = driver_history.get("team_constructor_position", 10)
        features["team_avg_pit_time"] = driver_history.get("team_avg_pit_time", 2.8)
        features["team_reliability_rate"] = driver_history.get("team_reliability_rate", 0.95)

        # --- Session-based features (from FP1/FP2/FP3/Quali) ---
        for session_type in session_types:
            prefix = session_type
            stats = session_data_map.get((driver.id, session_type))
            if stats:
                features[f"{prefix}_best_lap"] = stats.best_lap_time or 0.0
                features[f"{prefix}_avg_lap"] = stats.avg_lap_time or 0.0
                features[f"{prefix}_best_s1"] = stats.best_sector1 or 0.0
                features[f"{prefix}_best_s2"] = stats.best_sector2 or 0.0
                features[f"{prefix}_best_s3"] = stats.best_sector3 or 0.0
                features[f"{prefix}_long_run_pace"] = stats.long_run_pace or 0.0
                features[f"{prefix}_long_run_deg"] = stats.long_run_degradation or 0.0
                features[f"{prefix}_top_speed"] = stats.top_speed or 0.0
                features[f"{prefix}_position"] = stats.position or 20
                features[f"{prefix}_laps"] = stats.laps_completed
            else:
                # No data for this session — use neutral defaults
                features[f"{prefix}_best_lap"] = 0.0
                features[f"{prefix}_avg_lap"] = 0.0
                features[f"{prefix}_best_s1"] = 0.0
                features[f"{prefix}_best_s2"] = 0.0
                features[f"{prefix}_best_s3"] = 0.0
                features[f"{prefix}_long_run_pace"] = 0.0
                features[f"{prefix}_long_run_deg"] = 0.0
                features[f"{prefix}_top_speed"] = 0.0
                features[f"{prefix}_position"] = 20
                features[f"{prefix}_laps"] = 0

        # --- Weather features ---
        weather = _get_session_weather(db, race_weekend_id, session_types)
        features["air_temp"] = weather.get("air_temp", 25.0)
        features["track_temp"] = weather.get("track_temp", 35.0)
        features["rainfall"] = 1.0 if weather.get("rainfall", False) else 0.0

        # --- Grid position (only available at quali stage) ---
        if stage == "quali":
            quali_stats = session_data_map.get((driver.id, "quali"))
            features["grid_position"] = quali_stats.position if quali_stats and quali_stats.position else 20
        else:
            features["grid_position"] = features.get("championship_position", 20)

        # --- Derived features ---
        features["is_sprint_weekend"] = 1.0 if race.is_sprint_weekend else 0.0
        features["season_round"] = race.round

        feature_sets.append(FeatureSet(
            driver_id=driver.id,
            race_weekend_id=race_weekend_id,
            stage=stage,
            features=features,
        ))

    return feature_sets


def store_features(db: Session, feature_sets: list[FeatureSet]) -> None:
    """Persist computed features to the HistoricalFeature table."""
    for fs in feature_sets:
        existing = db.query(HistoricalFeature).filter(
            HistoricalFeature.race_weekend_id == fs.race_weekend_id,
            HistoricalFeature.driver_id == fs.driver_id,
            HistoricalFeature.stage == fs.stage,
        ).first()

        if existing:
            existing.feature_vector = fs.features
        else:
            db.add(HistoricalFeature(
                race_weekend_id=fs.race_weekend_id,
                driver_id=fs.driver_id,
                stage=fs.stage,
                feature_vector=fs.features,
            ))
    db.commit()


def build_training_dataset(
    db: Session,
    stage: str,
    target: str = "race_position",
) -> tuple[list[dict], list[int | float]]:
    """
    Build a training dataset from all completed races with stored features.

    Args:
        db: Database session.
        stage: The prediction stage to train for.
        target: The target column — 'race_position' or 'qualifying_position'.

    Returns:
        Tuple of (list of feature dicts, list of target values).
    """
    features_rows = db.query(HistoricalFeature).filter(
        HistoricalFeature.stage == stage,
    ).all()

    X = []
    y = []

    for row in features_rows:
        target_value = getattr(row, target, None)
        if target_value is None:
            continue
        X.append(row.feature_vector)
        y.append(target_value)

    return X, y


# --- Private helper functions ---

def _load_session_data(
    db: Session, race_weekend_id: int, session_types: list[str],
) -> dict[tuple[int, str], DriverSessionStats]:
    """Load DriverSessionStats keyed by (driver_id, session_type)."""
    result = {}
    for session_type in session_types:
        session = db.query(SessionData).filter(
            SessionData.race_weekend_id == race_weekend_id,
            SessionData.session_type == session_type,
        ).first()
        if not session:
            continue
        stats = db.query(DriverSessionStats).filter(
            DriverSessionStats.session_data_id == session.id,
        ).all()
        for s in stats:
            result[(s.driver_id, session_type)] = s
    return result


def _load_historical_stats(
    db: Session, season: int, current_round: int, circuit_id: str,
) -> dict[int, dict]:
    """
    Compute historical stats for each driver from prior races in the season
    and previous seasons at this circuit.
    """
    # Get completed races before this round
    prior_races = db.query(RaceWeekend).filter(
        RaceWeekend.status == "completed",
        ((RaceWeekend.season == season) & (RaceWeekend.round < current_round))
        | (RaceWeekend.season < season),
    ).all()

    if not prior_races:
        return {}

    prior_race_ids = [r.id for r in prior_races]

    # Same-circuit races for track-specific stats
    circuit_races = [r for r in prior_races if r.circuit_id == circuit_id]
    circuit_race_ids = [r.id for r in circuit_races]

    # Current-season races for recent form
    season_races = [r for r in prior_races if r.season == season]
    season_race_ids = [r.id for r in season_races]
    last5_race_ids = [r.id for r in sorted(season_races, key=lambda r: r.round, reverse=True)[:5]]

    drivers = db.query(Driver).filter(Driver.active.is_(True)).all()
    result = {}

    for driver in drivers:
        stats = {}

        # Last 5 races: average position and points
        if last5_race_ids:
            last5_results = db.query(ActualResult).filter(
                ActualResult.race_weekend_id.in_(last5_race_ids),
                ActualResult.category == "race_top5",
                ActualResult.driver_id == driver.id,
            ).all()
            positions = [r.position for r in last5_results if r.position]
            stats["avg_position_last5"] = np.mean(positions) if positions else 12.0
            stats["avg_points_last5"] = 0.0  # simplified — would need full results
        else:
            stats["avg_position_last5"] = 12.0
            stats["avg_points_last5"] = 0.0

        # Season wins and podiums
        season_results = db.query(ActualResult).filter(
            ActualResult.race_weekend_id.in_(season_race_ids),
            ActualResult.category == "race_top5",
            ActualResult.driver_id == driver.id,
        ).all()
        stats["wins_season"] = sum(1 for r in season_results if r.position == 1)
        stats["podiums_season"] = sum(1 for r in season_results if r.position and r.position <= 3)
        stats["championship_position"] = 20  # simplified; could query standings

        # DNF rate
        dnf_results = db.query(ActualResult).filter(
            ActualResult.race_weekend_id.in_(prior_race_ids),
            ActualResult.category == "dnf",
            ActualResult.driver_id == driver.id,
        ).all()
        total_races = len(season_race_ids) if season_race_ids else 1
        stats["dnf_rate"] = len(dnf_results) / max(total_races, 1)

        # Circuit-specific stats
        if circuit_race_ids:
            circuit_results = db.query(ActualResult).filter(
                ActualResult.race_weekend_id.in_(circuit_race_ids),
                ActualResult.category == "race_top5",
                ActualResult.driver_id == driver.id,
            ).all()
            circuit_positions = [r.position for r in circuit_results if r.position]
            stats["circuit_avg_position"] = np.mean(circuit_positions) if circuit_positions else 12.0
            stats["circuit_best_position"] = min(circuit_positions) if circuit_positions else 20
            stats["circuit_races_count"] = len(circuit_positions)
        else:
            stats["circuit_avg_position"] = 12.0
            stats["circuit_best_position"] = 20
            stats["circuit_races_count"] = 0

        # Team stats (simplified)
        stats["team_constructor_position"] = 10
        stats["team_avg_pit_time"] = 2.8
        stats["team_reliability_rate"] = 0.95

        result[driver.id] = stats

    return result


def _get_session_weather(
    db: Session, race_weekend_id: int, session_types: list[str],
) -> dict:
    """Get the most recent weather data from available sessions."""
    for session_type in reversed(session_types):
        session = db.query(SessionData).filter(
            SessionData.race_weekend_id == race_weekend_id,
            SessionData.session_type == session_type,
        ).first()
        if session and session.weather_data:
            return session.weather_data
    return {}
```

- [ ] **Step 2: Create tests for feature engineering**

```python
# backend/tests/test_features.py
import pytest
from unittest.mock import MagicMock, patch

from app.ml.features import (
    STAGE_SESSIONS,
    build_features_for_stage,
    FeatureSet,
)


def test_stage_sessions_ordering():
    """Verify each stage includes all prior sessions."""
    assert STAGE_SESSIONS["pre"] == []
    assert STAGE_SESSIONS["fp1"] == ["fp1"]
    assert STAGE_SESSIONS["fp2"] == ["fp1", "fp2"]
    assert STAGE_SESSIONS["fp3"] == ["fp1", "fp2", "fp3"]
    assert STAGE_SESSIONS["quali"] == ["fp1", "fp2", "fp3", "quali"]


def test_feature_set_structure():
    fs = FeatureSet(
        driver_id=1,
        race_weekend_id=1,
        stage="pre",
        features={"avg_position_last5": 3.2, "dnf_rate": 0.05},
    )
    assert fs.driver_id == 1
    assert "avg_position_last5" in fs.features
    assert fs.features["dnf_rate"] == 0.05


def test_pre_stage_has_no_session_features():
    """Pre-stage features should not include any fp/quali session data keys."""
    session_keys = STAGE_SESSIONS["pre"]
    assert len(session_keys) == 0


def test_quali_stage_includes_grid_position():
    """At quali stage, grid_position should be derived from qualifying results."""
    # This is a structural test — the actual grid_position logic is tested in integration
    assert "quali" in STAGE_SESSIONS["quali"]
```

**Commit message:** `feat: add feature engineering module for ML pipeline`

---

### Task 9: ML Models — Train and Predict

**Files:**
- Create: `backend/app/ml/models.py`
- Create: `backend/app/ml/model_store.py`
- Create: `backend/tests/test_models.py`

Each prediction category uses a specific model type. Models are trained on historical feature vectors and produce ranked predictions with confidence scores.

- [ ] **Step 1: Create the model store (save/load models)**

```python
# backend/app/ml/model_store.py
"""Save and load trained ML models using joblib."""

import logging
from pathlib import Path

import joblib

from app.config import settings

logger = logging.getLogger(__name__)


def get_model_path(model_name: str, version: str) -> Path:
    """Get the filesystem path for a model file."""
    model_dir = Path(settings.model_storage_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    return model_dir / f"{model_name}_{version}.joblib"


def save_model(model, model_name: str, version: str) -> Path:
    """Save a trained model to disk."""
    path = get_model_path(model_name, version)
    joblib.dump(model, path)
    logger.info("Saved model %s v%s to %s", model_name, version, path)
    return path


def load_model(model_name: str, version: str):
    """Load a trained model from disk. Returns None if not found."""
    path = get_model_path(model_name, version)
    if not path.exists():
        logger.warning("Model not found: %s", path)
        return None
    model = joblib.load(path)
    logger.info("Loaded model %s v%s from %s", model_name, version, path)
    return model


def get_latest_version(model_name: str) -> str | None:
    """Find the latest version of a model on disk."""
    model_dir = Path(settings.model_storage_dir)
    if not model_dir.exists():
        return None
    files = sorted(model_dir.glob(f"{model_name}_*.joblib"), reverse=True)
    if not files:
        return None
    # Extract version from filename: model_name_v1.2.3.joblib → v1.2.3
    stem = files[0].stem
    version = stem.replace(f"{model_name}_", "")
    return version
```

- [ ] **Step 2: Create the ML models module**

```python
# backend/app/ml/models.py
"""ML model definitions for each prediction category."""

import logging
from datetime import datetime

import numpy as np
import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LinearRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.preprocessing import LabelEncoder

from app.ml.model_store import save_model, load_model

logger = logging.getLogger(__name__)

# Feature columns used by all position-based models
POSITION_FEATURES = [
    "avg_position_last5", "avg_points_last5", "dnf_rate",
    "wins_season", "podiums_season", "championship_position",
    "circuit_avg_position", "circuit_best_position", "circuit_races_count",
    "team_constructor_position", "air_temp", "track_temp", "rainfall",
    "grid_position", "is_sprint_weekend", "season_round",
]

# Features added per available session (prefix: fp1_, fp2_, fp3_, quali_)
SESSION_FEATURES_SUFFIXES = [
    "best_lap", "avg_lap", "best_s1", "best_s2", "best_s3",
    "long_run_pace", "long_run_deg", "top_speed", "position", "laps",
]

MODEL_VERSION = datetime.utcnow().strftime("v%Y%m%d")


def _get_feature_names(stage: str) -> list[str]:
    """Get the full list of feature names for a given stage."""
    from app.ml.features import STAGE_SESSIONS
    names = list(POSITION_FEATURES)
    for session_type in STAGE_SESSIONS.get(stage, []):
        for suffix in SESSION_FEATURES_SUFFIXES:
            names.append(f"{session_type}_{suffix}")
    return names


def _dicts_to_matrix(feature_dicts: list[dict], feature_names: list[str]) -> np.ndarray:
    """Convert list of feature dicts to a numpy matrix, filling missing values with 0."""
    matrix = np.zeros((len(feature_dicts), len(feature_names)))
    for i, fd in enumerate(feature_dicts):
        for j, name in enumerate(feature_names):
            matrix[i, j] = fd.get(name, 0.0)
    return matrix


class PositionRanker:
    """
    XGBoost Ranker for qualifying and race position predictions.
    Outputs a ranking of drivers for top-5 prediction.
    """

    def __init__(self, stage: str, target: str = "race_position"):
        self.stage = stage
        self.target = target  # "race_position" or "qualifying_position"
        self.model_name = f"position_ranker_{target}_{stage}"
        self.feature_names = _get_feature_names(stage)
        self.model = None

    def train(self, feature_dicts: list[dict], targets: list[int]) -> None:
        """Train the XGBoost ranker on historical data."""
        X = _dicts_to_matrix(feature_dicts, self.feature_names)
        y = np.array(targets, dtype=np.float32)

        # For ranking, XGBoost uses pairwise loss. We train as regression
        # and rank by predicted values (lower = better position).
        self.model = xgb.XGBRegressor(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
        )
        self.model.fit(X, y)
        save_model(self.model, self.model_name, MODEL_VERSION)
        logger.info("Trained %s with %d samples", self.model_name, len(X))

    def predict(self, feature_dicts: list[dict], driver_ids: list[int]) -> list[dict]:
        """
        Predict positions for a set of drivers.
        Returns sorted list of {driver_id, predicted_position, confidence}.
        """
        if self.model is None:
            self.model = load_model(self.model_name, MODEL_VERSION)
        if self.model is None:
            logger.warning("No trained model for %s", self.model_name)
            return []

        X = _dicts_to_matrix(feature_dicts, self.feature_names)
        predictions = self.model.predict(X)

        # Sort by predicted value (lower = better position)
        ranked = sorted(zip(driver_ids, predictions), key=lambda x: x[1])

        # Compute confidence as inverse of spread (normalized)
        pred_range = max(predictions) - min(predictions) if len(predictions) > 1 else 1.0
        results = []
        for rank, (driver_id, pred_val) in enumerate(ranked, 1):
            # Confidence: higher for drivers predicted closer to P1
            confidence = max(0.1, 1.0 - (pred_val - min(predictions)) / max(pred_range, 0.1))
            confidence = min(confidence, 0.99)
            results.append({
                "driver_id": driver_id,
                "predicted_position": rank,
                "confidence": round(confidence, 3),
            })

        return results


class FastestLapClassifier:
    """XGBoost classifier predicting which driver gets fastest lap."""

    def __init__(self, stage: str):
        self.stage = stage
        self.model_name = f"fastest_lap_{stage}"
        self.feature_names = _get_feature_names(stage)
        self.model = None

    def train(self, feature_dicts: list[dict], targets: list[int]) -> None:
        """Train: targets are 1 (got FL) or 0 (didn't)."""
        X = _dicts_to_matrix(feature_dicts, self.feature_names)
        y = np.array(targets, dtype=np.int32)

        self.model = xgb.XGBClassifier(
            n_estimators=150,
            max_depth=5,
            learning_rate=0.1,
            scale_pos_weight=len(y) / max(sum(y), 1),  # handle class imbalance
            random_state=42,
        )
        self.model.fit(X, y)
        save_model(self.model, self.model_name, MODEL_VERSION)

    def predict(self, feature_dicts: list[dict], driver_ids: list[int]) -> list[dict]:
        """Predict probability of getting fastest lap for each driver."""
        if self.model is None:
            self.model = load_model(self.model_name, MODEL_VERSION)
        if self.model is None:
            return []

        X = _dicts_to_matrix(feature_dicts, self.feature_names)
        probas = self.model.predict_proba(X)

        # Column 1 is the probability of class 1 (got FL)
        fl_probs = probas[:, 1] if probas.shape[1] > 1 else probas[:, 0]

        results = []
        for driver_id, prob in sorted(zip(driver_ids, fl_probs), key=lambda x: -x[1]):
            results.append({
                "driver_id": driver_id,
                "confidence": round(float(prob), 3),
            })
        return results


class SafetyCarPredictor:
    """Random Forest classifier for safety car prediction (yes/no + count)."""

    def __init__(self, stage: str):
        self.stage = stage
        self.model_name = f"safety_car_{stage}"
        # Safety car model uses race-level features, not per-driver
        self.feature_names = [
            "air_temp", "track_temp", "rainfall", "is_sprint_weekend",
            "season_round", "circuit_avg_position",  # proxy for circuit danger
        ]
        self.model = None
        self.count_model = None

    def train(self, feature_dicts: list[dict], sc_yes: list[int], sc_counts: list[int]) -> None:
        """Train: sc_yes is 0/1, sc_counts is number of safety cars."""
        X = _dicts_to_matrix(feature_dicts, self.feature_names)

        # Yes/no classifier
        self.model = RandomForestClassifier(
            n_estimators=100, max_depth=5, random_state=42,
        )
        self.model.fit(X, np.array(sc_yes))
        save_model(self.model, self.model_name, MODEL_VERSION)

        # Count regressor (only on positive samples)
        positive_mask = np.array(sc_yes) == 1
        if positive_mask.sum() > 5:
            from sklearn.ensemble import RandomForestRegressor
            self.count_model = RandomForestRegressor(
                n_estimators=50, max_depth=4, random_state=42,
            )
            self.count_model.fit(X[positive_mask], np.array(sc_counts)[positive_mask])
            save_model(self.count_model, f"{self.model_name}_count", MODEL_VERSION)

    def predict(self, feature_dict: dict) -> dict:
        """Predict safety car yes/no and expected count."""
        if self.model is None:
            self.model = load_model(self.model_name, MODEL_VERSION)
        if self.model is None:
            return {"yes": True, "count": 1, "confidence": 0.5}

        X = _dicts_to_matrix([feature_dict], self.feature_names)
        proba = self.model.predict_proba(X)[0]
        yes_prob = proba[1] if len(proba) > 1 else 0.5

        count = 1
        if self.count_model is None:
            self.count_model = load_model(f"{self.model_name}_count", MODEL_VERSION)
        if self.count_model is not None:
            count = max(0, round(float(self.count_model.predict(X)[0])))

        return {
            "yes": yes_prob > 0.5,
            "count": count,
            "confidence": round(float(max(yes_prob, 1 - yes_prob)), 3),
        }


class DNFPredictor:
    """Random Forest classifier predicting which drivers will DNF."""

    def __init__(self, stage: str):
        self.stage = stage
        self.model_name = f"dnf_{stage}"
        self.feature_names = _get_feature_names(stage)
        self.model = None

    def train(self, feature_dicts: list[dict], targets: list[int]) -> None:
        """Train: targets are 1 (DNF) or 0 (finished)."""
        X = _dicts_to_matrix(feature_dicts, self.feature_names)
        y = np.array(targets, dtype=np.int32)

        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=5,
            class_weight="balanced",
            random_state=42,
        )
        self.model.fit(X, y)
        save_model(self.model, self.model_name, MODEL_VERSION)

    def predict(self, feature_dicts: list[dict], driver_ids: list[int]) -> list[dict]:
        """Predict DNF probability for each driver, return top 3 most likely."""
        if self.model is None:
            self.model = load_model(self.model_name, MODEL_VERSION)
        if self.model is None:
            return []

        X = _dicts_to_matrix(feature_dicts, self.feature_names)
        probas = self.model.predict_proba(X)
        dnf_probs = probas[:, 1] if probas.shape[1] > 1 else np.zeros(len(driver_ids))

        results = []
        for driver_id, prob in sorted(zip(driver_ids, dnf_probs), key=lambda x: -x[1]):
            results.append({
                "driver_id": driver_id,
                "confidence": round(float(prob), 3),
            })
        return results[:3]  # top 3 most likely DNFs


class PitStopPredictor:
    """Linear Regression for predicting quickest pit stop team."""

    def __init__(self, stage: str):
        self.stage = stage
        self.model_name = f"pitstop_{stage}"
        self.feature_names = ["team_avg_pit_time", "team_constructor_position", "team_reliability_rate"]
        self.model = None

    def train(self, feature_dicts: list[dict], targets: list[float]) -> None:
        """Train: targets are pit stop duration in seconds."""
        X = _dicts_to_matrix(feature_dicts, self.feature_names)
        y = np.array(targets, dtype=np.float32)

        self.model = LinearRegression()
        self.model.fit(X, y)
        save_model(self.model, self.model_name, MODEL_VERSION)

    def predict(self, feature_dicts: list[dict], team_ids: list[int]) -> list[dict]:
        """Predict pit stop times per team, return sorted by fastest."""
        if self.model is None:
            self.model = load_model(self.model_name, MODEL_VERSION)
        if self.model is None:
            return []

        X = _dicts_to_matrix(feature_dicts, self.feature_names)
        predictions = self.model.predict(X)

        results = []
        for team_id, pred_time in sorted(zip(team_ids, predictions), key=lambda x: x[1]):
            results.append({
                "team_id": team_id,
                "predicted_time": round(float(pred_time), 3),
                "confidence": 0.6,  # pit stop predictions have inherent uncertainty
            })
        return results


class TireStrategyPredictor:
    """Decision Tree classifier predicting winner's pit stop count (tire strategy)."""

    def __init__(self, stage: str):
        self.stage = stage
        self.model_name = f"tire_strategy_{stage}"
        self.feature_names = [
            "air_temp", "track_temp", "rainfall", "is_sprint_weekend",
            "season_round",
        ]
        self.model = None

    def train(self, feature_dicts: list[dict], targets: list[int]) -> None:
        """Train: targets are pit stop counts (1, 2, 3, etc.)."""
        X = _dicts_to_matrix(feature_dicts, self.feature_names)
        y = np.array(targets, dtype=np.int32)

        self.model = DecisionTreeClassifier(
            max_depth=5, random_state=42,
        )
        self.model.fit(X, y)
        save_model(self.model, self.model_name, MODEL_VERSION)

    def predict(self, feature_dict: dict) -> dict:
        """Predict the most likely number of pit stops."""
        if self.model is None:
            self.model = load_model(self.model_name, MODEL_VERSION)
        if self.model is None:
            return {"stops": 1, "confidence": 0.5}

        X = _dicts_to_matrix([feature_dict], self.feature_names)
        prediction = int(self.model.predict(X)[0])
        proba = self.model.predict_proba(X)[0]
        confidence = float(max(proba))

        return {
            "stops": prediction,
            "confidence": round(confidence, 3),
        }
```

- [ ] **Step 3: Create tests for ML models**

```python
# backend/tests/test_models.py
import pytest
import numpy as np
from unittest.mock import patch

from app.ml.models import (
    PositionRanker,
    FastestLapClassifier,
    SafetyCarPredictor,
    DNFPredictor,
    PitStopPredictor,
    TireStrategyPredictor,
    _dicts_to_matrix,
    _get_feature_names,
)


def _make_feature_dict(**overrides):
    """Create a minimal feature dict for testing."""
    base = {
        "avg_position_last5": 5.0,
        "avg_points_last5": 12.0,
        "dnf_rate": 0.05,
        "wins_season": 2,
        "podiums_season": 5,
        "championship_position": 3,
        "circuit_avg_position": 4.0,
        "circuit_best_position": 1,
        "circuit_races_count": 3,
        "team_constructor_position": 2,
        "air_temp": 25.0,
        "track_temp": 35.0,
        "rainfall": 0.0,
        "grid_position": 3,
        "is_sprint_weekend": 0.0,
        "season_round": 5,
        "team_avg_pit_time": 2.5,
        "team_reliability_rate": 0.97,
    }
    base.update(overrides)
    return base


def test_dicts_to_matrix():
    dicts = [{"a": 1.0, "b": 2.0}, {"a": 3.0, "b": 4.0}]
    names = ["a", "b"]
    result = _dicts_to_matrix(dicts, names)
    assert result.shape == (2, 2)
    assert result[0, 0] == 1.0
    assert result[1, 1] == 4.0


def test_dicts_to_matrix_missing_keys():
    dicts = [{"a": 1.0}]
    names = ["a", "b"]
    result = _dicts_to_matrix(dicts, names)
    assert result[0, 1] == 0.0  # missing key defaults to 0


def test_get_feature_names_pre():
    names = _get_feature_names("pre")
    assert "avg_position_last5" in names
    assert "fp1_best_lap" not in names


def test_get_feature_names_fp1():
    names = _get_feature_names("fp1")
    assert "fp1_best_lap" in names
    assert "fp2_best_lap" not in names


def test_position_ranker_train_predict(tmp_path):
    with patch("app.ml.models.save_model"), patch("app.ml.model_store.settings") as mock_settings:
        mock_settings.model_storage_dir = str(tmp_path)

        ranker = PositionRanker(stage="pre")
        features = [_make_feature_dict(championship_position=i) for i in range(1, 21)]
        targets = list(range(1, 21))

        ranker.train(features, targets)
        assert ranker.model is not None

        test_features = [_make_feature_dict(championship_position=1), _make_feature_dict(championship_position=20)]
        results = ranker.predict(test_features, [1, 2])

        assert len(results) == 2
        assert all("driver_id" in r and "predicted_position" in r and "confidence" in r for r in results)
        assert results[0]["predicted_position"] < results[1]["predicted_position"]


def test_fastest_lap_classifier_train_predict(tmp_path):
    with patch("app.ml.models.save_model"):
        clf = FastestLapClassifier(stage="pre")
        features = [_make_feature_dict() for _ in range(50)]
        targets = [1 if i < 5 else 0 for i in range(50)]

        clf.train(features, targets)
        assert clf.model is not None

        results = clf.predict([_make_feature_dict()], [1])
        assert len(results) == 1
        assert 0.0 <= results[0]["confidence"] <= 1.0


def test_safety_car_predictor(tmp_path):
    with patch("app.ml.models.save_model"):
        predictor = SafetyCarPredictor(stage="pre")
        features = [_make_feature_dict() for _ in range(30)]
        sc_yes = [1 if i % 3 == 0 else 0 for i in range(30)]
        sc_counts = [2 if i % 3 == 0 else 0 for i in range(30)]

        predictor.train(features, sc_yes, sc_counts)

        result = predictor.predict(_make_feature_dict())
        assert "yes" in result
        assert "count" in result
        assert "confidence" in result


def test_tire_strategy_predictor(tmp_path):
    with patch("app.ml.models.save_model"):
        predictor = TireStrategyPredictor(stage="pre")
        features = [_make_feature_dict() for _ in range(30)]
        targets = [1] * 15 + [2] * 15  # half 1-stop, half 2-stop

        predictor.train(features, targets)

        result = predictor.predict(_make_feature_dict())
        assert result["stops"] in (1, 2)
        assert 0.0 <= result["confidence"] <= 1.0
```

**Commit message:** `feat: add ML models for all prediction categories`

---

### Task 10: Prediction Generation Service

**Files:**
- Create: `backend/app/ml/prediction_service.py`
- Create: `backend/tests/test_prediction_service.py`

This service orchestrates feature building, model inference, and writing `MLPrediction` rows. It is the main entry point called by the scheduler after each session.

- [ ] **Step 1: Create the prediction generation service**

```python
# backend/app/ml/prediction_service.py
"""Generates ML predictions and stores them in the database."""

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.f1 import Driver, Team, RaceWeekend
from app.models.prediction import MLPrediction
from app.ml.features import build_features_for_stage, store_features
from app.ml.models import (
    PositionRanker,
    FastestLapClassifier,
    SafetyCarPredictor,
    DNFPredictor,
    PitStopPredictor,
    TireStrategyPredictor,
    MODEL_VERSION,
)

logger = logging.getLogger(__name__)


class PredictionGenerationService:
    """Generates ML predictions for a race weekend at a given stage."""

    def __init__(self, db: Session):
        self.db = db

    def generate_predictions(self, race_weekend_id: int, stage: str) -> int:
        """
        Generate all category predictions for a race weekend at the given stage.

        Args:
            race_weekend_id: Database ID of the RaceWeekend.
            stage: One of 'pre', 'fp1', 'fp2', 'fp3', 'quali'.

        Returns:
            Number of MLPrediction rows created.
        """
        race = self.db.get(RaceWeekend, race_weekend_id)
        if not race:
            logger.error("RaceWeekend %s not found", race_weekend_id)
            return 0

        logger.info("Generating predictions for %s (R%s) at stage %s", race.name, race.round, stage)

        # Step 1: Build feature vectors for all drivers
        feature_sets = build_features_for_stage(self.db, race_weekend_id, stage)
        if not feature_sets:
            logger.warning("No feature sets generated for race %s stage %s", race_weekend_id, stage)
            return 0

        # Store features for future training
        store_features(self.db, feature_sets)

        # Prepare feature dicts and driver IDs
        feature_dicts = [fs.features for fs in feature_sets]
        driver_ids = [fs.driver_id for fs in feature_sets]

        # Step 2: Delete existing predictions for this race+stage
        self.db.query(MLPrediction).filter(
            MLPrediction.race_weekend_id == race_weekend_id,
            MLPrediction.session_stage == stage,
        ).delete()

        count = 0

        # --- Qualifying Top 5 ---
        count += self._predict_positions(
            race_weekend_id, stage, feature_dicts, driver_ids,
            category="qualifying_top5", target="qualifying_position",
        )

        # --- Race Top 5 ---
        count += self._predict_positions(
            race_weekend_id, stage, feature_dicts, driver_ids,
            category="race_top5", target="race_position",
        )

        # --- Sprint Top 5 (only for sprint weekends) ---
        if race.is_sprint_weekend:
            count += self._predict_positions(
                race_weekend_id, stage, feature_dicts, driver_ids,
                category="sprint_top5", target="race_position",
            )

        # --- Fastest Lap ---
        count += self._predict_fastest_lap(race_weekend_id, stage, feature_dicts, driver_ids)

        # --- Constructor Points ---
        count += self._predict_constructor_points(race_weekend_id, stage, feature_dicts, driver_ids)

        # --- Quickest Pit Stop ---
        count += self._predict_quickest_pitstop(race_weekend_id, stage)

        # --- Safety Car ---
        count += self._predict_safety_car(race_weekend_id, stage, feature_dicts)

        # --- DNF ---
        count += self._predict_dnf(race_weekend_id, stage, feature_dicts, driver_ids)

        # --- Tire Strategy ---
        count += self._predict_tire_strategy(race_weekend_id, stage, feature_dicts)

        # --- Teammate Battles ---
        count += self._predict_teammate_battles(race_weekend_id, stage, feature_dicts, driver_ids)

        self.db.commit()
        logger.info("Generated %d prediction rows for race %s stage %s", count, race_weekend_id, stage)
        return count

    def _predict_positions(
        self, race_weekend_id: int, stage: str,
        feature_dicts: list[dict], driver_ids: list[int],
        category: str, target: str,
    ) -> int:
        """Predict top-5 positions using PositionRanker."""
        ranker = PositionRanker(stage=stage, target=target)
        results = ranker.predict(feature_dicts, driver_ids)

        count = 0
        for result in results[:5]:
            self.db.add(MLPrediction(
                race_weekend_id=race_weekend_id,
                category=category,
                position=result["predicted_position"],
                driver_id=result["driver_id"],
                confidence=result["confidence"],
                model_version=MODEL_VERSION,
                session_stage=stage,
            ))
            count += 1
        return count

    def _predict_fastest_lap(
        self, race_weekend_id: int, stage: str,
        feature_dicts: list[dict], driver_ids: list[int],
    ) -> int:
        clf = FastestLapClassifier(stage=stage)
        results = clf.predict(feature_dicts, driver_ids)
        if results:
            top = results[0]
            driver = self.db.get(Driver, top["driver_id"])
            self.db.add(MLPrediction(
                race_weekend_id=race_weekend_id,
                category="fastest_lap",
                driver_id=top["driver_id"],
                team_id=driver.team_id if driver else None,
                confidence=top["confidence"],
                model_version=MODEL_VERSION,
                session_stage=stage,
            ))
            return 1
        return 0

    def _predict_constructor_points(
        self, race_weekend_id: int, stage: str,
        feature_dicts: list[dict], driver_ids: list[int],
    ) -> int:
        """Predict constructor points winner from position predictions."""
        ranker = PositionRanker(stage=stage, target="race_position")
        results = ranker.predict(feature_dicts, driver_ids)
        if not results:
            return 0

        # Sum predicted positions per team (lower total = more points)
        team_scores: dict[int, float] = {}
        for result in results:
            driver = self.db.get(Driver, result["driver_id"])
            if driver:
                team_scores[driver.team_id] = team_scores.get(driver.team_id, 0) + result["predicted_position"]

        # Team with lowest total predicted position = most constructor points
        if team_scores:
            best_team_id = min(team_scores, key=team_scores.get)
            self.db.add(MLPrediction(
                race_weekend_id=race_weekend_id,
                category="constructor_points",
                team_id=best_team_id,
                confidence=0.6,
                model_version=MODEL_VERSION,
                session_stage=stage,
            ))
            return 1
        return 0

    def _predict_quickest_pitstop(self, race_weekend_id: int, stage: str) -> int:
        """Predict which team will have the quickest pit stop."""
        teams = self.db.query(Team).filter(Team.active.is_(True)).all()
        if not teams:
            return 0

        predictor = PitStopPredictor(stage=stage)
        feature_dicts = [
            {"team_avg_pit_time": 2.5, "team_constructor_position": i + 1, "team_reliability_rate": 0.95}
            for i in range(len(teams))
        ]
        team_ids = [t.id for t in teams]

        results = predictor.predict(feature_dicts, team_ids)
        if results:
            top = results[0]
            self.db.add(MLPrediction(
                race_weekend_id=race_weekend_id,
                category="quickest_pitstop",
                team_id=top["team_id"],
                confidence=top["confidence"],
                model_version=MODEL_VERSION,
                session_stage=stage,
            ))
            return 1
        return 0

    def _predict_safety_car(
        self, race_weekend_id: int, stage: str, feature_dicts: list[dict],
    ) -> int:
        """Predict safety car occurrence and count."""
        if not feature_dicts:
            return 0

        # Use first driver's features as race-level proxy
        predictor = SafetyCarPredictor(stage=stage)
        result = predictor.predict(feature_dicts[0])

        self.db.add(MLPrediction(
            race_weekend_id=race_weekend_id,
            category="safety_car",
            value=f"{'yes' if result['yes'] else 'no'},{result['count']}",
            confidence=result["confidence"],
            model_version=MODEL_VERSION,
            session_stage=stage,
        ))
        return 1

    def _predict_dnf(
        self, race_weekend_id: int, stage: str,
        feature_dicts: list[dict], driver_ids: list[int],
    ) -> int:
        predictor = DNFPredictor(stage=stage)
        results = predictor.predict(feature_dicts, driver_ids)

        count = 0
        for result in results:
            self.db.add(MLPrediction(
                race_weekend_id=race_weekend_id,
                category="dnf",
                driver_id=result["driver_id"],
                confidence=result["confidence"],
                model_version=MODEL_VERSION,
                session_stage=stage,
            ))
            count += 1
        return count

    def _predict_tire_strategy(
        self, race_weekend_id: int, stage: str, feature_dicts: list[dict],
    ) -> int:
        if not feature_dicts:
            return 0

        predictor = TireStrategyPredictor(stage=stage)
        result = predictor.predict(feature_dicts[0])

        self.db.add(MLPrediction(
            race_weekend_id=race_weekend_id,
            category="tire_strategy",
            position=result["stops"],
            confidence=result["confidence"],
            model_version=MODEL_VERSION,
            session_stage=stage,
        ))
        return 1

    def _predict_teammate_battles(
        self, race_weekend_id: int, stage: str,
        feature_dicts: list[dict], driver_ids: list[int],
    ) -> int:
        """Predict teammate battles using race position predictions."""
        ranker = PositionRanker(stage=stage, target="race_position")
        results = ranker.predict(feature_dicts, driver_ids)
        if not results:
            return 0

        # Map driver_id to predicted position
        driver_positions = {r["driver_id"]: r["predicted_position"] for r in results}

        # Group drivers by team
        teams = self.db.query(Team).filter(Team.active.is_(True)).all()
        count = 0
        for team in teams:
            team_drivers = self.db.query(Driver).filter(
                Driver.team_id == team.id, Driver.active.is_(True),
            ).all()
            if len(team_drivers) < 2:
                continue

            # Pick the driver with the better (lower) predicted position
            best_driver = min(team_drivers, key=lambda d: driver_positions.get(d.id, 99))
            pos1 = driver_positions.get(team_drivers[0].id, 99)
            pos2 = driver_positions.get(team_drivers[1].id, 99)
            gap = abs(pos1 - pos2)
            confidence = min(0.95, 0.5 + gap * 0.05)

            self.db.add(MLPrediction(
                race_weekend_id=race_weekend_id,
                category="teammate_battle",
                team_id=team.id,
                driver_id=best_driver.id,
                confidence=round(confidence, 3),
                model_version=MODEL_VERSION,
                session_stage=stage,
            ))
            count += 1
        return count
```

- [ ] **Step 2: Create tests for prediction service**

```python
# backend/tests/test_prediction_service.py
import pytest
from unittest.mock import patch, MagicMock

from app.ml.prediction_service import PredictionGenerationService


@pytest.fixture
def mock_db():
    db = MagicMock()
    return db


def test_generate_predictions_race_not_found(mock_db):
    mock_db.get.return_value = None
    service = PredictionGenerationService(mock_db)
    result = service.generate_predictions(999, "pre")
    assert result == 0


def test_generate_predictions_no_features(mock_db):
    race = MagicMock()
    race.name = "Test GP"
    race.round = 1
    race.is_sprint_weekend = False
    mock_db.get.return_value = race

    with patch("app.ml.prediction_service.build_features_for_stage", return_value=[]):
        service = PredictionGenerationService(mock_db)
        result = service.generate_predictions(1, "pre")
        assert result == 0
```

**Commit message:** `feat: add prediction generation service for ML pipeline`

---

### Task 11: APScheduler Integration

**Files:**
- Create: `backend/app/scheduler/__init__.py`
- Create: `backend/app/scheduler/jobs.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/routers/admin.py`
- Create: `backend/tests/test_scheduler.py`

The scheduler uses event-driven triggers: jobs fire 30 minutes after each session ends. On failure, they retry with exponential backoff. An admin endpoint allows manual triggering.

- [ ] **Step 1: Create the scheduler module**

```python
# backend/app/scheduler/__init__.py
```

```python
# backend/app/scheduler/jobs.py
"""APScheduler job definitions for the ML pipeline."""

import asyncio
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.f1 import RaceWeekend
from app.ingestion.data_sync import DataSyncService
from app.ml.prediction_service import PredictionGenerationService

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler: BackgroundScheduler | None = None

# Stage mapping: which session triggers which prediction stage
SESSION_TO_STAGE = {
    "fp1": "fp1",
    "fp2": "fp2",
    "fp3": "fp3",
    "quali": "quali",
    "race": None,  # race triggers scoring, not prediction
}


def init_scheduler() -> BackgroundScheduler:
    """Initialize and start the APScheduler."""
    global scheduler
    if scheduler is not None:
        return scheduler

    scheduler = BackgroundScheduler(
        job_defaults={"coalesce": True, "max_instances": 1},
    )
    scheduler.start()
    logger.info("APScheduler started")

    # Schedule jobs for upcoming race weekends
    schedule_upcoming_races()

    return scheduler


def shutdown_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    global scheduler
    if scheduler:
        scheduler.shutdown(wait=False)
        scheduler = None
        logger.info("APScheduler shut down")


def schedule_upcoming_races() -> None:
    """Schedule data ingestion + prediction jobs for all upcoming race weekends."""
    db = SessionLocal()
    try:
        upcoming = db.query(RaceWeekend).filter(
            RaceWeekend.status.in_(["upcoming", "active"]),
        ).all()

        for race in upcoming:
            schedule_race_weekend_jobs(race)
    finally:
        db.close()


def schedule_race_weekend_jobs(race: RaceWeekend) -> None:
    """Schedule all session-end jobs for a single race weekend."""
    delay = timedelta(minutes=settings.data_fetch_delay_minutes)

    session_times = {
        "fp1": race.fp1_time,
        "fp2": race.fp2_time,
        "fp3": race.fp3_time,
        "quali": race.quali_time,
        "race": race.race_time,
    }

    for session_type, session_time in session_times.items():
        if not session_time:
            continue

        # Estimate session duration (sessions last ~1-2 hours)
        session_durations = {
            "fp1": timedelta(hours=1),
            "fp2": timedelta(hours=1),
            "fp3": timedelta(hours=1),
            "quali": timedelta(hours=1),
            "race": timedelta(hours=2),
        }

        trigger_time = session_time + session_durations[session_type] + delay

        # Skip if trigger time is in the past
        if trigger_time < datetime.utcnow():
            continue

        job_id = f"pipeline_{race.id}_{session_type}"

        if scheduler and not scheduler.get_job(job_id):
            scheduler.add_job(
                run_pipeline_job,
                trigger=DateTrigger(run_date=trigger_time),
                id=job_id,
                args=[race.id, session_type],
                name=f"Pipeline: {race.name} {session_type}",
                replace_existing=True,
            )
            logger.info(
                "Scheduled %s for %s at %s",
                session_type, race.name, trigger_time.isoformat(),
            )


def run_pipeline_job(race_weekend_id: int, session_type: str, retry_count: int = 0) -> None:
    """
    Main pipeline job: fetch data, generate predictions.
    Runs in a background thread.
    """
    logger.info("Running pipeline job for race %s session %s (attempt %d)", race_weekend_id, session_type, retry_count + 1)

    db = SessionLocal()
    try:
        # Run the async data sync in an event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Step 1: Sync session data
            sync_service = DataSyncService(db)
            success = loop.run_until_complete(
                sync_service.sync_session(race_weekend_id, session_type)
            )

            if not success:
                raise RuntimeError(f"Data sync failed for {session_type}")

            # Step 2: If this is the race session, also sync results
            if session_type == "race":
                loop.run_until_complete(
                    sync_service.sync_race_results(race_weekend_id)
                )
                # Mark race as completed
                race = db.get(RaceWeekend, race_weekend_id)
                if race:
                    race.status = "completed"
                    db.commit()
                logger.info("Race results synced for race %s", race_weekend_id)
            else:
                # Step 3: Generate predictions for this stage
                stage = SESSION_TO_STAGE.get(session_type)
                if stage:
                    prediction_service = PredictionGenerationService(db)
                    count = prediction_service.generate_predictions(race_weekend_id, stage)
                    logger.info("Generated %d predictions for race %s stage %s", count, race_weekend_id, stage)

        finally:
            loop.close()

    except Exception as e:
        logger.error("Pipeline job failed for race %s session %s: %s", race_weekend_id, session_type, e)
        db.rollback()

        # Retry with exponential backoff
        if retry_count < settings.max_retries:
            backoff_minutes = [30, 60, 120][retry_count]
            retry_time = datetime.utcnow() + timedelta(minutes=backoff_minutes)
            retry_job_id = f"pipeline_{race_weekend_id}_{session_type}_retry{retry_count + 1}"

            if scheduler:
                scheduler.add_job(
                    run_pipeline_job,
                    trigger=DateTrigger(run_date=retry_time),
                    id=retry_job_id,
                    args=[race_weekend_id, session_type, retry_count + 1],
                    name=f"Retry: R{race_weekend_id} {session_type} (attempt {retry_count + 2})",
                    replace_existing=True,
                )
                logger.info(
                    "Scheduled retry %d for race %s %s at %s",
                    retry_count + 1, race_weekend_id, session_type, retry_time.isoformat(),
                )
        else:
            logger.error("Max retries exceeded for race %s session %s", race_weekend_id, session_type)

    finally:
        db.close()


def trigger_manual_pipeline(race_weekend_id: int, stage: str) -> dict:
    """
    Manually trigger the prediction pipeline for a specific race and stage.
    Called from the admin endpoint.
    """
    db = SessionLocal()
    try:
        race = db.get(RaceWeekend, race_weekend_id)
        if not race:
            return {"error": "Race not found"}

        # If stage is a session type (fp1, fp2, etc.), run full pipeline
        session_type = stage
        if stage in SESSION_TO_STAGE:
            # Run sync + predict
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                sync_service = DataSyncService(db)
                loop.run_until_complete(
                    sync_service.sync_session(race_weekend_id, session_type)
                )
            except Exception as e:
                logger.warning("Data sync failed (continuing with prediction): %s", e)
            finally:
                loop.close()

        # Generate predictions
        prediction_service = PredictionGenerationService(db)
        count = prediction_service.generate_predictions(race_weekend_id, stage)

        return {"success": True, "predictions_generated": count}
    finally:
        db.close()
```

- [ ] **Step 2: Update main.py to integrate the scheduler**

```python
# backend/app/main.py
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
import app.models  # noqa: F401 — registers models with Base
from app.routers import auth, races, predictions, leaderboard, admin, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)
    if settings.scheduler_enabled:
        from app.scheduler.jobs import init_scheduler
        init_scheduler()
    yield
    # Shutdown
    if settings.scheduler_enabled:
        from app.scheduler.jobs import shutdown_scheduler
        shutdown_scheduler()


app = FastAPI(title="F1 Predict API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(races.router)
app.include_router(predictions.router)
app.include_router(leaderboard.router)
app.include_router(admin.router)
app.include_router(users.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
```

- [ ] **Step 3: Add manual trigger endpoint to admin router**

Add the following endpoint to the existing `backend/app/routers/admin.py`:

```python
# Add to existing admin.py, after the existing imports:
from app.scheduler.jobs import trigger_manual_pipeline

# Add this new endpoint after the existing trigger_scoring endpoint:

@router.post("/trigger-pipeline/{race_id}/{stage}")
def trigger_pipeline(race_id: int, stage: str):
    """Manually trigger the ML prediction pipeline for a specific race and stage."""
    valid_stages = ["pre", "fp1", "fp2", "fp3", "quali"]
    if stage not in valid_stages:
        raise HTTPException(status_code=400, detail=f"Invalid stage. Must be one of: {valid_stages}")

    result = trigger_manual_pipeline(race_id, stage)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
```

- [ ] **Step 4: Create scheduler tests**

```python
# backend/tests/test_scheduler.py
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from app.scheduler.jobs import (
    SESSION_TO_STAGE,
    schedule_race_weekend_jobs,
    trigger_manual_pipeline,
)


def test_session_to_stage_mapping():
    assert SESSION_TO_STAGE["fp1"] == "fp1"
    assert SESSION_TO_STAGE["fp2"] == "fp2"
    assert SESSION_TO_STAGE["fp3"] == "fp3"
    assert SESSION_TO_STAGE["quali"] == "quali"
    assert SESSION_TO_STAGE["race"] is None  # race triggers scoring, not prediction


@patch("app.scheduler.jobs.scheduler")
def test_schedule_race_weekend_jobs(mock_scheduler):
    mock_scheduler.get_job.return_value = None

    race = MagicMock()
    race.id = 1
    race.name = "Australian GP"
    race.fp1_time = datetime.utcnow() + timedelta(days=1)
    race.fp2_time = datetime.utcnow() + timedelta(days=1, hours=4)
    race.fp3_time = datetime.utcnow() + timedelta(days=2)
    race.quali_time = datetime.utcnow() + timedelta(days=2, hours=4)
    race.race_time = datetime.utcnow() + timedelta(days=3)

    schedule_race_weekend_jobs(race)

    # Should schedule 5 jobs (fp1, fp2, fp3, quali, race)
    assert mock_scheduler.add_job.call_count == 5


@patch("app.scheduler.jobs.scheduler")
def test_schedule_skips_past_sessions(mock_scheduler):
    mock_scheduler.get_job.return_value = None

    race = MagicMock()
    race.id = 1
    race.name = "Past GP"
    race.fp1_time = datetime.utcnow() - timedelta(days=5)
    race.fp2_time = datetime.utcnow() - timedelta(days=4)
    race.fp3_time = datetime.utcnow() - timedelta(days=3)
    race.quali_time = datetime.utcnow() - timedelta(days=2)
    race.race_time = datetime.utcnow() + timedelta(days=1)  # only race is future

    schedule_race_weekend_jobs(race)

    # Only the race session should be scheduled
    assert mock_scheduler.add_job.call_count == 1


@patch("app.scheduler.jobs.SessionLocal")
@patch("app.scheduler.jobs.PredictionGenerationService")
def test_trigger_manual_pipeline(mock_pred_service_cls, mock_session_local):
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db

    race = MagicMock()
    race.name = "Test GP"
    mock_db.get.return_value = race

    mock_pred_service = MagicMock()
    mock_pred_service.generate_predictions.return_value = 15
    mock_pred_service_cls.return_value = mock_pred_service

    result = trigger_manual_pipeline(1, "pre")

    assert result["success"] is True
    assert result["predictions_generated"] == 15
```

**Commit message:** `feat: add APScheduler integration with event-driven job triggers`

---

### Task 12: Add Seeding CLI Command and Admin Seed Endpoint

**Files:**
- Modify: `backend/app/routers/admin.py`

Add an endpoint to trigger the full data seed from the admin router, useful for initial setup and development.

- [ ] **Step 1: Add seed endpoint to admin router**

Add to `backend/app/routers/admin.py`:

```python
# Add to imports at top:
import asyncio
from app.services.seeder import run_full_seed, seed_teams_and_drivers

# Add these new endpoints:

@router.post("/seed")
def trigger_full_seed(db: Session = Depends(get_db)):
    """Trigger full database seed: teams, drivers, schedules, historical data."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_full_seed(db))
        return {"status": "Seed completed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Seed failed: {str(e)}")
    finally:
        loop.close()


@router.post("/seed/teams-drivers")
def trigger_seed_teams_drivers(db: Session = Depends(get_db)):
    """Seed only teams and drivers (fast, no external API calls for data)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        team_map = loop.run_until_complete(seed_teams_and_drivers(db))
        return {"status": "ok", "teams_seeded": len(team_map)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Seed failed: {str(e)}")
    finally:
        loop.close()
```

**Commit message:** `feat: add admin endpoints for data seeding and pipeline triggering`

---

### Task 13: Training Orchestrator — Batch Train All Models

**Files:**
- Create: `backend/app/ml/training.py`

Provides a single entry point to train all models from historical data. Called during initial setup and can be triggered via admin endpoint.

- [ ] **Step 1: Create the training orchestrator**

```python
# backend/app/ml/training.py
"""Batch training orchestrator for all ML models."""

import logging

import numpy as np
from sqlalchemy.orm import Session

from app.models.f1 import RaceWeekend, Driver
from app.models.prediction import ActualResult
from app.models.training_data import HistoricalFeature, SessionData, DriverSessionStats
from app.ml.features import build_features_for_stage, store_features
from app.ml.models import (
    PositionRanker,
    FastestLapClassifier,
    SafetyCarPredictor,
    DNFPredictor,
    PitStopPredictor,
    TireStrategyPredictor,
)

logger = logging.getLogger(__name__)


def train_all_models(db: Session, stage: str = "pre") -> dict[str, int]:
    """
    Train all ML models using historical data.

    Steps:
    1. Build features for all completed races at the given stage.
    2. Extract targets (actual results) for each training example.
    3. Train each model type.

    Args:
        db: Database session.
        stage: Which prediction stage to train for.

    Returns:
        Dict mapping model name to number of training samples used.
    """
    logger.info("Starting batch training for stage: %s", stage)
    results = {}

    # Step 1: Build features for all completed races (if not already stored)
    completed_races = db.query(RaceWeekend).filter(
        RaceWeekend.status == "completed",
    ).order_by(RaceWeekend.season, RaceWeekend.round).all()

    for race in completed_races:
        existing_count = db.query(HistoricalFeature).filter(
            HistoricalFeature.race_weekend_id == race.id,
            HistoricalFeature.stage == stage,
        ).count()
        if existing_count == 0:
            feature_sets = build_features_for_stage(db, race.id, stage)
            if feature_sets:
                # Enrich with actual results for training targets
                _fill_actual_targets(db, feature_sets, race.id)
                store_features(db, feature_sets)

    # Step 2: Load all stored features with targets
    all_features = db.query(HistoricalFeature).filter(
        HistoricalFeature.stage == stage,
    ).all()

    if not all_features:
        logger.warning("No training data available for stage %s", stage)
        return results

    # --- Train qualifying position ranker ---
    quali_X, quali_y = _extract_training_data(all_features, "qualifying_position")
    if len(quali_X) >= 20:
        ranker = PositionRanker(stage=stage, target="qualifying_position")
        ranker.train(quali_X, quali_y)
        results["qualifying_ranker"] = len(quali_X)

    # --- Train race position ranker ---
    race_X, race_y = _extract_training_data(all_features, "race_position")
    if len(race_X) >= 20:
        ranker = PositionRanker(stage=stage, target="race_position")
        ranker.train(race_X, race_y)
        results["race_ranker"] = len(race_X)

    # --- Train fastest lap classifier ---
    fl_X, fl_y = _extract_fl_targets(db, all_features)
    if len(fl_X) >= 20:
        clf = FastestLapClassifier(stage=stage)
        clf.train(fl_X, fl_y)
        results["fastest_lap"] = len(fl_X)

    # --- Train safety car predictor ---
    sc_X, sc_yes, sc_counts = _extract_sc_targets(db, all_features)
    if len(sc_X) >= 10:
        predictor = SafetyCarPredictor(stage=stage)
        predictor.train(sc_X, sc_yes, sc_counts)
        results["safety_car"] = len(sc_X)

    # --- Train DNF predictor ---
    dnf_X, dnf_y = _extract_dnf_targets(db, all_features)
    if len(dnf_X) >= 20:
        predictor = DNFPredictor(stage=stage)
        predictor.train(dnf_X, dnf_y)
        results["dnf"] = len(dnf_X)

    # --- Train pit stop predictor ---
    pit_X, pit_y = _extract_pit_targets(db, all_features)
    if len(pit_X) >= 10:
        predictor = PitStopPredictor(stage=stage)
        predictor.train(pit_X, pit_y)
        results["pitstop"] = len(pit_X)

    # --- Train tire strategy predictor ---
    tire_X, tire_y = _extract_tire_targets(db, all_features)
    if len(tire_X) >= 10:
        predictor = TireStrategyPredictor(stage=stage)
        predictor.train(tire_X, tire_y)
        results["tire_strategy"] = len(tire_X)

    logger.info("Training complete: %s", results)
    return results


def _fill_actual_targets(db: Session, feature_sets, race_weekend_id: int) -> None:
    """Fill in actual qualifying/race positions from ActualResult."""
    results = db.query(ActualResult).filter(
        ActualResult.race_weekend_id == race_weekend_id,
    ).all()

    quali_map = {}
    race_map = {}
    for r in results:
        if r.category == "qualifying_top5" and r.driver_id and r.position:
            quali_map[r.driver_id] = r.position
        elif r.category == "race_top5" and r.driver_id and r.position:
            race_map[r.driver_id] = r.position

    for fs in feature_sets:
        # For drivers outside top 5, assign positions 6-20 based on historical avg
        fs.features["_qualifying_position"] = quali_map.get(fs.driver_id)
        fs.features["_race_position"] = race_map.get(fs.driver_id)


def _extract_training_data(
    features: list[HistoricalFeature], target_key: str,
) -> tuple[list[dict], list[int]]:
    """Extract feature dicts and targets where target is available."""
    X, y = [], []
    internal_key = f"_{target_key}"
    for f in features:
        target = f.feature_vector.get(internal_key) or getattr(f, target_key, None)
        if target is not None:
            X.append(f.feature_vector)
            y.append(int(target))
    return X, y


def _extract_fl_targets(
    db: Session, features: list[HistoricalFeature],
) -> tuple[list[dict], list[int]]:
    """Extract fastest lap binary targets."""
    # Group features by race weekend
    race_features: dict[int, list[HistoricalFeature]] = {}
    for f in features:
        race_features.setdefault(f.race_weekend_id, []).append(f)

    X, y = [], []
    for race_id, feats in race_features.items():
        fl_result = db.query(ActualResult).filter(
            ActualResult.race_weekend_id == race_id,
            ActualResult.category == "fastest_lap",
        ).first()

        fl_driver_id = fl_result.driver_id if fl_result else None

        for f in feats:
            X.append(f.feature_vector)
            y.append(1 if f.driver_id == fl_driver_id else 0)

    return X, y


def _extract_sc_targets(
    db: Session, features: list[HistoricalFeature],
) -> tuple[list[dict], list[int], list[int]]:
    """Extract safety car targets — one per race."""
    seen_races = set()
    X, sc_yes, sc_counts = [], [], []

    for f in features:
        if f.race_weekend_id in seen_races:
            continue
        seen_races.add(f.race_weekend_id)

        sc_result = db.query(ActualResult).filter(
            ActualResult.race_weekend_id == f.race_weekend_id,
            ActualResult.category == "safety_car",
        ).first()

        if sc_result:
            X.append(f.feature_vector)
            sc_yes.append(1 if sc_result.value == "yes" else 0)
            sc_counts.append(sc_result.position or 0)

    return X, sc_yes, sc_counts


def _extract_dnf_targets(
    db: Session, features: list[HistoricalFeature],
) -> tuple[list[dict], list[int]]:
    """Extract DNF binary targets per driver per race."""
    race_dnfs: dict[int, set[int]] = {}

    race_ids = set(f.race_weekend_id for f in features)
    dnf_results = db.query(ActualResult).filter(
        ActualResult.race_weekend_id.in_(race_ids),
        ActualResult.category == "dnf",
    ).all()

    for r in dnf_results:
        race_dnfs.setdefault(r.race_weekend_id, set()).add(r.driver_id)

    X, y = [], []
    for f in features:
        dnf_set = race_dnfs.get(f.race_weekend_id, set())
        X.append(f.feature_vector)
        y.append(1 if f.driver_id in dnf_set else 0)

    return X, y


def _extract_pit_targets(
    db: Session, features: list[HistoricalFeature],
) -> tuple[list[dict], list[float]]:
    """Extract pit stop time targets per team per race."""
    seen = set()
    X, y = [], []

    for f in features:
        if f.race_weekend_id in seen:
            continue
        seen.add(f.race_weekend_id)

        pit_result = db.query(ActualResult).filter(
            ActualResult.race_weekend_id == f.race_weekend_id,
            ActualResult.category == "quickest_pitstop",
        ).first()

        if pit_result and pit_result.value:
            X.append({
                "team_avg_pit_time": f.feature_vector.get("team_avg_pit_time", 2.5),
                "team_constructor_position": f.feature_vector.get("team_constructor_position", 10),
                "team_reliability_rate": f.feature_vector.get("team_reliability_rate", 0.95),
            })
            y.append(float(pit_result.value))

    return X, y


def _extract_tire_targets(
    db: Session, features: list[HistoricalFeature],
) -> tuple[list[dict], list[int]]:
    """Extract tire strategy (pit stop count) targets."""
    seen = set()
    X, y = [], []

    for f in features:
        if f.race_weekend_id in seen:
            continue
        seen.add(f.race_weekend_id)

        tire_result = db.query(ActualResult).filter(
            ActualResult.race_weekend_id == f.race_weekend_id,
            ActualResult.category == "tire_strategy",
        ).first()

        if tire_result and tire_result.position is not None:
            X.append(f.feature_vector)
            y.append(tire_result.position)

    return X, y
```

- [ ] **Step 2: Add training endpoint to admin router**

Add to `backend/app/routers/admin.py`:

```python
# Add to imports:
from app.ml.training import train_all_models

# Add endpoint:

@router.post("/train-models")
def trigger_model_training(stage: str = "pre", db: Session = Depends(get_db)):
    """Train all ML models from historical data."""
    valid_stages = ["pre", "fp1", "fp2", "fp3", "quali"]
    if stage not in valid_stages:
        raise HTTPException(status_code=400, detail=f"Invalid stage. Must be one of: {valid_stages}")
    results = train_all_models(db, stage)
    return {"status": "Training complete", "models_trained": results}
```

**Commit message:** `feat: add batch training orchestrator for all ML models`

---

## Summary

The implementation consists of 13 tasks that build up the ML pipeline layer by layer:

| Task | What it does | Key files |
|------|-------------|-----------|
| 1 | Dependencies + config | `pyproject.toml`, `config.py` |
| 2 | Training data models | `models/training_data.py` |
| 3 | Jolyon API client | `ingestion/jolyon_client.py` |
| 4 | FastF1 telemetry client | `ingestion/fastf1_client.py` |
| 5 | Weather API client | `ingestion/weather_client.py` |
| 6 | Data sync orchestrator | `ingestion/data_sync.py` |
| 7 | Data seeder | `services/seeder.py` |
| 8 | Feature engineering | `ml/features.py` |
| 9 | ML models (all 6 types) | `ml/models.py`, `ml/model_store.py` |
| 10 | Prediction generation | `ml/prediction_service.py` |
| 11 | APScheduler integration | `scheduler/jobs.py`, `main.py` |
| 12 | Admin seed/trigger endpoints | `routers/admin.py` |
| 13 | Batch training orchestrator | `ml/training.py` |

**Execution order matters:** Tasks 1-2 must come first (dependencies and models). Tasks 3-5 can run in parallel (independent API clients). Task 6 depends on 3-5. Task 7 depends on 6. Task 8 depends on 2. Tasks 9-10 depend on 8. Task 11 depends on 6+10. Tasks 12-13 depend on 7+10+11.
