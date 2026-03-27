from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.f1 import RaceWeekend
from app.models.prediction import UserPrediction, PredictionDetail
from app.schemas.prediction import PredictionSubmission, PredictionResponse

router = APIRouter(prefix="/races", tags=["predictions"])


@router.post("/{race_id}/predict", response_model=PredictionResponse, status_code=status.HTTP_201_CREATED)
def submit_prediction(
    race_id: int,
    body: PredictionSubmission,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    race = db.get(RaceWeekend, race_id)
    if not race:
        raise HTTPException(status_code=404, detail="Race not found")

    if race.prediction_deadline and datetime.now(timezone.utc) > race.prediction_deadline.replace(tzinfo=timezone.utc):
        raise HTTPException(status_code=403, detail="Prediction deadline has passed")

    # Delete existing prediction if updating
    existing = (
        db.query(UserPrediction)
        .filter(UserPrediction.user_id == current_user.id, UserPrediction.race_weekend_id == race_id)
        .first()
    )
    if existing:
        db.delete(existing)
        db.flush()

    prediction = UserPrediction(
        user_id=current_user.id,
        race_weekend_id=race_id,
        locked=True,
    )
    db.add(prediction)
    db.flush()

    for detail in body.details:
        db.add(PredictionDetail(
            prediction_id=prediction.id,
            category=detail.category,
            position=detail.position,
            driver_id=detail.driver_id,
            team_id=detail.team_id,
            value=detail.value,
        ))

    db.commit()
    db.refresh(prediction)
    return prediction


@router.get("/{race_id}/my-prediction", response_model=PredictionResponse)
def get_my_prediction(
    race_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prediction = (
        db.query(UserPrediction)
        .filter(UserPrediction.user_id == current_user.id, UserPrediction.race_weekend_id == race_id)
        .first()
    )
    if not prediction:
        raise HTTPException(status_code=404, detail="No prediction found")
    return prediction
