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
