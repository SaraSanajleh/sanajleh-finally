"""Jordan geography helpers. Centroids are city-level map pins, not invented POIs."""

from __future__ import annotations

from typing import Any
import re

# Public city/governorate centroids for map fallbacks when a record has no GPS.
# precision must be marked "city_centroid" whenever these are used.
CITY_CENTROIDS: dict[str, tuple[float, float]] = {
    "amman": (31.9454, 35.9284),
    "ajloun": (32.3326, 35.7517),
    "jerash": (32.2808, 35.8993),
    "irbid": (32.5556, 35.8500),
    "aqaba": (29.5320, 35.0063),
    "madaba": (31.7160, 35.7940),
    "karak": (31.1853, 35.7047),
    "maan": (30.1962, 35.7340),
    "ma'an": (30.1962, 35.7340),
    "mafraq": (32.3429, 36.2080),
    "tafilah": (30.8375, 35.6042),
    "zarqa": (32.0728, 36.0880),
    "balqa": (32.0392, 35.7272),
    "salt": (32.0392, 35.7272),
    "petra": (30.3285, 35.4444),
    "wadi rum": (29.5328, 35.4194),
    "wadi musa": (30.3220, 35.4790),
    "dead sea": (31.5590, 35.4732),
}

# Queen Alia (AMM) and King Hussein (AQJ). Used to pick the first-night hotel.
AIRPORT_COORDS: dict[str, tuple[float, float]] = {
    "AMM": (31.72255, 35.99321),
    "AQJ": (29.61162, 35.01807),
    "OTHER": (31.72255, 35.99321),
}

AIRPORT_CITY: dict[str, str] = {
    "AMM": "amman",
    "AQJ": "aqaba",
    "OTHER": "amman",
}

# north_center = reachable as day trips from Amman. south = the southern circuit.
REGION_HALF: dict[str, str] = {
    "irbid": "north_center",
    "ajloun": "north_center",
    "jerash": "north_center",
    "mafraq": "north_center",
    "amman": "north_center",
    "zarqa": "north_center",
    "balqa": "north_center",
    "salt": "north_center",
    "madaba": "north_center",
    "dead sea": "north_center",
    "karak": "south",
    "tafilah": "south",
    "petra": "south",
    "wadi musa": "south",
    "wadi rum": "south",
    "maan": "south",
    "ma'an": "south",
    "aqaba": "south",
}

REGION_BELT: dict[str, str] = {
    "irbid": "north",
    "ajloun": "north",
    "jerash": "north",
    "mafraq": "north",
    "amman": "center",
    "zarqa": "center",
    "balqa": "center",
    "salt": "center",
    "madaba": "center",
    "dead sea": "center",
    "karak": "south",
    "tafilah": "south",
    "petra": "south",
    "wadi musa": "south",
    "wadi rum": "south",
    "maan": "south",
    "ma'an": "south",
    "aqaba": "south",
}

WIZARD_REGION_TO_KEYS: dict[str, list[str]] = {
    "amman": ["amman"],
    "petra": ["petra", "maan", "ma'an", "wadi musa"],
    "wadi rum": ["wadi rum", "maan", "ma'an"],
    "aqaba": ["aqaba"],
    "dead sea": ["dead sea", "balqa", "madaba", "karak"],
    "jerash": ["jerash"],
    "ajloun": ["ajloun"],
    "madaba": ["madaba"],
    "irbid": ["irbid"],
}

REGION_ALIASES: dict[str, str] = {
    "amman governorate": "amman",
    "ajloun governorate": "ajloun",
    "jerash governorate": "jerash",
    "irbid governorate": "irbid",
    "aqaba governorate": "aqaba",
    "madaba governorate": "madaba",
    "karak governorate": "karak",
    "al karak": "karak",
    "ma'an governorate": "maan",
    "maan governorate": "maan",
    "mafraq governorate": "mafraq",
    "tafilah governorate": "tafilah",
    "tafila": "tafilah",
    "zarqa governorate": "zarqa",
    "al zarqa": "zarqa",
    "balqa governorate": "balqa",
    "al balqa": "balqa",
    "wadi musa": "petra",
    "sweimeh": "dead sea",
    "suweimeh": "dead sea",
    "sweimah": "dead sea",
    "suwayma": "dead sea",
    "as-suwayma": "dead sea",
}


def region_key(value: str | None) -> str:
    """Collapse 'Ajloun Governorate' / 'Ajloun' into a stable key."""
    text = (value or "").strip().lower()
    if not text:
        return ""
    if text in REGION_ALIASES:
        return REGION_ALIASES[text]
    text = text.replace(" governorate", "").replace("governorate", "").strip()
    text = text.replace(" region", "").strip()
    text = text.replace("al-", "").replace("al ", "")
    return REGION_ALIASES.get(text, text)


def is_known_region_key(key: str | None) -> bool:
    return bool(key) and (
        key in CITY_CENTROIDS or key in REGION_HALF or key in WIZARD_REGION_TO_KEYS
    )


def catalog_region_key(city: str | None, region: str | None) -> str:
    """Map catalog city+governorate onto a tourism region. Sweimeh is Dead Sea, not a new dest."""
    city_key = region_key(city)
    if is_known_region_key(city_key):
        return city_key
    region_mapped = region_key(region)
    if is_known_region_key(region_mapped):
        return region_mapped
    return city_key or region_mapped


def wizard_region_keys(regions: list[str]) -> set[str]:
    keys: set[str] = set()
    for region in regions:
        mapped = WIZARD_REGION_TO_KEYS.get(region_key(region), [region_key(region)])
        keys.update(k for k in mapped if k)
    return keys


def text_mentions_region(text: str, keys: set[str]) -> bool:
    hay = (text or "").lower()
    return any(key and key in hay for key in keys)


def centroid_for(name: str | None) -> tuple[float, float] | None:
    key = region_key(name)
    if key in CITY_CENTROIDS:
        return CITY_CENTROIDS[key]
    raw = (name or "").strip().lower()
    return CITY_CENTROIDS.get(raw)


def extract_coordinates(payload: dict[str, Any] | None) -> tuple[float | None, float | None]:
    if not payload:
        return None, None
    location = payload.get("location") if isinstance(payload.get("location"), dict) else payload
    coords = location.get("coordinates") if isinstance(location, dict) else None
    if isinstance(coords, dict):
        lat, lon = coords.get("latitude"), coords.get("longitude")
        if _valid_coord(lat, lon):
            return float(lat), float(lon)
    lat = payload.get("latitude")
    lon = payload.get("longitude")
    if _valid_coord(lat, lon):
        return float(lat), float(lon)
    return None, None


def _valid_coord(lat: Any, lon: Any) -> bool:
    try:
        lat_f, lon_f = float(lat), float(lon)
    except (TypeError, ValueError):
        return False
    if lat_f == 0.0 and lon_f == 0.0:
        return False
    return 29.0 <= lat_f <= 33.5 and 34.5 <= lon_f <= 39.5


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import atan2, cos, radians, sin, sqrt

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 6371.0 * 2 * atan2(sqrt(a), sqrt(1 - a))


KNOWN_REGION_KEYS: tuple[str, ...] = tuple(
    dict.fromkeys([*WIZARD_REGION_TO_KEYS.keys(), *CITY_CENTROIDS.keys(), *REGION_ALIASES.values()])
)


def regions_mentioned(text: str) -> set[str]:
    """Which Jordan tourism regions a free-text field actually names."""
    import re

    hay = (text or "").lower()
    found: set[str] = set()
    for key in KNOWN_REGION_KEYS:
        if not key:
            continue
        if " " in key or len(key) > 4:
            hit = key in hay
        else:
            hit = re.search(rf"\b{re.escape(key)}\b", hay) is not None
        if hit:
            found.add(region_key(key) or key)
    return {item for item in found if item}


def region_half(key: str | None) -> str:
    return REGION_HALF.get(region_key(key), "north_center")


def region_belt(key: str | None) -> str:
    return REGION_BELT.get(region_key(key), "center")


def venue_name_key(name: str | None) -> str:
    """Same kitchen listed as 'Al-Bustan' and 'Al-Bustan Restaurant Madaba'."""
    text = " ".join((name or "").lower().split())
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = " ".join(text.split())
    noise = {"restaurant", "cafe", "café", "the"}
    places = {key.lower() for key in CITY_CENTROIDS}
    suffixes = sorted(noise | places, key=len, reverse=True)
    changed = True
    while changed and text:
        changed = False
        for suffix in suffixes:
            token = f" {suffix}"
            if text.endswith(token):
                trimmed = text[: -len(token)].strip()
                if trimmed:
                    text = trimmed
                    changed = True
                    break
    return text


def arrival_city_key(airport: str | None) -> str:
    return AIRPORT_CITY.get((airport or "AMM").upper(), "amman")


def airport_coords(airport: str | None) -> tuple[float, float]:
    return AIRPORT_COORDS.get((airport or "AMM").upper(), AIRPORT_COORDS["AMM"])
