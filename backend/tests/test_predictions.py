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
        assert resp.status_code in (401, 403)

    def test_get_my_prediction(self, client, auth_headers, sample_race, sample_drivers):
        client.post(
            f"/races/{sample_race.id}/predict",
            headers=auth_headers,
            json={
                "details": [
                    {"category": "fastest_lap", "driver_id": sample_drivers[0].id},
                ]
            },
        )
        resp = client.get(f"/races/{sample_race.id}/my-prediction", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["details"][0]["category"] == "fastest_lap"

    def test_get_my_prediction_none(self, client, auth_headers, sample_race):
        resp = client.get(f"/races/{sample_race.id}/my-prediction", headers=auth_headers)
        assert resp.status_code == 404

    def test_update_prediction_replaces(self, client, auth_headers, sample_race, sample_drivers):
        client.post(
            f"/races/{sample_race.id}/predict",
            headers=auth_headers,
            json={
                "details": [
                    {"category": "fastest_lap", "driver_id": sample_drivers[0].id},
                ]
            },
        )
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
