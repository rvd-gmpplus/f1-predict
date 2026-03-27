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
