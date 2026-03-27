import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.ingestion.weather_client import WeatherClient, WeatherAPIError, _median, CIRCUIT_COORDS


@pytest.fixture
def client():
    return WeatherClient(api_key="test-key-123")


MOCK_FORECAST_RESPONSE = {
    "list": [
        {
            "main": {"temp": 25.0, "humidity": 60.0},
            "wind": {"speed": 5.0, "deg": 180.0},
            "weather": [{"description": "clear sky"}],
            "rain": {},
            "pop": 0.1,
        },
        {
            "main": {"temp": 27.0, "humidity": 55.0},
            "wind": {"speed": 6.0, "deg": 190.0},
            "weather": [{"description": "few clouds"}],
            "rain": {"3h": 0.5},
            "pop": 0.3,
        },
    ],
}


@pytest.mark.asyncio
async def test_get_forecast(client):
    mock_response = MagicMock()
    mock_response.json.return_value = MOCK_FORECAST_RESPONSE
    mock_response.raise_for_status = MagicMock()

    with patch("app.ingestion.weather_client.httpx.AsyncClient") as mock_client_cls:
        mock_ctx = AsyncMock()
        mock_ctx.get.return_value = mock_response
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        forecasts = await client.get_forecast("albert_park")
        assert len(forecasts) == 2
        assert forecasts[0].air_temp == 25.0
        assert forecasts[1].rain_mm == 0.5


@pytest.mark.asyncio
async def test_unknown_circuit(client):
    with pytest.raises(WeatherAPIError, match="Unknown circuit"):
        await client.get_forecast("nonexistent_circuit")


@pytest.mark.asyncio
async def test_no_api_key():
    client = WeatherClient(api_key="")
    with pytest.raises(WeatherAPIError, match="No API key"):
        await client.get_forecast("albert_park")


def test_median():
    assert _median([1.0, 2.0, 3.0]) == 2.0
    assert _median([1.0, 2.0, 3.0, 4.0]) == 2.5
    assert _median([]) == 0.0


def test_circuit_coords_have_required_tracks():
    required = ["albert_park", "shanghai", "bahrain", "monaco", "silverstone", "monza", "spa"]
    for circuit in required:
        assert circuit in CIRCUIT_COORDS, f"Missing coordinates for {circuit}"
