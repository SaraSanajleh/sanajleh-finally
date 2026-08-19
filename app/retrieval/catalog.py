"""Local tourism catalog — ground-truth POIs, restaurants, and hotels."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config.settings import get_app_settings
from app.planning.geo import catalog_region_key, region_key
from app.retrieval.knowledge import KnowledgeCard, _card_from_entity
from app.utils.logging import get_logger

logger = get_logger(__name__)

REGION_ACCEPT: dict[str, set[str]] = {
    "petra": {"petra", "wadi musa"},
    "wadi rum": {"wadi rum"},
    "dead sea": {"dead sea"},
    "maan": {"petra", "wadi musa", "maan", "ma'an"},
    "wadi musa": {"petra", "wadi musa"},
}

# Neighbouring admin regions may supply a card only when the name/city
# is clearly the same tourist destination (Suweimeh → Dead Sea).
REGION_NEIGHBORS: dict[str, set[str]] = {
    "petra": {"maan", "ma'an"},
    "wadi rum": {"maan", "ma'an", "aqaba"},
    "dead sea": {"balqa", "madaba", "karak"},
    "wadi musa": {"maan", "ma'an", "petra"},
}

NAME_HINTS: dict[str, tuple[str, ...]] = {
    "petra": ("petra", "wadi musa", "siq", "khazneh", "treasury"),
    "wadi rum": ("wadi rum", "rum village", "disi"),
    "dead sea": (
        "dead sea",
        "suweimeh",
        "sweimeh",
        "panoramic complex",
        "panorama complex",
    ),
    "jerash": ("jerash", "jarash"),
    "ajloun": ("ajloun", "ajlun"),
}


def _flatten(raw: dict[str, Any]) -> dict[str, Any]:
    identity = raw.get("identity") if isinstance(raw.get("identity"), dict) else {}
    semantic = raw.get("semantic") if isinstance(raw.get("semantic"), dict) else {}
    location = raw.get("location") if isinstance(raw.get("location"), dict) else {}
    coords = location.get("coordinates") if isinstance(location.get("coordinates"), dict) else {}
    return {
        "id": raw.get("id"),
        "name": identity.get("name") or raw.get("name"),
        "entity_type": raw.get("entity_type") or "poi",
        "region": location.get("region") or "",
        "city": location.get("city") or "",
        "category": identity.get("category") or "",
        "summary": semantic.get("summary") or "",
        "latitude": coords.get("latitude"),
        "longitude": coords.get("longitude"),
        "why_retrieved": ["local_tourism_catalog"],
        "facts": {
            "identity": identity,
            "semantic": semantic,
            "operation": raw.get("operation") if isinstance(raw.get("operation"), dict) else {},
            "pricing": raw.get("pricing") if isinstance(raw.get("pricing"), dict) else {},
            "audience": raw.get("audience") if isinstance(raw.get("audience"), dict) else {},
            "experience": raw.get("experience") if isinstance(raw.get("experience"), dict) else {},
        },
    }


def _load_file(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read catalog %s: %s", path, exc)
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


@lru_cache
def load_tourism_catalog() -> tuple[KnowledgeCard, ...]:
    settings = get_app_settings()
    root = Path(settings.tourism_data_dir)
    if not root.is_absolute():
        root = settings.project_root / root
    cards: list[KnowledgeCard] = []
    for filename, entity_type in (
        ("poi.json", "poi"),
        ("restaurant.json", "restaurant"),
        ("hotel.json", "hotel"),
    ):
        for raw in _load_file(root / filename):
            card = _card_from_entity(_flatten(raw), entity_type, None, "catalog")
            if card is None:
                continue
            if not card.region_key:
                card.region_key = catalog_region_key(card.city, card.region)
            cards.append(card)
    logger.info("Loaded %s tourism catalog cards", len(cards))
    return tuple(cards)


def card_matches_region(card: KnowledgeCard, key: str) -> bool:
    """Hard geographic gate. A Jerash day cannot admit an Irbid card."""
    wanted = region_key(key)
    if not wanted:
        return True
    accept = REGION_ACCEPT.get(wanted, {wanted})
    if card.region_key and card.region_key in accept:
        return True
    hay = f"{card.name} {card.city} {card.region}".lower()
    hinted = any(hint in hay for hint in NAME_HINTS.get(wanted, (wanted,)))
    if card.region_key:
        return hinted and card.region_key in REGION_NEIGHBORS.get(wanted, set())
    return hinted


def cards_for_region(key: str, entity_type: str | None = None) -> list[KnowledgeCard]:
    out: list[KnowledgeCard] = []
    for card in load_tourism_catalog():
        if entity_type and card.entity_type != entity_type:
            continue
        if card_matches_region(card, key):
            out.append(card)
    return out
