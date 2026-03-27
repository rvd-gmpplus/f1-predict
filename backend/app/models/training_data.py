from datetime import datetime

from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, JSON, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SessionData(Base):
    __tablename__ = "session_data"
    __table_args__ = (
        UniqueConstraint("race_weekend_id", "session_type", name="uq_race_session"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    race_weekend_id: Mapped[int] = mapped_column(ForeignKey("race_weekends.id"))
    session_type: Mapped[str] = mapped_column(String(20))
    weather_data: Mapped[dict | None] = mapped_column(JSON)
    track_temp: Mapped[float | None] = mapped_column(Float)
    air_temp: Mapped[float | None] = mapped_column(Float)
    rainfall: Mapped[bool] = mapped_column(Boolean, default=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DriverSessionStats(Base):
    __tablename__ = "driver_session_stats"
    __table_args__ = (
        UniqueConstraint("session_data_id", "driver_id", name="uq_session_driver"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_data_id: Mapped[int] = mapped_column(ForeignKey("session_data.id"))
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"))
    best_lap_time: Mapped[float | None] = mapped_column(Float)
    avg_lap_time: Mapped[float | None] = mapped_column(Float)
    best_sector1: Mapped[float | None] = mapped_column(Float)
    best_sector2: Mapped[float | None] = mapped_column(Float)
    best_sector3: Mapped[float | None] = mapped_column(Float)
    long_run_pace: Mapped[float | None] = mapped_column(Float)
    long_run_degradation: Mapped[float | None] = mapped_column(Float)
    stint_data: Mapped[dict | None] = mapped_column(JSON)
    top_speed: Mapped[float | None] = mapped_column(Float)
    position: Mapped[int | None] = mapped_column(Integer)
    laps_completed: Mapped[int] = mapped_column(Integer, default=0)
    is_dnf: Mapped[bool] = mapped_column(Boolean, default=False)
    tire_compounds_used: Mapped[str | None] = mapped_column(String(50))
    pit_stops: Mapped[int] = mapped_column(Integer, default=0)
    pit_times: Mapped[dict | None] = mapped_column(JSON)


class HistoricalFeature(Base):
    __tablename__ = "historical_features"
    __table_args__ = (
        UniqueConstraint("race_weekend_id", "driver_id", "stage", name="uq_feature_race_driver_stage"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    race_weekend_id: Mapped[int] = mapped_column(ForeignKey("race_weekends.id"))
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"))
    stage: Mapped[str] = mapped_column(String(10))
    feature_vector: Mapped[dict] = mapped_column(JSON)
    qualifying_position: Mapped[int | None] = mapped_column(Integer)
    race_position: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
