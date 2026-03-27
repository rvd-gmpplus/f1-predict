from datetime import datetime

from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, UniqueConstraint, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserPrediction(Base):
    __tablename__ = "user_predictions"
    __table_args__ = (
        UniqueConstraint("user_id", "race_weekend_id", name="uq_user_race_prediction"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    race_weekend_id: Mapped[int] = mapped_column(ForeignKey("race_weekends.id"))
    submitted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    locked: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship(back_populates="predictions")
    race_weekend: Mapped["RaceWeekend"] = relationship(back_populates="predictions")
    details: Mapped[list["PredictionDetail"]] = relationship(back_populates="prediction", cascade="all, delete-orphan")


class PredictionDetail(Base):
    __tablename__ = "prediction_details"

    id: Mapped[int] = mapped_column(primary_key=True)
    prediction_id: Mapped[int] = mapped_column(ForeignKey("user_predictions.id"))
    category: Mapped[str] = mapped_column(String(30))
    position: Mapped[int | None] = mapped_column(Integer)
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("drivers.id"))
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    value: Mapped[str | None] = mapped_column(String(100))

    prediction: Mapped["UserPrediction"] = relationship(back_populates="details")
    driver: Mapped["Driver | None"] = relationship()
    team: Mapped["Team | None"] = relationship()


class ActualResult(Base):
    __tablename__ = "actual_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    race_weekend_id: Mapped[int] = mapped_column(ForeignKey("race_weekends.id"))
    category: Mapped[str] = mapped_column(String(30))
    position: Mapped[int | None] = mapped_column(Integer)
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("drivers.id"))
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    value: Mapped[str | None] = mapped_column(String(100))

    race_weekend: Mapped["RaceWeekend"] = relationship(back_populates="results")
    driver: Mapped["Driver | None"] = relationship()
    team: Mapped["Team | None"] = relationship()


class MLPrediction(Base):
    __tablename__ = "ml_predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    race_weekend_id: Mapped[int] = mapped_column(ForeignKey("race_weekends.id"))
    category: Mapped[str] = mapped_column(String(30))
    position: Mapped[int | None] = mapped_column(Integer)
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("drivers.id"))
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    value: Mapped[str | None] = mapped_column(String(100))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    model_version: Mapped[str] = mapped_column(String(50))
    session_stage: Mapped[str] = mapped_column(String(10))
    generated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    race_weekend: Mapped["RaceWeekend"] = relationship(back_populates="ml_predictions")
    driver: Mapped["Driver | None"] = relationship()
    team: Mapped["Team | None"] = relationship()


class UserScore(Base):
    __tablename__ = "user_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    race_weekend_id: Mapped[int] = mapped_column(ForeignKey("race_weekends.id"))
    category: Mapped[str] = mapped_column(String(30))
    points_earned: Mapped[int] = mapped_column(Integer, default=0)
    breakdown: Mapped[dict | None] = mapped_column(JSON)

    user: Mapped["User"] = relationship(back_populates="scores")
    race_weekend: Mapped["RaceWeekend"] = relationship()
