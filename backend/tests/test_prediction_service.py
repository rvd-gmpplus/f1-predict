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
