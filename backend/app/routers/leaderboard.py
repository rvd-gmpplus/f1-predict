from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models.user import User
from app.models.prediction import UserScore, UserPrediction
from app.schemas.prediction import LeaderboardEntry

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("/season", response_model=list[LeaderboardEntry])
def season_leaderboard(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.total_score.desc()).all()
    entries = []
    for rank, user in enumerate(users, start=1):
        race_count = (
            db.query(func.count(func.distinct(UserPrediction.race_weekend_id)))
            .filter(UserPrediction.user_id == user.id)
            .scalar()
        ) or 0
        best = (
            db.query(func.sum(UserScore.points_earned))
            .filter(UserScore.user_id == user.id)
            .group_by(UserScore.race_weekend_id)
            .order_by(func.sum(UserScore.points_earned).desc())
            .first()
        )
        entries.append(LeaderboardEntry(
            rank=rank, user_id=user.id, username=user.username,
            total_score=user.total_score, races_participated=race_count,
            best_weekend=best[0] if best else 0,
        ))
    return entries


@router.get("/race/{race_id}", response_model=list[LeaderboardEntry])
def race_leaderboard(race_id: int, db: Session = Depends(get_db)):
    results = (
        db.query(UserScore.user_id, func.sum(UserScore.points_earned).label("race_total"))
        .filter(UserScore.race_weekend_id == race_id)
        .group_by(UserScore.user_id)
        .order_by(func.sum(UserScore.points_earned).desc())
        .all()
    )
    entries = []
    for rank, (user_id, race_total) in enumerate(results, start=1):
        user = db.get(User, user_id)
        entries.append(LeaderboardEntry(
            rank=rank, user_id=user.id, username=user.username,
            total_score=int(race_total), races_participated=1,
            best_weekend=int(race_total),
        ))
    return entries
