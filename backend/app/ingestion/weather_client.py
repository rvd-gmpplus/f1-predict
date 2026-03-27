"""OpenWeatherMap client for pre-race weather forecasts."""

import logging
from dataclasses import dataclass

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

OWM_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"

# Circuit coordinates for weather lookups
CIRCUIT_COORDS: dict[str, tuple[float, float]] = {
    "albert_park": (-37.8497, 144.9680),
    "shanghai": (31.3389, 121.2198),
    "suzuka": (34.8431, 136.5406),
    "bahrain": (26.0325, 50.5106),
    "jeddah": (21.6319, 39.1044),
    "miami": (25.9581, -80.2389),
    "imola": (44.3439, 11.7167),
    "monaco": (43.7347, 7.4206),
    "montreal": (45.5017, -73.5228),
    "barcelona": (41.5700, 2.2611),
    "spielberg": (47.2197, 14.7647),
    "silverstone": (52.0786, -1.0169),
    "hungaroring": (47.5789, 19.2486),
    "spa": (50.4372, 5.9714),
    "zandvoort": (52.3888, 4.5409),
    "monza": (45.6156, 9.2811),
    "baku": (40.3725, 49.8533),
    "marina_bay": (1.2914, 103.8640),
    "cota": (30.1328, -97.6411),
    "hermanos_rodriguez": (19.4042, -99.0907),
    "interlagos": (-23.7036, -46.6997),
    "vegas": (36.1162, -115.1745),
    "losail": (25.4900, 51.4542),
    "yas_marina": (24.4672, 54.6031),
}


@dataclass
class WeatherForecast:
    air_temp: float  # Celsius
    humidity: float  # percentage
    wind_speed: float  # m/s
    wind_direction: float  # degrees
    rain_probability: float  # 0-1
    description: str
    rain_mm: float  # expected rain in mm


class WeatherAPIError(Exception):
    """Raised when the OpenWeatherMap API call fails."""
    pass


class WeatherClient:
    """Fetches weather forecasts from OpenWeatherMap for circuit locations."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.openweathermap_api_key

    async def get_forecast(self, circuit_id: str) -> list[WeatherForecast]:
        """
        Get 5-day/3-hour forecast for a circuit.

        Args:
            circuit_id: The circuit identifier matching CIRCUIT_COORDS keys.

        Returns:
            List of WeatherForecast entries (up to 40 entries, 3-hour intervals).
        """
        coords = CIRCUIT_COORDS.get(circuit_id)
        if not coords:
            logger.warning("No coordinates for circuit: %s", circuit_id)
            raise WeatherAPIError(f"Unknown circuit: {circuit_id}")

        if not self.api_key:
            logger.warning("No OpenWeatherMap API key configured")
            raise WeatherAPIError("No API key configured")

        lat, lon = coords
        params = {
            "lat": lat,
            "lon": lon,
            "appid": self.api_key,
            "units": "metric",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(OWM_FORECAST_URL, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            logger.error("OpenWeatherMap HTTP error %s", e.response.status_code)
            raise WeatherAPIError(f"HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error("OpenWeatherMap request failed: %s", e)
            raise WeatherAPIError(f"Request failed: {e}") from e

        forecasts = []
        for entry in data.get("list", []):
            main = entry.get("main", {})
            wind = entry.get("wind", {})
            weather = entry.get("weather", [{}])[0]
            rain = entry.get("rain", {})
            pop = entry.get("pop", 0)

            forecasts.append(WeatherForecast(
                air_temp=main.get("temp", 0.0),
                humidity=main.get("humidity", 0.0),
                wind_speed=wind.get("speed", 0.0),
                wind_direction=wind.get("deg", 0.0),
                rain_probability=float(pop),
                description=weather.get("description", ""),
                rain_mm=rain.get("3h", 0.0),
            ))

        return forecasts

    async def get_race_weekend_forecast(self, circuit_id: str) -> WeatherForecast | None:
        """
        Get an averaged forecast for race day conditions.
        Takes the median conditions from all forecast entries to smooth noise.
        """
        try:
            forecasts = await self.get_forecast(circuit_id)
        except WeatherAPIError:
            return None

        if not forecasts:
            return None

        return WeatherForecast(
            air_temp=_median([f.air_temp for f in forecasts]),
            humidity=_median([f.humidity for f in forecasts]),
            wind_speed=_median([f.wind_speed for f in forecasts]),
            wind_direction=_median([f.wind_direction for f in forecasts]),
            rain_probability=_median([f.rain_probability for f in forecasts]),
            description="aggregated forecast",
            rain_mm=sum(f.rain_mm for f in forecasts) / len(forecasts),
        )


def _median(values: list[float]) -> float:
    """Return median of a list of floats."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    mid = len(sorted_vals) // 2
    if len(sorted_vals) % 2 == 0:
        return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2
    return sorted_vals[mid]
