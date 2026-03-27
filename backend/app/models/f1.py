from datetime import datetime

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    short_name: Mapped[str] = mapped_column(String(10))
    color_hex: Mapped[str] = mapped_column(String(7))
    country: Mapped[str] = mapped_column(String(50))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    drivers: Mapped[list["Driver"]] = relationship(back_populates="team")


class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(3), unique=True)
    full_name: Mapped[str] = mapped_column(String(100))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    number: Mapped[int] = mapped_column(Integer)
    country: Mapped[str] = mapped_column(String(50))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    team: Mapped["Team"] = relationship(back_populates="drivers")


class RaceWeekend(Base):
    __tablename__ = "race_weekends"

    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[int] = mapped_column(Integer, index=True)
    round: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(100))
    circuit_id: Mapped[str] = mapped_column(String(50))
    country: Mapped[str] = mapped_column(String(50))
    is_sprint_weekend: Mapped[bool] = mapped_column(Boolean, default=False)
    fp1_time: Mapped[datetime | None] = mapped_column(DateTime)
    fp2_time: Mapped[datetime | None] = mapped_column(DateTime)
    fp3_time: Mapped[datetime | None] = mapped_column(DateTime)
    quali_time: Mapped[datetime | None] = mapped_column(DateTime)
    race_time: Mapped[datetime | None] = mapped_column(DateTime)
    prediction_deadline: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="upcoming")

    predictions: Mapped[list["UserPrediction"]] = relationship(back_populates="race_weekend")
    results: Mapped[list["ActualResult"]] = relationship(back_populates="race_weekend")
    ml_predictions: Mapped[list["MLPrediction"]] = relationship(back_populates="race_weekend")
