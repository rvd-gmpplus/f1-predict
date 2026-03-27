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


@patch("app.scheduler.jobs.SessionLocal")
def test_trigger_manual_pipeline_race_not_found(mock_session_local):
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    mock_db.get.return_value = None

    result = trigger_manual_pipeline(999, "pre")

    assert "error" in result
    assert result["error"] == "Race not found"
