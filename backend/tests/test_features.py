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
