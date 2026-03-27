from datetime import datetime
from pydantic import BaseModel


class PredictionDetailInput(BaseModel):
    category: str
    position: int | None = None
    driver_id: int | None = None
    team_id: int | None = None
    value: str | None = None


class PredictionSubmission(BaseModel):
    details: list[PredictionDetailInput]


class PredictionDetailResponse(BaseModel):
    category: str
    position: int | None = None
    driver_id: int | None = None
    team_id: int | None = None
    value: str | None = None
    model_config = {"from_attributes": True}


class PredictionResponse(BaseModel):
    id: int
    race_weekend_id: int
    submitted_at: datetime
    locked: bool
    details: list[PredictionDetailResponse]
    model_config = {"from_attributes": True}


class ScoreDetailResponse(BaseModel):
    category: str
    points_earned: int
    breakdown: dict | None = None
    model_config = {"from_attributes": True}


class RaceResultsResponse(BaseModel):
    race_weekend_id: int
    user_scores: list[ScoreDetailResponse]
    total_points: int


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: int
    username: str
    total_score: int
    races_participated: int
    best_weekend: int
    is_ai: bool = False
