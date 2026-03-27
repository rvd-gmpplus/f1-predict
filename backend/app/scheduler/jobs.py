"""APScheduler job definitions for the ML pipeline."""

import asyncio
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.f1 import RaceWeekend
from app.ingestion.data_sync import DataSyncService
from app.ml.prediction_service import PredictionGenerationService

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler: BackgroundScheduler | None = None

# Stage mapping: which session triggers which prediction stage
SESSION_TO_STAGE = {
    "fp1": "fp1",
    "fp2": "fp2",
    "fp3": "fp3",
    "quali": "quali",
    "race": None,  # race triggers scoring, not prediction
}


def init_scheduler() -> BackgroundScheduler:
    """Initialize and start the APScheduler."""
    global scheduler
    if scheduler is not None:
        return scheduler

    scheduler = BackgroundScheduler(
        job_defaults={"coalesce": True, "max_instances": 1},
    )
    scheduler.start()
    logger.info("APScheduler started")

    # Schedule jobs for upcoming race weekends
    schedule_upcoming_races()

    return scheduler


def shutdown_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    global scheduler
    if scheduler:
        scheduler.shutdown(wait=False)
        scheduler = None
        logger.info("APScheduler shut down")


def schedule_upcoming_races() -> None:
    """Schedule data ingestion + prediction jobs for all upcoming race weekends."""
    db = SessionLocal()
    try:
        upcoming = db.query(RaceWeekend).filter(
            RaceWeekend.status.in_(["upcoming", "active"]),
        ).all()

        for race in upcoming:
            schedule_race_weekend_jobs(race)
    finally:
        db.close()


def schedule_race_weekend_jobs(race: RaceWeekend) -> None:
    """Schedule all session-end jobs for a single race weekend."""
    delay = timedelta(minutes=settings.data_fetch_delay_minutes)

    session_times = {
        "fp1": race.fp1_time,
        "fp2": race.fp2_time,
        "fp3": race.fp3_time,
        "quali": race.quali_time,
        "race": race.race_time,
    }

    session_durations = {
        "fp1": timedelta(hours=1),
        "fp2": timedelta(hours=1),
        "fp3": timedelta(hours=1),
        "quali": timedelta(hours=1),
        "race": timedelta(hours=2),
    }

    for session_type, session_time in session_times.items():
        if not session_time:
            continue

        trigger_time = session_time + session_durations[session_type] + delay

        # Skip if trigger time is in the past
        if trigger_time < datetime.utcnow():
            continue

        job_id = f"pipeline_{race.id}_{session_type}"

        if scheduler and not scheduler.get_job(job_id):
            scheduler.add_job(
                run_pipeline_job,
                trigger=DateTrigger(run_date=trigger_time),
                id=job_id,
                args=[race.id, session_type],
                name=f"Pipeline: {race.name} {session_type}",
                replace_existing=True,
            )
            logger.info(
                "Scheduled %s for %s at %s",
                session_type, race.name, trigger_time.isoformat(),
            )


def run_pipeline_job(race_weekend_id: int, session_type: str, retry_count: int = 0) -> None:
    """
    Main pipeline job: fetch data, generate predictions.
    Runs in a background thread via APScheduler.
    """
    logger.info(
        "Running pipeline job for race %s session %s (attempt %d)",
        race_weekend_id, session_type, retry_count + 1,
    )

    db = SessionLocal()
    try:
        # Run the async data sync in a new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Step 1: Sync session data
            sync_service = DataSyncService(db)
            success = loop.run_until_complete(
                sync_service.sync_session(race_weekend_id, session_type)
            )

            if not success:
                raise RuntimeError(f"Data sync failed for {session_type}")

            # Step 2: If this is the race session, also sync results
            if session_type == "race":
                loop.run_until_complete(
                    sync_service.sync_race_results(race_weekend_id)
                )
                # Mark race as completed
                race = db.get(RaceWeekend, race_weekend_id)
                if race:
                    race.status = "completed"
                    db.commit()
                logger.info("Race results synced for race %s", race_weekend_id)
            else:
                # Step 3: Generate predictions for this stage
                stage = SESSION_TO_STAGE.get(session_type)
                if stage:
                    prediction_service = PredictionGenerationService(db)
                    count = prediction_service.generate_predictions(race_weekend_id, stage)
                    logger.info(
                        "Generated %d predictions for race %s stage %s",
                        count, race_weekend_id, stage,
                    )

        finally:
            loop.close()

    except Exception as e:
        logger.error(
            "Pipeline job failed for race %s session %s: %s",
            race_weekend_id, session_type, e,
        )
        db.rollback()

        # Retry with exponential backoff
        if retry_count < settings.max_retries:
            backoff_minutes = [30, 60, 120][retry_count]
            retry_time = datetime.utcnow() + timedelta(minutes=backoff_minutes)
            retry_job_id = f"pipeline_{race_weekend_id}_{session_type}_retry{retry_count + 1}"

            if scheduler:
                scheduler.add_job(
                    run_pipeline_job,
                    trigger=DateTrigger(run_date=retry_time),
                    id=retry_job_id,
                    args=[race_weekend_id, session_type, retry_count + 1],
                    name=f"Retry: R{race_weekend_id} {session_type} (attempt {retry_count + 2})",
                    replace_existing=True,
                )
                logger.info(
                    "Scheduled retry %d for race %s %s at %s",
                    retry_count + 1, race_weekend_id, session_type, retry_time.isoformat(),
                )
        else:
            logger.error(
                "Max retries exceeded for race %s session %s", race_weekend_id, session_type,
            )

    finally:
        db.close()


def trigger_manual_pipeline(race_weekend_id: int, stage: str) -> dict:
    """
    Manually trigger the prediction pipeline for a specific race and stage.
    Called from the admin endpoint.
    """
    db = SessionLocal()
    try:
        race = db.get(RaceWeekend, race_weekend_id)
        if not race:
            return {"error": "Race not found"}

        # If stage is a session type (fp1, fp2, etc.), run full pipeline with data sync
        if stage in SESSION_TO_STAGE:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                sync_service = DataSyncService(db)
                loop.run_until_complete(
                    sync_service.sync_session(race_weekend_id, stage)
                )
            except Exception as e:
                logger.warning("Data sync failed (continuing with prediction): %s", e)
            finally:
                loop.close()

        # Generate predictions
        prediction_service = PredictionGenerationService(db)
        count = prediction_service.generate_predictions(race_weekend_id, stage)

        return {"success": True, "predictions_generated": count}
    finally:
        db.close()
