from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models.f1 import RaceWeekend
from app.models.prediction import UserPrediction, ActualResult, UserScore
from app.models.user import User
from app.services.score_calculator import calculate_user_race_score

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
