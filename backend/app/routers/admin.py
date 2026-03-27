import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models.f1 import RaceWeekend
from app.models.prediction import UserPrediction, ActualResult, UserScore
from app.models.user import User
from app.services.score_calculator import calculate_user_race_score
from app.services.seeder import run_full_seed, seed_teams_and_drivers
from app.scheduler.jobs import trigger_manual_pipeline
from app.ml.training import train_all_models

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/score-race/{race_id}")
def trigger_scoring(race_id: int, db: Session = Depends(get_db)):
    race = db.get(RaceWeekend, race_id)
    if not race:
        raise HTTPException(status_code=404, detail="Race not found")

    results_rows = db.query(ActualResult).filter(ActualResult.race_weekend_id == race_id).all()
    if not results_rows:
        raise HTTPException(status_code=400, detail="No actual results found for this race")

    actual_results = _build_actual_results(results_rows)
    predictions = db.query(UserPrediction).filter(UserPrediction.race_weekend_id == race_id).all()
    scored_users = []

    for prediction in predictions:
        db.query(UserScore).filter(
            UserScore.user_id == prediction.user_id, UserScore.race_weekend_id == race_id,
        ).delete()

        details = [
            {"category": d.category, "position": d.position, "driver_id": d.driver_id, "team_id": d.team_id, "value": d.value}
            for d in prediction.details
        ]

        scores = calculate_user_race_score(details, actual_results, race.is_sprint_weekend)

        for cat, score_data in scores.items():
            if cat == "grand_total":
                continue
            db.add(UserScore(
                user_id=prediction.user_id, race_weekend_id=race_id,
                category=cat, points_earned=score_data["total"], breakdown=score_data,
            ))

        user = db.get(User, prediction.user_id)
        all_scores = db.query(UserScore).filter(UserScore.user_id == user.id).all()
        user.total_score = sum(s.points_earned for s in all_scores) + scores["grand_total"]
        scored_users.append({"user_id": user.id, "total": scores["grand_total"]})

    db.commit()
    race.status = "completed"
    db.commit()

    return {"scored": len(scored_users), "users": scored_users}


@router.post("/seed")
def trigger_full_seed(db: Session = Depends(get_db)):
    """Trigger full database seed: teams, drivers, schedules, historical data."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_full_seed(db))
        return {"status": "Seed completed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Seed failed: {str(e)}")
    finally:
        loop.close()


@router.post("/seed/teams-drivers")
def trigger_seed_teams_drivers(db: Session = Depends(get_db)):
    """Seed only teams and drivers (fast, no external API calls for data)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        team_map = loop.run_until_complete(seed_teams_and_drivers(db))
        return {"status": "ok", "teams_seeded": len(team_map)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Seed failed: {str(e)}")
    finally:
        loop.close()


@router.post("/trigger-pipeline/{race_id}/{stage}")
def trigger_pipeline(race_id: int, stage: str):
    """Manually trigger the ML prediction pipeline for a specific race and stage."""
    valid_stages = ["pre", "fp1", "fp2", "fp3", "quali"]
    if stage not in valid_stages:
        raise HTTPException(status_code=400, detail=f"Invalid stage. Must be one of: {valid_stages}")

    result = trigger_manual_pipeline(race_id, stage)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/train-models")
def trigger_model_training(stage: str = "pre", db: Session = Depends(get_db)):
    """Train all ML models from historical data."""
    valid_stages = ["pre", "fp1", "fp2", "fp3", "quali"]
    if stage not in valid_stages:
        raise HTTPException(status_code=400, detail=f"Invalid stage. Must be one of: {valid_stages}")
    results = train_all_models(db, stage)
    return {"status": "Training complete", "models_trained": results}


def _build_actual_results(results_rows: list) -> dict:
    grouped: dict[str, list] = {}
    for r in results_rows:
        grouped.setdefault(r.category, []).append(r)

    actual = {}

    for cat in ["qualifying_top5", "race_top5", "sprint_top5"]:
        if cat in grouped:
            sorted_rows = sorted(grouped[cat], key=lambda r: r.position or 99)
            actual[cat] = [r.driver_id for r in sorted_rows]

    if "fastest_lap" in grouped:
        r = grouped["fastest_lap"][0]
        actual["fastest_lap"] = {"driver_id": r.driver_id, "team_id": r.team_id}

    if "constructor_points" in grouped:
        sorted_rows = sorted(grouped["constructor_points"], key=lambda r: r.position or 99)
        actual["constructor_points"] = {
            "first_id": sorted_rows[0].team_id,
            "second_id": sorted_rows[1].team_id if len(sorted_rows) > 1 else None,
        }

    if "quickest_pitstop" in grouped:
        r = grouped["quickest_pitstop"][0]
        actual["quickest_pitstop"] = {"team_id": r.team_id, "fastest_time": float(r.value) if r.value else 0.0}

    if "teammate_battle" in grouped:
        actual["teammate_battle"] = {r.team_id: r.driver_id for r in grouped["teammate_battle"]}

    if "safety_car" in grouped:
        r = grouped["safety_car"][0]
        actual["safety_car"] = {"yes": r.value == "yes", "count": r.position or 0}

    if "dnf" in grouped:
        actual["dnf"] = [r.driver_id for r in grouped["dnf"]]

    if "tire_strategy" in grouped:
        r = grouped["tire_strategy"][0]
        actual["tire_strategy"] = r.position or int(r.value or 0)

    return actual
