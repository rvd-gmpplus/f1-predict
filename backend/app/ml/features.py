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
