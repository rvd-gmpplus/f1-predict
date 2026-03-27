"""Save and load trained ML models using joblib."""

import logging
from pathlib import Path

import joblib

from app.config import settings

logger = logging.getLogger(__name__)


def get_model_path(model_name: str, version: str) -> Path:
    """Get the filesystem path for a model file."""
    model_dir = Path(settings.model_storage_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    return model_dir / f"{model_name}_{version}.joblib"


def save_model(model, model_name: str, version: str) -> Path:
    """Save a trained model to disk."""
    path = get_model_path(model_name, version)
    joblib.dump(model, path)
    logger.info("Saved model %s v%s to %s", model_name, version, path)
    return path


def load_model(model_name: str, version: str):
    """Load a trained model from disk. Returns None if not found."""
    path = get_model_path(model_name, version)
    if not path.exists():
        logger.warning("Model not found: %s", path)
        return None
    model = joblib.load(path)
    logger.info("Loaded model %s v%s from %s", model_name, version, path)
    return model


def get_latest_version(model_name: str) -> str | None:
    """Find the latest version of a model on disk."""
    model_dir = Path(settings.model_storage_dir)
    if not model_dir.exists():
        return None
    files = sorted(model_dir.glob(f"{model_name}_*.joblib"), reverse=True)
    if not files:
        return None
    # Extract version from filename: model_name_v1.2.3.joblib -> v1.2.3
    stem = files[0].stem
    version = stem.replace(f"{model_name}_", "")
    return version
