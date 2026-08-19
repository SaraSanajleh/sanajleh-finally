"""Optional Open-Meteo weather. Degrades to unknown — never invents conditions."""

from __future__ import annotations

from datetime import date

import httpx

from app.context.models import WeatherDay
from app.planning.geo import CITY_CENTROIDS, centroid_for
from app.utils.logging import get_logger

logger = get_logger(__name__)

OPEN_METEO = "https://api.open-meteo.com/v1/forecast"


async def fetch_weather(
    *,
    region_keys: list[str],
    start: date,
    days: int,
    enabled: bool,
    timeout: float,
) -> tuple[list[WeatherDay], str]:
    if not enabled:
        return [], "disabled"
    lat_lon = None
    for key in region_keys:
        lat_lon = centroid_for(key)
        if lat_lon:
            break
    if lat_lon is None:
        lat_lon = CITY_CENTROIDS["amman"]
    end = start.toordinal() + max(days - 1, 0)
    end_date = date.fromordinal(end)
    params = {
        "latitude": lat_lon[0],
        "longitude": lat_lon[1],
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": "Asia/Amman",
        "start_date": start.isoformat(),
        "end_date": end_date.isoformat(),
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(OPEN_METEO, params=params)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:  # noqa: BLE001 — weather is optional
        logger.info("Weather unavailable: %s", exc)
        return [], "unavailable"

    daily = payload.get("daily") or {}
    dates = daily.get("time") or []
    if not dates:
        return [], "unavailable"

    days_out: list[WeatherDay] = []
    tmax = daily.get("temperature_2m_max") or []
    tmin = daily.get("temperature_2m_min") or []
    pop = daily.get("precipitation_probability_max") or []
    for idx, day in enumerate(dates):
        max_c = _num(tmax[idx] if idx < len(tmax) else None)
        min_c = _num(tmin[idx] if idx < len(tmin) else None)
        rain = _num(pop[idx] if idx < len(pop) else None)
        days_out.append(
            WeatherDay(
                date=str(day),
                t_min_c=min_c,
                t_max_c=max_c,
                precipitation_probability=rain,
                condition=_condition(max_c, rain),
                source="open-meteo",
            )
        )
    return days_out, "ok"


def _num(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _condition(max_c: float | None, rain: float | None) -> str:
    if rain is not None and rain >= 50:
        return "rain_likely"
    if max_c is not None and max_c >= 36:
        return "very_hot"
    if max_c is not None and max_c >= 30:
        return "hot"
    if max_c is not None and max_c <= 12:
        return "cool"
    if max_c is None and rain is None:
        return "unknown"
    return "fair"
