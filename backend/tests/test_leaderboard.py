from app.models.prediction import UserScore
from app.models.user import User
from app.services.auth import hash_password


class TestLeaderboard:
    def _create_users_with_scores(self, db, sample_race):
        users = []
        for name, score in [("alice", 300), ("bob", 250), ("charlie", 400)]:
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
