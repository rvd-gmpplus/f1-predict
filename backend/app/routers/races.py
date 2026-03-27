from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models.f1 import RaceWeekend, Driver, Team
from app.models.prediction import MLPrediction
from app.schemas.race import (
    RaceWeekendResponse, RaceWeekendDetail, DriverResponse, TeamResponse, MLPredictionResponse,
)

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
