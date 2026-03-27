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
