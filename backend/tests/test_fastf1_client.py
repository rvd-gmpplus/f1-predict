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
