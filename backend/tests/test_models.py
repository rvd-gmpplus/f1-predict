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
