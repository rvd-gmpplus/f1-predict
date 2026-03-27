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
        # For drivers outside top 5, actual positions are stored as None
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
