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
