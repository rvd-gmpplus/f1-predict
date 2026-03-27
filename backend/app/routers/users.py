# backend/app/routers/users.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models.user import User
from app.models.prediction import UserScore, UserPrediction

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{user_id}/history")
def get_user_history(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    race_scores = (
        db.query(UserScore.race_weekend_id, func.sum(UserScore.points_earned).label("total"))
        .filter(UserScore.user_id == user_id)
        .group_by(UserScore.race_weekend_id)
        .order_by(UserScore.race_weekend_id)
        .all()
    )
    return {
        "user_id": user_id, "username": user.username,
        "races": [{"race_weekend_id": r.race_weekend_id, "points": int(r.total)} for r in race_scores],
    }


@router.get("/{user_id}/stats")
def get_user_stats(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    category_scores = (
        db.query(UserScore.category, func.sum(UserScore.points_earned).label("total"), func.count(UserScore.id).label("count"))
        .filter(UserScore.user_id == user_id)
        .group_by(UserScore.category)
        .all()
    )
    categories = [
        {"category": cs.category, "total_points": int(cs.total), "predictions_made": cs.count,
         "avg_points": round(int(cs.total) / cs.count, 1) if cs.count else 0}
        for cs in category_scores
    ]
    categories.sort(key=lambda c: c["total_points"], reverse=True)
    races_participated = (
        db.query(func.count(func.distinct(UserPrediction.race_weekend_id)))
        .filter(UserPrediction.user_id == user_id).scalar()
    ) or 0
    return {
        "user_id": user_id, "username": user.username, "total_score": user.total_score,
        "races_participated": races_participated, "categories": categories,
        "best_category": categories[0]["category"] if categories else None,
        "worst_category": categories[-1]["category"] if categories else None,
    }
