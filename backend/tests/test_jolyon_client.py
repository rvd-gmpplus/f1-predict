import pytest
import json
from unittest.mock import AsyncMock, patch

from app.ingestion.jolyon_client import JolyonClient, JolyonAPIError, _parse_pit_duration


@pytest.fixture
def client():
    return JolyonClient(base_url="https://api.jolyon.co/f1")


MOCK_RACE_RESULTS = {
    "MRData": {
        "RaceTable": {
            "Races": [{
                "Results": [
                    {
                        "position": "1",
                        "Driver": {"code": "VER", "givenName": "Max", "familyName": "Verstappen"},
                        "Constructor": {"name": "Red Bull"},
                        "grid": "1",
                        "status": "Finished",
                        "points": "25",
                        "FastestLap": {"rank": "1", "Time": {"time": "1:32.456"}},
                    },
                    {
                        "position": "2",
                        "Driver": {"code": "NOR", "givenName": "Lando", "familyName": "Norris"},
                        "Constructor": {"name": "McLaren"},
                        "grid": "3",
                        "status": "Finished",
                        "points": "18",
                        "FastestLap": {"rank": "5", "Time": {"time": "1:33.100"}},
                    },
                ],
            }],
        },
    },
}


MOCK_QUALIFYING_RESULTS = {
    "MRData": {
        "RaceTable": {
            "Races": [{
                "QualifyingResults": [
                    {
                        "position": "1",
                        "Driver": {"code": "VER", "givenName": "Max", "familyName": "Verstappen"},
                        "Constructor": {"name": "Red Bull"},
                        "Q1": "1:30.100",
                        "Q2": "1:29.500",
                        "Q3": "1:28.900",
                    },
                ],
            }],
        },
    },
}


@pytest.mark.asyncio
async def test_get_race_results(client):
    with patch.object(client, "_get", new_callable=AsyncMock, return_value=MOCK_RACE_RESULTS):
        results = await client.get_race_results(2025, 1)
        assert len(results) == 2
        assert results[0].driver_code == "VER"
        assert results[0].position == 1
        assert results[0].fastest_lap is True
        assert results[0].fastest_lap_time == "1:32.456"
        assert results[1].fastest_lap is False


@pytest.mark.asyncio
async def test_get_qualifying_results(client):
    with patch.object(client, "_get", new_callable=AsyncMock, return_value=MOCK_QUALIFYING_RESULTS):
        results = await client.get_qualifying_results(2025, 1)
        assert len(results) == 1
        assert results[0].driver_code == "VER"
        assert results[0].q3_time == "1:28.900"


@pytest.mark.asyncio
async def test_empty_response(client):
    empty = {"MRData": {"RaceTable": {"Races": []}}}
    with patch.object(client, "_get", new_callable=AsyncMock, return_value=empty):
        results = await client.get_race_results(2025, 99)
        assert results == []


def test_parse_pit_duration():
    assert _parse_pit_duration("23.456") == 23.456
    assert _parse_pit_duration("1:23.456") == 83.456
    assert _parse_pit_duration("invalid") == 0.0
