# F1 Predict — Backend API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete backend REST API with auth, predictions, scoring, and leaderboard — ready for the ML pipeline and frontend to connect to.

**Architecture:** Single FastAPI application with SQLAlchemy ORM, PostgreSQL for production, SQLite for tests. JWT auth with OAuth support. Pure-function scoring engine with comprehensive test coverage.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0, Pydantic v2, python-jose, passlib, authlib, pytest, httpx

**Plan scope:** This is Plan 1 of 3. Plan 2 covers Data Ingestion & ML Pipeline. Plan 3 covers the Frontend.

---

## File Structure

```
backend/
├── pyproject.toml
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, router includes, CORS
│   ├── config.py             # Settings from environment variables
│   ├── database.py           # SQLAlchemy engine, session factory, Base
│   ├── dependencies.py       # get_db, get_current_user
│   ├── enums.py              # PredictionCategory, SessionStage, RaceStatus
│   ├── models/
│   │   ├── __init__.py       # Re-exports all models
│   │   ├── user.py           # User
│   │   ├── f1.py             # Team, Driver, RaceWeekend
│   │   └── prediction.py     # UserPrediction, PredictionDetail, ActualResult, MLPrediction, UserScore
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py           # RegisterRequest, LoginRequest, TokenResponse, UserResponse
│   │   ├── race.py           # RaceWeekendResponse, DriverResponse, TeamResponse
│   │   └── prediction.py     # PredictionSubmission, PredictionResponse, ScoreResponse, LeaderboardEntry
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py           # /auth/* endpoints
│   │   ├── races.py          # /races/* endpoints
│   │   ├── predictions.py    # /races/{id}/predict, /races/{id}/my-prediction
│   │   └── leaderboard.py    # /leaderboard/* endpoints
│   └── services/
│       ├── __init__.py
│       ├── auth.py           # hash_password, verify_password, create_token, decode_token
│       └── scoring.py        # score_position_based, score_single_pick, score_special, calculate_race_scores
├── tests/
│   ├── conftest.py           # Test DB, client, auth fixtures
│   ├── test_scoring.py       # Scoring engine unit tests
│   ├── test_auth.py          # Auth endpoint integration tests
│   ├── test_predictions.py   # Prediction submission + deadline tests
│   └── test_leaderboard.py   # Leaderboard endpoint tests
```

---

### Task 1: Project Scaffold & Configuration

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`

- [ ] **Step 1: Create pyproject.toml with all dependencies**

```toml
[project]
name = "f1-predict-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "sqlalchemy>=2.0.0",
    "psycopg2-binary>=2.9.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
    "authlib>=1.3.0",
    "httpx>=0.27.0",
    "python-multipart>=0.0.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",
]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"
```

- [ ] **Step 2: Create app config**

```python
# backend/app/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./f1predict.db"
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24  # 24 hours

    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    frontend_url: str = "http://localhost:3000"

    model_config = {"env_file": ".env"}


settings = Settings()
```

- [ ] **Step 3: Create minimal FastAPI app**

```python
# backend/app/__init__.py
```

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

app = FastAPI(title="F1 Predict API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok"}
```

- [ ] **Step 4: Install and verify the app starts**

Run: `cd backend && pip install -e ".[dev]" && python -m uvicorn app.main:app --port 8000 &`
Then: `curl http://localhost:8000/health`
Expected: `{"status":"ok"}`
Kill the server after verification.

- [ ] **Step 5: Commit**

```bash
git add backend/
git commit -m "feat: scaffold backend project with FastAPI and config"
```

---

### Task 2: Database Setup & All Models

**Files:**
- Create: `backend/app/database.py`
- Create: `backend/app/enums.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/f1.py`
- Create: `backend/app/models/prediction.py`

- [ ] **Step 1: Create database connection module**

```python
# backend/app/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, echo=False)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 2: Create enums**

```python
# backend/app/enums.py
import enum


class PredictionCategory(str, enum.Enum):
    QUALIFYING_TOP5 = "qualifying_top5"
    RACE_TOP5 = "race_top5"
    SPRINT_TOP5 = "sprint_top5"
    FASTEST_LAP = "fastest_lap"
    CONSTRUCTOR_POINTS = "constructor_points"
    QUICKEST_PITSTOP = "quickest_pitstop"
    TEAMMATE_BATTLE = "teammate_battle"
    SAFETY_CAR = "safety_car"
    DNF = "dnf"
    TIRE_STRATEGY = "tire_strategy"


class SessionStage(str, enum.Enum):
    PRE = "pre"
    FP1 = "fp1"
    FP2 = "fp2"
    FP3 = "fp3"
    QUALI = "quali"


class RaceStatus(str, enum.Enum):
    UPCOMING = "upcoming"
    ACTIVE = "active"
    COMPLETED = "completed"
```

- [ ] **Step 3: Create User model**

```python
# backend/app/models/user.py
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255))
    oauth_provider: Mapped[str | None] = mapped_column(String(20))
    oauth_id: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    total_score: Mapped[int] = mapped_column(Integer, default=0)

    predictions: Mapped[list["UserPrediction"]] = relationship(back_populates="user")
    scores: Mapped[list["UserScore"]] = relationship(back_populates="user")
```

- [ ] **Step 4: Create F1 models (Team, Driver, RaceWeekend)**

```python
# backend/app/models/f1.py
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
```

- [ ] **Step 5: Create prediction models**

```python
# backend/app/models/prediction.py
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
```

- [ ] **Step 6: Create models __init__.py**

```python
# backend/app/models/__init__.py
from app.models.user import User
from app.models.f1 import Team, Driver, RaceWeekend
from app.models.prediction import (
    UserPrediction,
    PredictionDetail,
    ActualResult,
    MLPrediction,
    UserScore,
)

__all__ = [
    "User",
    "Team",
    "Driver",
    "RaceWeekend",
    "UserPrediction",
    "PredictionDetail",
    "ActualResult",
    "MLPrediction",
    "UserScore",
]
```

- [ ] **Step 7: Wire up database table creation in main.py**

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
import app.models  # noqa: F401 — registers models with Base

app = FastAPI(title="F1 Predict API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health_check():
    return {"status": "ok"}
```

- [ ] **Step 8: Verify tables are created**

Run: `cd backend && python -c "from app.main import app; from app.database import engine, Base; Base.metadata.create_all(bind=engine); print('Tables:', list(Base.metadata.tables.keys()))"`
Expected: Lists all 8 tables: users, teams, drivers, race_weekends, user_predictions, prediction_details, actual_results, ml_predictions, user_scores

- [ ] **Step 9: Commit**

```bash
git add backend/
git commit -m "feat: add database setup and all SQLAlchemy models"
```

---

### Task 3: Test Fixtures & Dependencies

**Files:**
- Create: `backend/app/dependencies.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Create FastAPI dependencies**

```python
# backend/app/dependencies.py
from typing import Generator

from sqlalchemy.orm import Session

from app.database import SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 2: Create test fixtures**

```python
# backend/tests/__init__.py
```

```python
# backend/tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.database import Base
from app.dependencies import get_db
from app.main import app
from app.models import Team, Driver, RaceWeekend
from app.services.auth import hash_password
from app.models.user import User

TEST_DB_URL = "sqlite:///./test.db"


@pytest.fixture(scope="function")
def db():
    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    TestSession = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sample_team(db):
    team = Team(
        name="Red Bull Racing", short_name="RBR",
        color_hex="#3671C6", country="Austria", active=True,
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


@pytest.fixture
def sample_teams(db):
    teams = [
        Team(name="Red Bull Racing", short_name="RBR", color_hex="#3671C6", country="Austria"),
        Team(name="McLaren", short_name="MCL", color_hex="#FF8700", country="United Kingdom"),
    ]
    db.add_all(teams)
    db.commit()
    for t in teams:
        db.refresh(t)
    return teams


@pytest.fixture
def sample_drivers(db, sample_teams):
    drivers = [
        Driver(code="VER", full_name="Max Verstappen", team_id=sample_teams[0].id, number=1, country="Netherlands"),
        Driver(code="PER", full_name="Sergio Perez", team_id=sample_teams[0].id, number=11, country="Mexico"),
        Driver(code="NOR", full_name="Lando Norris", team_id=sample_teams[1].id, number=4, country="United Kingdom"),
        Driver(code="PIA", full_name="Oscar Piastri", team_id=sample_teams[1].id, number=81, country="Australia"),
    ]
    db.add_all(drivers)
    db.commit()
    for d in drivers:
        db.refresh(d)
    return drivers


@pytest.fixture
def sample_race(db):
    from datetime import datetime, timedelta
    race = RaceWeekend(
        season=2026, round=1, name="Australian Grand Prix",
        circuit_id="albert_park", country="Australia",
        is_sprint_weekend=False,
        quali_time=datetime.utcnow() + timedelta(days=7),
        race_time=datetime.utcnow() + timedelta(days=8),
        prediction_deadline=datetime.utcnow() + timedelta(days=7),
        status="upcoming",
    )
    db.add(race)
    db.commit()
    db.refresh(race)
    return race


@pytest.fixture
def past_race(db):
    from datetime import datetime, timedelta
    race = RaceWeekend(
        season=2026, round=1, name="Australian Grand Prix",
        circuit_id="albert_park", country="Australia",
        is_sprint_weekend=False,
        quali_time=datetime.utcnow() - timedelta(days=1),
        race_time=datetime.utcnow() - timedelta(hours=12),
        prediction_deadline=datetime.utcnow() - timedelta(days=1),
        status="completed",
    )
    db.add(race)
    db.commit()
    db.refresh(race)
    return race


@pytest.fixture
def test_user(db):
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=hash_password("password123"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    from app.services.auth import create_access_token
    token = create_access_token(user_id=test_user.id)
    return {"Authorization": f"Bearer {token}"}
```

- [ ] **Step 3: Verify fixtures load without errors**

Run: `cd backend && python -m pytest tests/conftest.py --collect-only`
Expected: No errors (no tests collected, but module loads cleanly)

- [ ] **Step 4: Commit**

```bash
git add backend/
git commit -m "feat: add test fixtures and FastAPI dependencies"
```

---

### Task 4: Auth Service

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/auth.py`
- Create: `backend/tests/test_auth.py`

- [ ] **Step 1: Write failing tests for auth service functions**

```python
# backend/tests/test_auth.py
from app.services.auth import hash_password, verify_password, create_access_token, decode_access_token


class TestPasswordHashing:
    def test_hash_password_returns_hash(self):
        hashed = hash_password("mysecret")
        assert hashed != "mysecret"
        assert len(hashed) > 20

    def test_verify_password_correct(self):
        hashed = hash_password("mysecret")
        assert verify_password("mysecret", hashed) is True

    def test_verify_password_wrong(self):
        hashed = hash_password("mysecret")
        assert verify_password("wrongpassword", hashed) is False


class TestJWT:
    def test_create_and_decode_token(self):
        token = create_access_token(user_id=42)
        payload = decode_access_token(token)
        assert payload["sub"] == 42

    def test_decode_invalid_token_returns_none(self):
        payload = decode_access_token("not.a.valid.token")
        assert payload is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_auth.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement auth service**

```python
# backend/app/services/__init__.py
```

```python
# backend/app/services/auth.py
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_auth.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/
git commit -m "feat: add auth service with password hashing and JWT"
```

---

### Task 5: Auth Schemas & Dependency

**Files:**
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/auth.py`
- Modify: `backend/app/dependencies.py`

- [ ] **Step 1: Create auth schemas**

```python
# backend/app/schemas/__init__.py
```

```python
# backend/app/schemas/auth.py
from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: str
    username: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    avatar_url: str | None = None
    total_score: int = 0

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Add get_current_user dependency**

```python
# backend/app/dependencies.py
from typing import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.auth import decode_access_token

security = HTTPBearer()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    from app.models.user import User

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.get(User, payload["sub"])
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
```

- [ ] **Step 3: Commit**

```bash
git add backend/
git commit -m "feat: add auth schemas and current_user dependency"
```

---

### Task 6: Auth Router (Register, Login, Me)

**Files:**
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/auth.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_auth.py`

- [ ] **Step 1: Write failing integration tests for auth endpoints**

Append to `backend/tests/test_auth.py`:

```python
class TestAuthEndpoints:
    def test_register_success(self, client):
        resp = client.post("/auth/register", json={
            "email": "new@example.com",
            "username": "newuser",
            "password": "securepass123",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["access_token"]
        assert data["token_type"] == "bearer"

    def test_register_duplicate_email(self, client, test_user):
        resp = client.post("/auth/register", json={
            "email": "test@example.com",
            "username": "other",
            "password": "password123",
        })
        assert resp.status_code == 409

    def test_login_success(self, client, test_user):
        resp = client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "password123",
        })
        assert resp.status_code == 200
        assert resp.json()["access_token"]

    def test_login_wrong_password(self, client, test_user):
        resp = client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    def test_me_authenticated(self, client, test_user, auth_headers):
        resp = client.get("/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["email"] == "test@example.com"

    def test_me_unauthenticated(self, client):
        resp = client.get("/auth/me")
        assert resp.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_auth.py::TestAuthEndpoints -v`
Expected: FAIL (404 — routes don't exist)

- [ ] **Step 3: Implement auth router**

```python
# backend/app/routers/__init__.py
```

```python
# backend/app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, UserResponse
from app.services.auth import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(
        (User.email == body.email) | (User.username == body.username)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email or username already taken")

    user = User(
        email=body.email,
        username=body.username,
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user_id=user.id)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(user_id=user.id)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user
```

- [ ] **Step 4: Register router in main.py**

Add to `backend/app/main.py` after the middleware setup:

```python
from app.routers import auth

app.include_router(auth.router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_auth.py -v`
Expected: All 11 tests PASS (5 unit + 6 integration)

- [ ] **Step 6: Commit**

```bash
git add backend/
git commit -m "feat: add auth router with register, login, and me endpoints"
```

---

### Task 7: Race & F1 Data Schemas and Router

**Files:**
- Create: `backend/app/schemas/race.py`
- Create: `backend/app/routers/races.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create race schemas**

```python
# backend/app/schemas/race.py
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


class RaceWeekendDetail(RaceWeekendResponse):
    ai_predictions: list["MLPredictionResponse"] = []


class MLPredictionResponse(BaseModel):
    category: str
    position: int | None = None
    driver_id: int | None = None
    team_id: int | None = None
    confidence: float
    session_stage: str
    generated_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Implement races router**

```python
# backend/app/routers/races.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models.f1 import RaceWeekend, Driver, Team
from app.models.prediction import MLPrediction
from app.schemas.race import (
    RaceWeekendResponse,
    RaceWeekendDetail,
    DriverResponse,
    TeamResponse,
    MLPredictionResponse,
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


@router.get("/{race_id}", response_model=RaceWeekendDetail)
def get_race(race_id: int, db: Session = Depends(get_db)):
    race = db.get(RaceWeekend, race_id)
    if not race:
        raise HTTPException(status_code=404, detail="Race not found")

    # Get latest AI predictions (most recent session_stage)
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
```

- [ ] **Step 3: Register races router in main.py**

Add to `backend/app/main.py`:

```python
from app.routers import auth, races

app.include_router(auth.router)
app.include_router(races.router)
```

- [ ] **Step 4: Quick smoke test**

Run: `cd backend && python -m pytest tests/test_auth.py -v`
Expected: All existing tests still PASS (no regressions)

- [ ] **Step 5: Commit**

```bash
git add backend/
git commit -m "feat: add race weekend, driver, and team endpoints"
```

---

### Task 8: Prediction Schemas & Submission Router

**Files:**
- Create: `backend/app/schemas/prediction.py`
- Create: `backend/app/routers/predictions.py`
- Create: `backend/tests/test_predictions.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create prediction schemas**

```python
# backend/app/schemas/prediction.py
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
```

- [ ] **Step 2: Write failing tests for prediction endpoints**

```python
# backend/tests/test_predictions.py
from datetime import datetime, timedelta


class TestPredictionSubmission:
    def test_submit_prediction_success(self, client, auth_headers, sample_race, sample_drivers):
        resp = client.post(
            f"/races/{sample_race.id}/predict",
            headers=auth_headers,
            json={
                "details": [
                    {"category": "qualifying_top5", "position": 1, "driver_id": sample_drivers[0].id},
                    {"category": "qualifying_top5", "position": 2, "driver_id": sample_drivers[2].id},
                    {"category": "fastest_lap", "driver_id": sample_drivers[0].id},
                ]
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["race_weekend_id"] == sample_race.id
        assert len(data["details"]) == 3
        assert data["locked"] is True

    def test_submit_prediction_after_deadline(self, client, auth_headers, past_race, sample_drivers):
        resp = client.post(
            f"/races/{past_race.id}/predict",
            headers=auth_headers,
            json={
                "details": [
                    {"category": "qualifying_top5", "position": 1, "driver_id": sample_drivers[0].id},
                ]
            },
        )
        assert resp.status_code == 403
        assert "deadline" in resp.json()["detail"].lower()

    def test_submit_prediction_unauthenticated(self, client, sample_race):
        resp = client.post(
            f"/races/{sample_race.id}/predict",
            json={"details": []},
        )
        assert resp.status_code == 403

    def test_get_my_prediction(self, client, auth_headers, sample_race, sample_drivers):
        # First submit
        client.post(
            f"/races/{sample_race.id}/predict",
            headers=auth_headers,
            json={
                "details": [
                    {"category": "fastest_lap", "driver_id": sample_drivers[0].id},
                ]
            },
        )
        # Then retrieve
        resp = client.get(f"/races/{sample_race.id}/my-prediction", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["details"][0]["category"] == "fastest_lap"

    def test_get_my_prediction_none(self, client, auth_headers, sample_race):
        resp = client.get(f"/races/{sample_race.id}/my-prediction", headers=auth_headers)
        assert resp.status_code == 404

    def test_update_prediction_replaces(self, client, auth_headers, sample_race, sample_drivers):
        # Submit first prediction
        client.post(
            f"/races/{sample_race.id}/predict",
            headers=auth_headers,
            json={
                "details": [
                    {"category": "fastest_lap", "driver_id": sample_drivers[0].id},
                ]
            },
        )
        # Submit updated prediction
        resp = client.post(
            f"/races/{sample_race.id}/predict",
            headers=auth_headers,
            json={
                "details": [
                    {"category": "fastest_lap", "driver_id": sample_drivers[2].id},
                ]
            },
        )
        assert resp.status_code == 201
        assert resp.json()["details"][0]["driver_id"] == sample_drivers[2].id
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_predictions.py -v`
Expected: FAIL (404 — routes don't exist)

- [ ] **Step 4: Implement predictions router**

```python
# backend/app/routers/predictions.py
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
```

- [ ] **Step 5: Register predictions router in main.py**

Add to `backend/app/main.py`:

```python
from app.routers import auth, races, predictions

app.include_router(auth.router)
app.include_router(races.router)
app.include_router(predictions.router)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_predictions.py -v`
Expected: All 6 tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/
git commit -m "feat: add prediction submission and retrieval endpoints"
```

---

### Task 9: Scoring Engine — Position-Based

**Files:**
- Create: `backend/app/services/scoring.py`
- Create: `backend/tests/test_scoring.py`

- [ ] **Step 1: Write failing tests for position-based scoring**

```python
# backend/tests/test_scoring.py
from app.services.scoring import score_position_based


class TestPositionBasedScoring:
    def test_exact_match_all_five(self):
        predicted = [10, 20, 30, 40, 50]  # driver IDs in order P1-P5
        actual = [10, 20, 30, 40, 50]
        result = score_position_based(predicted, actual)
        # 5 exact matches × 25 = 125 + 10 bonus = 135
        assert result["total"] == 135
        assert result["bonus"] is True

    def test_exact_match_single(self):
        predicted = [10, 20, 30, 40, 50]
        actual = [10, 99, 98, 97, 96]
        result = score_position_based(predicted, actual)
        # P1 exact = 25, rest not in top 5 = 0
        assert result["total"] == 25

    def test_off_by_one(self):
        predicted = [20, 10, 30, 40, 50]
        actual = [10, 20, 30, 40, 50]
        result = score_position_based(predicted, actual)
        # P1: predicted 20, actual 10 → 20 is at actual P2 → off by 1 = 15
        # P2: predicted 10, actual 20 → 10 is at actual P1 → off by 1 = 15
        # P3-P5: exact = 25 each = 75
        assert result["total"] == 15 + 15 + 75
        assert result["bonus"] is False

    def test_off_by_two(self):
        predicted = [30, 20, 10, 40, 50]
        actual = [10, 20, 30, 40, 50]
        result = score_position_based(predicted, actual)
        # P1: predicted 30, actual at P3 → off by 2 = 8
        # P2: predicted 20, actual at P2 → exact = 25
        # P3: predicted 10, actual at P1 → off by 2 = 8
        # P4, P5: exact = 25 each = 50
        assert result["total"] == 8 + 25 + 8 + 50

    def test_in_top5_wrong_position(self):
        predicted = [50, 40, 30, 20, 10]
        actual = [10, 20, 30, 40, 50]
        result = score_position_based(predicted, actual)
        # P1: predicted 50, actual at P5 → off by 4 = 3
        # P2: predicted 40, actual at P4 → off by 2 = 8
        # P3: predicted 30, actual at P3 → exact = 25
        # P4: predicted 20, actual at P2 → off by 2 = 8
        # P5: predicted 10, actual at P1 → off by 4 = 3
        assert result["total"] == 3 + 8 + 25 + 8 + 3

    def test_not_in_top5(self):
        predicted = [90, 91, 92, 93, 94]
        actual = [10, 20, 30, 40, 50]
        result = score_position_based(predicted, actual)
        assert result["total"] == 0

    def test_sprint_half_weight(self):
        predicted = [10, 20, 30, 40, 50]
        actual = [10, 20, 30, 40, 50]
        result = score_position_based(predicted, actual, is_sprint=True)
        # (125 + 10 bonus) * 0.5 = 67, rounded down = 67
        assert result["total"] == 67

    def test_partial_predictions(self):
        predicted = [10, 20]  # only predicted 2 positions
        actual = [10, 20, 30, 40, 50]
        result = score_position_based(predicted, actual)
        # P1: exact = 25, P2: exact = 25
        assert result["total"] == 50
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_scoring.py::TestPositionBasedScoring -v`
Expected: FAIL (import error)

- [ ] **Step 3: Implement position-based scoring**

```python
# backend/app/services/scoring.py
import math


def score_position_based(
    predicted_driver_ids: list[int],
    actual_driver_ids: list[int],
    is_sprint: bool = False,
) -> dict:
    """Score a top-5 position prediction against actual results.

    Args:
        predicted_driver_ids: driver IDs in predicted order (P1 first)
        actual_driver_ids: driver IDs in actual order (P1 first)
        is_sprint: if True, apply 0.5 weight

    Returns:
        dict with 'total', 'breakdown' (per-position), and 'bonus'
    """
    points_map = {0: 25, 1: 15, 2: 8}  # offset → points
    in_top5_points = 3

    actual_pos = {driver_id: pos for pos, driver_id in enumerate(actual_driver_ids[:5])}
    breakdown = []
    total = 0

    for pred_pos, driver_id in enumerate(predicted_driver_ids[:5]):
        if driver_id in actual_pos:
            offset = abs(pred_pos - actual_pos[driver_id])
            pts = points_map.get(offset, in_top5_points)
        else:
            pts = 0
        breakdown.append({"position": pred_pos + 1, "driver_id": driver_id, "points": pts})
        total += pts

    # Perfect 5 bonus: all 5 exactly correct
    all_exact = (
        len(predicted_driver_ids) >= 5
        and len(actual_driver_ids) >= 5
        and all(
            predicted_driver_ids[i] == actual_driver_ids[i]
            for i in range(5)
        )
    )
    bonus = all_exact

    if bonus:
        total += 10

    if is_sprint:
        total = math.floor(total * 0.5)

    return {"total": total, "breakdown": breakdown, "bonus": bonus}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_scoring.py::TestPositionBasedScoring -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/
git commit -m "feat: add position-based scoring engine with Perfect 5 bonus"
```

---

### Task 10: Scoring Engine — Single-Pick & Special Categories

**Files:**
- Modify: `backend/app/services/scoring.py`
- Modify: `backend/tests/test_scoring.py`

- [ ] **Step 1: Write failing tests for single-pick scoring**

Append to `backend/tests/test_scoring.py`:

```python
from app.services.scoring import score_fastest_lap, score_constructor, score_pitstop


class TestSinglePickScoring:
    def test_fastest_lap_exact(self):
        # Predicted driver got fastest lap
        assert score_fastest_lap(predicted_driver_id=10, actual_driver_id=10, predicted_team_id=1, actual_team_id=1) == {"total": 30, "close": False}

    def test_fastest_lap_same_team(self):
        # Wrong driver, right team
        assert score_fastest_lap(predicted_driver_id=11, actual_driver_id=10, predicted_team_id=1, actual_team_id=1) == {"total": 10, "close": True}

    def test_fastest_lap_wrong(self):
        assert score_fastest_lap(predicted_driver_id=20, actual_driver_id=10, predicted_team_id=2, actual_team_id=1) == {"total": 0, "close": False}

    def test_constructor_exact(self):
        assert score_constructor(predicted_team_id=1, actual_first_id=1, actual_second_id=2) == {"total": 30, "close": False}

    def test_constructor_second(self):
        assert score_constructor(predicted_team_id=2, actual_first_id=1, actual_second_id=2) == {"total": 10, "close": True}

    def test_constructor_wrong(self):
        assert score_constructor(predicted_team_id=3, actual_first_id=1, actual_second_id=2) == {"total": 0, "close": False}

    def test_pitstop_exact(self):
        assert score_pitstop(predicted_team_id=1, actual_team_id=1, predicted_time=None, actual_fastest_time=2.1) == {"total": 30, "close": False}

    def test_pitstop_close(self):
        # Within 0.3s of fastest
        assert score_pitstop(predicted_team_id=2, actual_team_id=1, predicted_time=None, actual_fastest_time=2.1, predicted_team_time=2.3) == {"total": 10, "close": True}

    def test_pitstop_wrong(self):
        assert score_pitstop(predicted_team_id=2, actual_team_id=1, predicted_time=None, actual_fastest_time=2.1, predicted_team_time=3.0) == {"total": 0, "close": False}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_scoring.py::TestSinglePickScoring -v`
Expected: FAIL (import error)

- [ ] **Step 3: Implement single-pick scoring functions**

Append to `backend/app/services/scoring.py`:

```python
def score_fastest_lap(
    predicted_driver_id: int,
    actual_driver_id: int,
    predicted_team_id: int,
    actual_team_id: int,
) -> dict:
    if predicted_driver_id == actual_driver_id:
        return {"total": 30, "close": False}
    if predicted_team_id == actual_team_id:
        return {"total": 10, "close": True}
    return {"total": 0, "close": False}


def score_constructor(
    predicted_team_id: int,
    actual_first_id: int,
    actual_second_id: int,
) -> dict:
    if predicted_team_id == actual_first_id:
        return {"total": 30, "close": False}
    if predicted_team_id == actual_second_id:
        return {"total": 10, "close": True}
    return {"total": 0, "close": False}


def score_pitstop(
    predicted_team_id: int,
    actual_team_id: int,
    predicted_time: float | None,
    actual_fastest_time: float,
    predicted_team_time: float | None = None,
) -> dict:
    if predicted_team_id == actual_team_id:
        return {"total": 30, "close": False}
    if predicted_team_time is not None and abs(predicted_team_time - actual_fastest_time) <= 0.3:
        return {"total": 10, "close": True}
    return {"total": 0, "close": False}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_scoring.py::TestSinglePickScoring -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Write failing tests for special category scoring**

Append to `backend/tests/test_scoring.py`:

```python
from app.services.scoring import score_teammate_battles, score_safety_car, score_dnf, score_tire_strategy


class TestSpecialCategoryScoring:
    def test_teammate_battles_all_correct(self):
        predicted = {1: 10, 2: 30}  # team_id → predicted winner driver_id
        actual = {1: 10, 2: 30}
        result = score_teammate_battles(predicted, actual)
        assert result["total"] == 10  # 2 × 5

    def test_teammate_battles_mixed(self):
        predicted = {1: 10, 2: 30}
        actual = {1: 10, 2: 40}  # got team 2 wrong
        result = score_teammate_battles(predicted, actual)
        assert result["total"] == 5

    def test_safety_car_yes_correct(self):
        result = score_safety_car(predicted_yes=True, actual_yes=True, predicted_count=2, actual_count=2)
        assert result["total"] == 20  # 10 for yes + 10 for count

    def test_safety_car_yes_wrong_count(self):
        result = score_safety_car(predicted_yes=True, actual_yes=True, predicted_count=3, actual_count=2)
        assert result["total"] == 10  # 10 for yes, 0 for count

    def test_safety_car_wrong(self):
        result = score_safety_car(predicted_yes=False, actual_yes=True, predicted_count=0, actual_count=2)
        assert result["total"] == 0

    def test_dnf_all_correct(self):
        result = score_dnf(predicted_driver_ids=[10, 20], actual_driver_ids=[10, 20, 30])
        assert result["total"] == 30  # 2 × 15

    def test_dnf_partial(self):
        result = score_dnf(predicted_driver_ids=[10, 20, 30], actual_driver_ids=[10, 50])
        assert result["total"] == 15  # 1 correct × 15

    def test_dnf_none_correct(self):
        result = score_dnf(predicted_driver_ids=[10, 20], actual_driver_ids=[30, 40])
        assert result["total"] == 0

    def test_tire_strategy_correct(self):
        result = score_tire_strategy(predicted_stops=2, actual_stops=2)
        assert result["total"] == 20

    def test_tire_strategy_wrong(self):
        result = score_tire_strategy(predicted_stops=1, actual_stops=2)
        assert result["total"] == 0
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_scoring.py::TestSpecialCategoryScoring -v`
Expected: FAIL (import error)

- [ ] **Step 7: Implement special category scoring**

Append to `backend/app/services/scoring.py`:

```python
def score_teammate_battles(
    predicted_winners: dict[int, int],
    actual_winners: dict[int, int],
) -> dict:
    """Score teammate battle predictions.

    Args:
        predicted_winners: {team_id: winning_driver_id}
        actual_winners: {team_id: winning_driver_id}
    """
    total = 0
    breakdown = []
    for team_id, predicted_driver in predicted_winners.items():
        correct = actual_winners.get(team_id) == predicted_driver
        pts = 5 if correct else 0
        total += pts
        breakdown.append({"team_id": team_id, "correct": correct, "points": pts})
    return {"total": total, "breakdown": breakdown}


def score_safety_car(
    predicted_yes: bool,
    actual_yes: bool,
    predicted_count: int,
    actual_count: int,
) -> dict:
    total = 0
    yes_no_correct = predicted_yes == actual_yes
    count_correct = predicted_count == actual_count

    if yes_no_correct:
        total += 10
    if yes_no_correct and predicted_yes and count_correct:
        total += 10

    return {
        "total": total,
        "yes_no_correct": yes_no_correct,
        "count_correct": count_correct,
    }


def score_dnf(
    predicted_driver_ids: list[int],
    actual_driver_ids: list[int],
) -> dict:
    actual_set = set(actual_driver_ids)
    correct = [d for d in predicted_driver_ids if d in actual_set]
    total = len(correct) * 15
    return {"total": total, "correct_drivers": correct}


def score_tire_strategy(
    predicted_stops: int,
    actual_stops: int,
) -> dict:
    correct = predicted_stops == actual_stops
    return {"total": 20 if correct else 0, "correct": correct}
```

- [ ] **Step 8: Run all scoring tests**

Run: `cd backend && python -m pytest tests/test_scoring.py -v`
Expected: All 27 tests PASS

- [ ] **Step 9: Commit**

```bash
git add backend/
git commit -m "feat: add scoring for all prediction categories"
```

---

### Task 11: Leaderboard Router

**Files:**
- Create: `backend/app/routers/leaderboard.py`
- Create: `backend/tests/test_leaderboard.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing tests for leaderboard**

```python
# backend/tests/test_leaderboard.py
from app.models.prediction import UserScore
from app.models.user import User
from app.services.auth import hash_password


class TestLeaderboard:
    def _create_users_with_scores(self, db, sample_race):
        """Helper: create 3 users with scores for the given race."""
        users = []
        for i, (name, score) in enumerate([("alice", 300), ("bob", 250), ("charlie", 400)]):
            user = User(email=f"{name}@test.com", username=name, hashed_password=hash_password("pw"), total_score=score)
            db.add(user)
            db.flush()
            db.add(UserScore(
                user_id=user.id, race_weekend_id=sample_race.id,
                category="qualifying_top5", points_earned=score, breakdown={},
            ))
            users.append(user)
        db.commit()
        return users

    def test_season_leaderboard(self, client, db, sample_race):
        self._create_users_with_scores(db, sample_race)
        resp = client.get("/leaderboard/season")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 3
        # Highest score first
        assert data[0]["username"] == "charlie"
        assert data[0]["total_score"] == 400
        assert data[0]["rank"] == 1

    def test_race_leaderboard(self, client, db, sample_race):
        self._create_users_with_scores(db, sample_race)
        resp = client.get(f"/leaderboard/race/{sample_race.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 3
        assert data[0]["rank"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_leaderboard.py -v`
Expected: FAIL (404)

- [ ] **Step 3: Implement leaderboard router**

```python
# backend/app/routers/leaderboard.py
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
            rank=rank,
            user_id=user.id,
            username=user.username,
            total_score=user.total_score,
            races_participated=race_count,
            best_weekend=best[0] if best else 0,
        ))
    return entries


@router.get("/race/{race_id}", response_model=list[LeaderboardEntry])
def race_leaderboard(race_id: int, db: Session = Depends(get_db)):
    results = (
        db.query(
            UserScore.user_id,
            func.sum(UserScore.points_earned).label("race_total"),
        )
        .filter(UserScore.race_weekend_id == race_id)
        .group_by(UserScore.user_id)
        .order_by(func.sum(UserScore.points_earned).desc())
        .all()
    )

    entries = []
    for rank, (user_id, race_total) in enumerate(results, start=1):
        user = db.get(User, user_id)
        entries.append(LeaderboardEntry(
            rank=rank,
            user_id=user.id,
            username=user.username,
            total_score=int(race_total),
            races_participated=1,
            best_weekend=int(race_total),
        ))
    return entries
```

- [ ] **Step 4: Register leaderboard router in main.py**

Add to `backend/app/main.py`:

```python
from app.routers import auth, races, predictions, leaderboard

app.include_router(auth.router)
app.include_router(races.router)
app.include_router(predictions.router)
app.include_router(leaderboard.router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_leaderboard.py -v`
Expected: All 2 tests PASS

- [ ] **Step 6: Run full test suite**

Run: `cd backend && python -m pytest -v`
Expected: All tests PASS (scoring + auth + predictions + leaderboard)

- [ ] **Step 7: Commit**

```bash
git add backend/
git commit -m "feat: add leaderboard endpoints for season and per-race rankings"
```

---

### Task 12: Results & Score Calculation Endpoint

**Files:**
- Create: `backend/app/services/score_calculator.py`
- Create: `backend/app/routers/admin.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write tests for score calculation orchestrator**

Append to `backend/tests/test_scoring.py`:

```python
from app.services.score_calculator import calculate_user_race_score


class TestScoreCalculator:
    def test_calculate_user_race_score(self):
        """Test the full orchestrator with qualifying and fastest lap."""
        prediction_details = [
            {"category": "qualifying_top5", "position": 1, "driver_id": 10},
            {"category": "qualifying_top5", "position": 2, "driver_id": 20},
            {"category": "qualifying_top5", "position": 3, "driver_id": 30},
            {"category": "qualifying_top5", "position": 4, "driver_id": 40},
            {"category": "qualifying_top5", "position": 5, "driver_id": 50},
            {"category": "fastest_lap", "driver_id": 10, "team_id": 1},
        ]
        actual_results = {
            "qualifying_top5": [10, 20, 30, 40, 50],  # exact match
            "fastest_lap": {"driver_id": 10, "team_id": 1},
        }
        scores = calculate_user_race_score(prediction_details, actual_results, is_sprint_weekend=False)
        assert scores["qualifying_top5"]["total"] == 135  # 125 + 10 bonus
        assert scores["fastest_lap"]["total"] == 30
        assert scores["grand_total"] == 165
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_scoring.py::TestScoreCalculator -v`
Expected: FAIL (import error)

- [ ] **Step 3: Implement score calculator orchestrator**

```python
# backend/app/services/score_calculator.py
from app.services.scoring import (
    score_position_based,
    score_fastest_lap,
    score_constructor,
    score_pitstop,
    score_teammate_battles,
    score_safety_car,
    score_dnf,
    score_tire_strategy,
)


def calculate_user_race_score(
    prediction_details: list[dict],
    actual_results: dict,
    is_sprint_weekend: bool = False,
) -> dict:
    """Calculate scores for all prediction categories.

    Args:
        prediction_details: list of dicts with category, position, driver_id, team_id, value
        actual_results: dict keyed by category with actual outcome data
        is_sprint_weekend: whether sprint scoring applies

    Returns:
        dict keyed by category with score dicts, plus 'grand_total'
    """
    # Group predictions by category
    by_category: dict[str, list[dict]] = {}
    for detail in prediction_details:
        cat = detail["category"]
        by_category.setdefault(cat, []).append(detail)

    scores = {}
    grand_total = 0

    # Position-based categories
    for cat, is_sprint in [("qualifying_top5", False), ("race_top5", False), ("sprint_top5", True)]:
        if cat in by_category and cat in actual_results:
            predicted = sorted(by_category[cat], key=lambda d: d.get("position", 99))
            predicted_ids = [d["driver_id"] for d in predicted]
            actual_ids = actual_results[cat]
            result = score_position_based(predicted_ids, actual_ids, is_sprint=is_sprint)
            scores[cat] = result
            grand_total += result["total"]

    # Fastest lap
    if "fastest_lap" in by_category and "fastest_lap" in actual_results:
        pred = by_category["fastest_lap"][0]
        actual = actual_results["fastest_lap"]
        result = score_fastest_lap(
            pred["driver_id"], actual["driver_id"],
            pred.get("team_id", 0), actual.get("team_id", 0),
        )
        scores["fastest_lap"] = result
        grand_total += result["total"]

    # Constructor points
    if "constructor_points" in by_category and "constructor_points" in actual_results:
        pred = by_category["constructor_points"][0]
        actual = actual_results["constructor_points"]
        result = score_constructor(pred["team_id"], actual["first_id"], actual["second_id"])
        scores["constructor_points"] = result
        grand_total += result["total"]

    # Quickest pit stop
    if "quickest_pitstop" in by_category and "quickest_pitstop" in actual_results:
        pred = by_category["quickest_pitstop"][0]
        actual = actual_results["quickest_pitstop"]
        result = score_pitstop(
            pred["team_id"], actual["team_id"],
            None, actual["fastest_time"],
            actual.get("predicted_team_time"),
        )
        scores["quickest_pitstop"] = result
        grand_total += result["total"]

    # Teammate battles
    if "teammate_battle" in by_category and "teammate_battle" in actual_results:
        predicted_winners = {}
        for d in by_category["teammate_battle"]:
            if d.get("team_id") and d.get("driver_id"):
                predicted_winners[d["team_id"]] = d["driver_id"]
        result = score_teammate_battles(predicted_winners, actual_results["teammate_battle"])
        scores["teammate_battle"] = result
        grand_total += result["total"]

    # Safety car
    if "safety_car" in by_category and "safety_car" in actual_results:
        pred = by_category["safety_car"][0]
        actual = actual_results["safety_car"]
        pred_yes = pred.get("value", "").lower() == "yes"
        pred_count = int(pred.get("position") or 0)
        result = score_safety_car(pred_yes, actual["yes"], pred_count, actual["count"])
        scores["safety_car"] = result
        grand_total += result["total"]

    # DNF
    if "dnf" in by_category and "dnf" in actual_results:
        predicted_ids = [d["driver_id"] for d in by_category["dnf"] if d.get("driver_id")]
        result = score_dnf(predicted_ids, actual_results["dnf"])
        scores["dnf"] = result
        grand_total += result["total"]

    # Tire strategy
    if "tire_strategy" in by_category and "tire_strategy" in actual_results:
        pred = by_category["tire_strategy"][0]
        pred_stops = int(pred.get("value") or pred.get("position") or 0)
        result = score_tire_strategy(pred_stops, actual_results["tire_strategy"])
        scores["tire_strategy"] = result
        grand_total += result["total"]

    scores["grand_total"] = grand_total
    return scores
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_scoring.py -v`
Expected: All 28 tests PASS

- [ ] **Step 5: Create admin trigger endpoint**

```python
# backend/app/routers/admin.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models.f1 import RaceWeekend
from app.models.prediction import UserPrediction, ActualResult, UserScore
from app.models.user import User
from app.services.score_calculator import calculate_user_race_score

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/score-race/{race_id}")
def trigger_scoring(race_id: int, db: Session = Depends(get_db)):
    """Manually trigger scoring for a race. Requires actual results to be populated."""
    race = db.get(RaceWeekend, race_id)
    if not race:
        raise HTTPException(status_code=404, detail="Race not found")

    # Load actual results
    results_rows = db.query(ActualResult).filter(ActualResult.race_weekend_id == race_id).all()
    if not results_rows:
        raise HTTPException(status_code=400, detail="No actual results found for this race")

    actual_results = _build_actual_results(results_rows)

    # Score each user's prediction
    predictions = db.query(UserPrediction).filter(UserPrediction.race_weekend_id == race_id).all()
    scored_users = []

    for prediction in predictions:
        # Clear existing scores
        db.query(UserScore).filter(
            UserScore.user_id == prediction.user_id,
            UserScore.race_weekend_id == race_id,
        ).delete()

        details = [
            {
                "category": d.category,
                "position": d.position,
                "driver_id": d.driver_id,
                "team_id": d.team_id,
                "value": d.value,
            }
            for d in prediction.details
        ]

        scores = calculate_user_race_score(details, actual_results, race.is_sprint_weekend)

        for cat, score_data in scores.items():
            if cat == "grand_total":
                continue
            db.add(UserScore(
                user_id=prediction.user_id,
                race_weekend_id=race_id,
                category=cat,
                points_earned=score_data["total"],
                breakdown=score_data,
            ))

        # Update user total
        user = db.get(User, prediction.user_id)
        all_scores = db.query(UserScore).filter(UserScore.user_id == user.id).all()
        user.total_score = sum(s.points_earned for s in all_scores) + scores["grand_total"]
        scored_users.append({"user_id": user.id, "total": scores["grand_total"]})

    db.commit()
    race.status = "completed"
    db.commit()

    return {"scored": len(scored_users), "users": scored_users}


def _build_actual_results(results_rows: list[ActualResult]) -> dict:
    """Convert ActualResult rows into the dict format score_calculator expects."""
    grouped: dict[str, list] = {}
    for r in results_rows:
        grouped.setdefault(r.category, []).append(r)

    actual = {}

    for cat in ["qualifying_top5", "race_top5", "sprint_top5"]:
        if cat in grouped:
            sorted_rows = sorted(grouped[cat], key=lambda r: r.position or 99)
            actual[cat] = [r.driver_id for r in sorted_rows]

    if "fastest_lap" in grouped:
        r = grouped["fastest_lap"][0]
        actual["fastest_lap"] = {"driver_id": r.driver_id, "team_id": r.team_id}

    if "constructor_points" in grouped:
        sorted_rows = sorted(grouped["constructor_points"], key=lambda r: r.position or 99)
        actual["constructor_points"] = {
            "first_id": sorted_rows[0].team_id,
            "second_id": sorted_rows[1].team_id if len(sorted_rows) > 1 else None,
        }

    if "quickest_pitstop" in grouped:
        r = grouped["quickest_pitstop"][0]
        actual["quickest_pitstop"] = {
            "team_id": r.team_id,
            "fastest_time": float(r.value) if r.value else 0.0,
        }

    if "teammate_battle" in grouped:
        actual["teammate_battle"] = {r.team_id: r.driver_id for r in grouped["teammate_battle"]}

    if "safety_car" in grouped:
        r = grouped["safety_car"][0]
        actual["safety_car"] = {
            "yes": r.value == "yes",
            "count": r.position or 0,
        }

    if "dnf" in grouped:
        actual["dnf"] = [r.driver_id for r in grouped["dnf"]]

    if "tire_strategy" in grouped:
        r = grouped["tire_strategy"][0]
        actual["tire_strategy"] = r.position or int(r.value or 0)

    return actual
```

- [ ] **Step 6: Register admin router in main.py**

Add to `backend/app/main.py`:

```python
from app.routers import auth, races, predictions, leaderboard, admin

app.include_router(auth.router)
app.include_router(races.router)
app.include_router(predictions.router)
app.include_router(leaderboard.router)
app.include_router(admin.router)
```

- [ ] **Step 7: Run full test suite**

Run: `cd backend && python -m pytest -v`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add backend/
git commit -m "feat: add score calculation orchestrator and admin scoring endpoint"
```

---

### Task 13: AI Predictions & Results Endpoints

**Files:**
- Modify: `backend/app/routers/races.py`

- [ ] **Step 1: Add results and AI prediction history endpoints**

Append to `backend/app/routers/races.py`:

```python
from app.models.prediction import ActualResult, UserScore, MLPrediction
from app.schemas.prediction import ScoreDetailResponse, RaceResultsResponse
from app.schemas.race import MLPredictionResponse
from app.dependencies import get_current_user
from app.models.user import User


@router.get("/{race_id}/results", response_model=RaceResultsResponse)
def get_race_results(
    race_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    race = db.get(RaceWeekend, race_id)
    if not race:
        raise HTTPException(status_code=404, detail="Race not found")

    scores = (
        db.query(UserScore)
        .filter(UserScore.user_id == current_user.id, UserScore.race_weekend_id == race_id)
        .all()
    )
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
```

- [ ] **Step 2: Run full test suite to check for regressions**

Run: `cd backend && python -m pytest -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/
git commit -m "feat: add race results and AI prediction history endpoints"
```

---

### Task 14: OAuth Support (Google + GitHub)

**Files:**
- Modify: `backend/app/routers/auth.py`

- [ ] **Step 1: Add OAuth endpoints to auth router**

Append to `backend/app/routers/auth.py`:

```python
from authlib.integrations.starlette_client import OAuth
from starlette.requests import Request
from starlette.responses import RedirectResponse

from app.config import settings

oauth = OAuth()

if settings.google_client_id:
    oauth.register(
        name="google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

if settings.github_client_id:
    oauth.register(
        name="github",
        client_id=settings.github_client_id,
        client_secret=settings.github_client_secret,
        authorize_url="https://github.com/login/oauth/authorize",
        access_token_url="https://github.com/login/oauth/access_token",
        api_base_url="https://api.github.com/",
        client_kwargs={"scope": "user:email"},
    )


@router.get("/google")
async def google_login(request: Request):
    redirect_uri = f"{settings.frontend_url}/auth/callback/google"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.google.authorize_access_token(request)
    user_info = token.get("userinfo", {})

    user = db.query(User).filter(User.oauth_provider == "google", User.oauth_id == user_info["sub"]).first()
    if not user:
        user = db.query(User).filter(User.email == user_info["email"]).first()
        if user:
            user.oauth_provider = "google"
            user.oauth_id = user_info["sub"]
        else:
            user = User(
                email=user_info["email"],
                username=user_info.get("name", user_info["email"].split("@")[0]),
                oauth_provider="google",
                oauth_id=user_info["sub"],
                avatar_url=user_info.get("picture"),
            )
            db.add(user)
        db.commit()
        db.refresh(user)

    jwt_token = create_access_token(user_id=user.id)
    return RedirectResponse(f"{settings.frontend_url}/auth/success?token={jwt_token}")


@router.get("/github")
async def github_login(request: Request):
    redirect_uri = f"{settings.frontend_url}/auth/callback/github"
    return await oauth.github.authorize_redirect(request, redirect_uri)


@router.get("/github/callback")
async def github_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.github.authorize_access_token(request)
    resp = await oauth.github.get("user", token=token)
    user_info = resp.json()

    email_resp = await oauth.github.get("user/emails", token=token)
    emails = email_resp.json()
    primary_email = next((e["email"] for e in emails if e["primary"]), user_info.get("email"))

    user = db.query(User).filter(User.oauth_provider == "github", User.oauth_id == str(user_info["id"])).first()
    if not user:
        user = db.query(User).filter(User.email == primary_email).first()
        if user:
            user.oauth_provider = "github"
            user.oauth_id = str(user_info["id"])
        else:
            user = User(
                email=primary_email,
                username=user_info.get("login", primary_email.split("@")[0]),
                oauth_provider="github",
                oauth_id=str(user_info["id"]),
                avatar_url=user_info.get("avatar_url"),
            )
            db.add(user)
        db.commit()
        db.refresh(user)

    jwt_token = create_access_token(user_id=user.id)
    return RedirectResponse(f"{settings.frontend_url}/auth/success?token={jwt_token}")
```

- [ ] **Step 2: Add starlette to dependencies**

Add `"starlette>=0.41.0"` and `"itsdangerous>=2.0.0"` to the dependencies list in `pyproject.toml`. (Starlette is already included via FastAPI, but itsdangerous is needed for OAuth session state.)

- [ ] **Step 3: Run full test suite**

Run: `cd backend && python -m pytest -v`
Expected: All tests PASS (OAuth endpoints exist but aren't tested — they require real OAuth providers)

- [ ] **Step 4: Commit**

```bash
git add backend/
git commit -m "feat: add Google and GitHub OAuth login endpoints"
```

---

### Task 15: User History & Stats Endpoints

**Files:**
- Modify: `backend/app/routers/races.py` (or create a new user router)

- [ ] **Step 1: Create user router**

```python
# backend/app/routers/users.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.prediction import UserScore, UserPrediction

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{user_id}/history")
def get_user_history(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    race_scores = (
        db.query(
            UserScore.race_weekend_id,
            func.sum(UserScore.points_earned).label("total"),
        )
        .filter(UserScore.user_id == user_id)
        .group_by(UserScore.race_weekend_id)
        .order_by(UserScore.race_weekend_id)
        .all()
    )

    return {
        "user_id": user_id,
        "username": user.username,
        "races": [
            {"race_weekend_id": r.race_weekend_id, "points": int(r.total)}
            for r in race_scores
        ],
    }


@router.get("/{user_id}/stats")
def get_user_stats(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    category_scores = (
        db.query(
            UserScore.category,
            func.sum(UserScore.points_earned).label("total"),
            func.count(UserScore.id).label("count"),
        )
        .filter(UserScore.user_id == user_id)
        .group_by(UserScore.category)
        .all()
    )

    categories = [
        {
            "category": cs.category,
            "total_points": int(cs.total),
            "predictions_made": cs.count,
            "avg_points": round(int(cs.total) / cs.count, 1) if cs.count else 0,
        }
        for cs in category_scores
    ]
    categories.sort(key=lambda c: c["total_points"], reverse=True)

    races_participated = (
        db.query(func.count(func.distinct(UserPrediction.race_weekend_id)))
        .filter(UserPrediction.user_id == user_id)
        .scalar()
    ) or 0

    return {
        "user_id": user_id,
        "username": user.username,
        "total_score": user.total_score,
        "races_participated": races_participated,
        "categories": categories,
        "best_category": categories[0]["category"] if categories else None,
        "worst_category": categories[-1]["category"] if categories else None,
    }
```

- [ ] **Step 2: Register users router in main.py**

Add to `backend/app/main.py`:

```python
from app.routers import auth, races, predictions, leaderboard, admin, users

app.include_router(auth.router)
app.include_router(races.router)
app.include_router(predictions.router)
app.include_router(leaderboard.router)
app.include_router(admin.router)
app.include_router(users.router)
```

- [ ] **Step 3: Run full test suite**

Run: `cd backend && python -m pytest -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/
git commit -m "feat: add user history and stats endpoints"
```

---

### Task 16: Final Integration Verification

**Files:**
- No new files — verify everything works together

- [ ] **Step 1: Run full test suite**

Run: `cd backend && python -m pytest -v --tb=short`
Expected: All tests PASS. Count should be approximately 35-40 tests.

- [ ] **Step 2: Start server and verify all endpoints respond**

Run: `cd backend && python -m uvicorn app.main:app --port 8000 &`
Then verify:
```bash
curl http://localhost:8000/health
curl http://localhost:8000/docs
```
Expected: Health returns `{"status":"ok"}`, docs returns the Swagger UI HTML.

- [ ] **Step 3: Commit final state**

```bash
git add -A
git commit -m "chore: verify full backend API integration"
```

---

## Spec Coverage Checklist

| Spec Requirement | Task |
|-----------------|------|
| User model with auth fields | Task 2 |
| Team, Driver, RaceWeekend models | Task 2 |
| Prediction models (UserPrediction, PredictionDetail, etc.) | Task 2 |
| Category enum (all 10 types) | Task 2 |
| Email/password registration & login | Tasks 4-6 |
| JWT authentication | Tasks 4-5 |
| Google OAuth | Task 14 |
| GitHub OAuth | Task 14 |
| Race weekend list & detail endpoints | Task 7 |
| Driver/team list endpoints | Task 7 |
| Prediction submission with deadline enforcement | Task 8 |
| Position-based scoring (exact, off-by-1, off-by-2, in-top-5) | Task 9 |
| Perfect 5 bonus | Task 9 |
| Sprint half-weight scoring | Task 9 |
| Fastest lap scoring (exact + same team) | Task 10 |
| Constructor points scoring | Task 10 |
| Pit stop scoring (exact + within 0.3s) | Task 10 |
| Teammate battle scoring | Task 10 |
| Safety car scoring (yes/no + count) | Task 10 |
| DNF scoring | Task 10 |
| Tire strategy scoring | Task 10 |
| Score calculation orchestrator | Task 12 |
| Admin scoring trigger | Task 12 |
| Season leaderboard | Task 11 |
| Per-race leaderboard | Task 11 |
| AI prediction history endpoint | Task 13 |
| Race results endpoint | Task 13 |
| User history & stats | Task 15 |

**Deferred to Plan 2:** Data ingestion (Jolyon, FastF1, OpenWeatherMap), ML models, APScheduler, `POST /admin/trigger-pipeline`
**Deferred to Plan 3:** All frontend pages, visual design
