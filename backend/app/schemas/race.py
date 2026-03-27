from datetime import datetime
from pydantic import BaseModel


class TeamResponse(BaseModel):
    id: int
    name: str
    short_name: str
    color_hex: str
    country: str
    model_config = {"from_attributes": True}


class DriverResponse(BaseModel):
    id: int
    code: str
    full_name: str
    team_id: int
    number: int
    country: str
    model_config = {"from_attributes": True}


class RaceWeekendResponse(BaseModel):
    id: int
    season: int
    round: int
    name: str
    circuit_id: str
    country: str
    is_sprint_weekend: bool
    quali_time: datetime | None = None
    race_time: datetime | None = None
    prediction_deadline: datetime | None = None
    status: str
    model_config = {"from_attributes": True}


class MLPredictionResponse(BaseModel):
    category: str
    position: int | None = None
    driver_id: int | None = None
    team_id: int | None = None
    confidence: float
    session_stage: str
    generated_at: datetime
    model_config = {"from_attributes": True}


class RaceWeekendDetail(RaceWeekendResponse):
    ai_predictions: list[MLPredictionResponse] = []
