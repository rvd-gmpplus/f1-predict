from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models.f1 import RaceWeekend, Driver, Team
from app.models.prediction import ActualResult, UserScore, MLPrediction
from app.models.user import User
from app.schemas.race import (
    RaceWeekendResponse, RaceWeekendDetail, DriverResponse, TeamResponse, MLPredictionResponse,
)
from app.schemas.prediction import ScoreDetailResponse, RaceResultsResponse

router = APIRouter(prefix="/races", tags=["races"])


@router.get("", response_model=list[RaceWeekendResponse])
def list_races(
    season: int | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(RaceWeekend)
    if season:
        query = query.filter(RaceWeekend.season == season)
    if status:
        query = query.filter(RaceWeekend.status == status)
    return query.order_by(RaceWeekend.season, RaceWeekend.round).all()


@router.get("/drivers/all", response_model=list[DriverResponse])
def list_drivers(active: bool = True, db: Session = Depends(get_db)):
    query = db.query(Driver)
    if active:
        query = query.filter(Driver.active == True)
    return query.order_by(Driver.code).all()


@router.get("/teams/all", response_model=list[TeamResponse])
def list_teams(active: bool = True, db: Session = Depends(get_db)):
    query = db.query(Team)
    if active:
        query = query.filter(Team.active == True)
    return query.order_by(Team.name).all()


@router.get("/{race_id}", response_model=RaceWeekendDetail)
def get_race(race_id: int, db: Session = Depends(get_db)):
    race = db.get(RaceWeekend, race_id)
    if not race:
        raise HTTPException(status_code=404, detail="Race not found")

    ml_preds = (
        db.query(MLPrediction)
        .filter(MLPrediction.race_weekend_id == race_id)
        .order_by(MLPrediction.generated_at.desc())
        .all()
    )

    return RaceWeekendDetail(
        **{c.name: getattr(race, c.name) for c in race.__table__.columns},
        ai_predictions=[MLPredictionResponse.model_validate(p) for p in ml_preds],
    )


@router.get("/{race_id}/results", response_model=RaceResultsResponse)
def get_race_results(
    race_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    race = db.get(RaceWeekend, race_id)
    if not race:
        raise HTTPException(status_code=404, detail="Race not found")
    scores = db.query(UserScore).filter(UserScore.user_id == current_user.id, UserScore.race_weekend_id == race_id).all()
    total = sum(s.points_earned for s in scores)
    return RaceResultsResponse(
        race_weekend_id=race_id,
        user_scores=[ScoreDetailResponse.model_validate(s) for s in scores],
        total_points=total,
    )


@router.get("/{race_id}/ai-predictions", response_model=list[MLPredictionResponse])
def get_ai_predictions(race_id: int, db: Session = Depends(get_db)):
    preds = (
        db.query(MLPrediction)
        .filter(MLPrediction.race_weekend_id == race_id)
        .order_by(MLPrediction.session_stage, MLPrediction.category, MLPrediction.position)
        .all()
    )
    return [MLPredictionResponse.model_validate(p) for p in preds]
