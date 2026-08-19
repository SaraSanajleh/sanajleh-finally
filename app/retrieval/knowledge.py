"""Compress retriever clusters into grounded catalog cards for the planner."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.planning.constraints import item_is_avoided
from app.planning.geo import catalog_region_key, centroid_for, extract_coordinates
from app.planning.profile import TouristProfile
from app.config.settings import AppSettings, get_app_settings


class KnowledgeCard(BaseModel):
    item_id: str
    entity_type: str
    name: str
    region: str = ""
    city: str = ""
    region_key: str = ""
    category: str = ""
    summary: str = ""
    latitude: float | None = None
    longitude: float | None = None
    geo_precision: str = "unknown"
    why_retrieved: list[str] = Field(default_factory=list)
    why_selected: list[str] = Field(default_factory=list)
    relevance: float = 0.0
    facts: dict[str, Any] = Field(default_factory=dict)
    cluster_id: int | None = None
    cluster_theme: str = ""
    indoor_outdoor: str = ""

    def prompt_card(self) -> dict[str, Any]:
        return {
            "id": self.item_id,
            "type": self.entity_type,
            "name": self.name,
            "region": self.region,
            "city": self.city,
            "region_key": self.region_key,
            "category": self.category,
            "summary": self.summary,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "geo_precision": self.geo_precision,
            "why_retrieved": self.why_retrieved[:4],
            "why_selected": self.why_selected[:4],
            "relevance": round(self.relevance, 3),
            "facts": self.facts,
            "nearby_restaurant_ids": list(self.facts.get("nearby_restaurant_ids") or [])[:4],
            "nearby_poi_km": self.facts.get("nearby_poi_km") or {},
            "cluster_id": self.cluster_id,
            "cluster_theme": self.cluster_theme,
        }


class DayShortlist(BaseModel):
    day: int
    region: str
    region_key: str
    theme: str = ""
    pois: list[KnowledgeCard] = Field(default_factory=list)
    restaurants: list[KnowledgeCard] = Field(default_factory=list)
    hotels: list[KnowledgeCard] = Field(default_factory=list)


class RetrievedKnowledge(BaseModel):
    status: str = "unknown"
    duration_days: int | None = None
    planning_lock: str = ""
    pois: list[KnowledgeCard] = Field(default_factory=list)
    restaurants: list[KnowledgeCard] = Field(default_factory=list)
    hotels: list[KnowledgeCard] = Field(default_factory=list)
    clusters: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    day_shortlists: list[DayShortlist] = Field(default_factory=list)

    def id_index(self) -> dict[str, KnowledgeCard]:
        cards: dict[str, KnowledgeCard] = {}
        for card in (*self.pois, *self.restaurants, *self.hotels):
            cards[card.item_id] = card
            cards[card.name.lower()] = card
        return cards

    def prompt_dict(self, settings: AppSettings | None = None) -> dict[str, Any]:
        settings = settings or get_app_settings()
        return {
            "status": self.status,
            "planning_lock": self.planning_lock,
            "clusters": self.clusters,
            "pois": [c.prompt_card() for c in self.pois[: settings.retrieval_max_pois_prompt]],
            "restaurants": [
                c.prompt_card() for c in self.restaurants[: settings.retrieval_max_restaurants_prompt]
            ],
            "hotels": [c.prompt_card() for c in self.hotels[: settings.retrieval_max_hotels_prompt]],
            "day_shortlists": [
                {
                    "day": item.day,
                    "region": item.region,
                    "theme": item.theme,
                    "pois": [c.prompt_card() for c in item.pois],
                    "restaurants": [c.prompt_card() for c in item.restaurants],
                    "hotels": [c.prompt_card() for c in item.hotels],
                }
                for item in self.day_shortlists
            ],
        }


def _first_present(*values: Any) -> Any:
    """Keep 0 (free entry) and skip only empty/missing values."""
    for value in values:
        if value not in (None, "", []):
            return value
    return None


def _card_from_entity(
    entity: dict[str, Any],
    entity_type: str,
    cluster_id: int | None,
    theme: str,
    profile: TouristProfile | None = None,
) -> KnowledgeCard | None:
    item_id = str(entity.get("id") or entity.get("item_id") or "").strip()
    name = str(entity.get("name") or "").strip()
    if not item_id and not name:
        return None
    region = str(entity.get("region") or "")
    city = str(entity.get("city") or "")
    if profile is not None and item_is_avoided(name, region, city, profile):
        return None
    facts = entity.get("facts") if isinstance(entity.get("facts"), dict) else {}
    lat, lon = extract_coordinates(entity)
    precision = "unknown"
    if lat is None:
        lat, lon = extract_coordinates(facts)
    if lat is not None:
        precision = "exact"
    else:
        fallback = centroid_for(city) or centroid_for(region)
        if fallback:
            lat, lon = fallback
            precision = "city_centroid"
    identity = facts.get("identity") if isinstance(facts.get("identity"), dict) else {}
    semantic = facts.get("semantic") if isinstance(facts.get("semantic"), dict) else {}
    operation = facts.get("operation") if isinstance(facts.get("operation"), dict) else {}
    pricing = facts.get("pricing") if isinstance(facts.get("pricing"), dict) else {}
    audience = facts.get("audience") if isinstance(facts.get("audience"), dict) else {}
    experience = facts.get("experience") if isinstance(facts.get("experience"), dict) else {}
    compact_facts = {
        "category": identity.get("category") or entity.get("category") or "",
        "subcategory": identity.get("subcategory") or "",
        "themes": semantic.get("themes") or [],
        "visit_minutes": _first_present(
            operation.get("average_visit_minutes"),
            operation.get("average_dining_minutes"),
            facts.get("average_visit_minutes"),
            facts.get("average_dining_minutes"),
            facts.get("visit_minutes"),
            entity.get("average_visit_minutes"),
        ),
        "opening_hours": _first_present(
            operation.get("opening_hours"),
            facts.get("opening_hours"),
        ),
        "entry_fee": _first_present(pricing.get("entry_fee"), facts.get("entry_fee")),
        "night_price": _first_present(
            pricing.get("average_price_per_night"),
            facts.get("average_price_per_night"),
            facts.get("night_price"),
        ),
        "meal_price": _first_present(
            pricing.get("average_cost_per_person"),
            facts.get("average_cost_per_person"),
            facts.get("meal_price"),
        ),
        "currency": _first_present(pricing.get("currency"), facts.get("currency")),
        "price_level": _first_present(pricing.get("pricing_level"), facts.get("pricing_level")),
        "suitable_for": audience.get("suitable_for") or facts.get("suitable_for") or [],
        "accessibility": audience.get("accessibility") or audience.get("accessibility_level"),
        "indoor_outdoor": experience.get("indoor_outdoor") or facts.get("indoor_outdoor"),
        "star_rating": experience.get("star_rating") or facts.get("star_rating"),
        "cuisine_types": experience.get("cuisine_types") or facts.get("cuisine_types") or [],
        "closing_hours": _first_present(operation.get("closing_hours"), facts.get("closing_hours")),
        "highlights": experience.get("highlights") or facts.get("highlights") or [],
        "activity_level": experience.get("activity_level") or facts.get("activity_level"),
        "best_visit_time": experience.get("best_visit_time") or facts.get("best_visit_time") or [],
        "role": entity.get("role") or facts.get("role"),
    }
    compact_facts = {k: v for k, v in compact_facts.items() if v not in (None, "", [])}
    indoor = str(compact_facts.get("indoor_outdoor") or "")
    highlights = compact_facts.get("highlights") if isinstance(compact_facts.get("highlights"), list) else []
    summary = str(semantic.get("summary") or entity.get("summary") or "")[:280]
    if not summary and highlights:
        summary = str(highlights[0])[:280]
    return KnowledgeCard(
        item_id=item_id or name,
        entity_type=entity_type,
        name=name or item_id,
        region=region,
        city=city,
        region_key=catalog_region_key(city, region),
        indoor_outdoor=indoor,
        category=str(compact_facts.get("category") or entity.get("category") or ""),
        summary=summary,
        latitude=lat,
        longitude=lon,
        geo_precision=precision,
        why_retrieved=list(entity.get("why_retrieved") or [])[:6],
        facts=compact_facts,
        cluster_id=cluster_id,
        cluster_theme=theme,
    )


def overlay_retrieved_evidence(catalog: KnowledgeCard, retrieved: KnowledgeCard) -> KnowledgeCard:
    """Catalog keeps identity. Retriever average_visit_minutes set the POI clock."""
    facts = dict(catalog.facts)
    for key, value in retrieved.facts.items():
        if value in (None, "", [], {}):
            continue
        if key in {
            "nearby_restaurant_ids",
            "nearby_poi_km",
            "retrieved",
            "retrieval_rank",
            "role",
            "highlights",
            "best_visit_time",
        }:
            facts[key] = value
        elif key == "visit_minutes":
            try:
                minutes = int(round(float(value)))
            except (TypeError, ValueError):
                continue
            if minutes > 0:
                facts[key] = minutes
        elif key not in facts or facts[key] in (None, "", []):
            facts[key] = value
    facts["retrieved"] = True
    why = list(dict.fromkeys([*(retrieved.why_retrieved or []), *(catalog.why_retrieved or [])]))
    lat, lon, precision = catalog.latitude, catalog.longitude, catalog.geo_precision
    if catalog.geo_precision != "exact" and retrieved.geo_precision == "exact":
        lat, lon, precision = retrieved.latitude, retrieved.longitude, retrieved.geo_precision
    return catalog.model_copy(
        update={
            "why_retrieved": why[:8],
            "facts": facts,
            "summary": catalog.summary or retrieved.summary,
            "indoor_outdoor": catalog.indoor_outdoor or retrieved.indoor_outdoor,
            "latitude": lat,
            "longitude": lon,
            "geo_precision": precision,
            "category": catalog.category or retrieved.category,
        }
    )


def _distance_rows(slot: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for row in slot.get("distances_to_others") or []:
        if not isinstance(row, dict):
            continue
        poi_id = str(row.get("poi_id") or "").strip()
        try:
            km = float(row.get("km"))
        except (TypeError, ValueError):
            continue
        if poi_id:
            out[poi_id] = km
    return out


def _attach_retrieval(card: KnowledgeCard, **extra: Any) -> KnowledgeCard:
    facts = dict(card.facts)
    for key, value in extra.items():
        if value not in (None, "", [], {}):
            facts[key] = value
    facts["retrieved"] = True
    return card.model_copy(update={"facts": facts})


def _entity_from_slot(slot: Any) -> dict[str, Any] | None:
    if not isinstance(slot, dict):
        return None
    if isinstance(slot.get("poi"), dict):
        poi = dict(slot["poi"])
        if slot.get("restaurants"):
            poi["_nearby_restaurants"] = slot.get("restaurants")
        return poi
    return slot


def compress_knowledge(
    raw: dict[str, Any],
    profile: TouristProfile,
    settings: AppSettings | None = None,
) -> RetrievedKnowledge:
    settings = settings or get_app_settings()
    meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
    status = str(meta.get("rag_status") or "unknown")
    pois: list[KnowledgeCard] = []
    restaurants: list[KnowledgeCard] = []
    hotels: list[KnowledgeCard] = []
    cluster_summaries: list[dict[str, Any]] = []
    seen: set[str] = set()

    for cluster in raw.get("clusters") or []:
        if not isinstance(cluster, dict):
            continue
        cid = cluster.get("cluster_id")
        theme = str(cluster.get("theme") or "")
        cluster_pois: list[str] = []
        for index, slot in enumerate(cluster.get("pois") or []):
            entity = _entity_from_slot(slot)
            if not entity:
                continue
            card = _card_from_entity(entity, "poi", cid, theme, profile)
            nearby_ids: list[str] = []
            slot_dict = slot if isinstance(slot, dict) else {}
            for rest in slot_dict.get("restaurants") or []:
                if not isinstance(rest, dict):
                    continue
                rcard = _card_from_entity(rest, "restaurant", cid, theme, profile)
                if rcard is None:
                    continue
                nearby_ids.append(rcard.item_id)
                if rcard.item_id not in seen:
                    seen.add(rcard.item_id)
                    restaurants.append(_attach_retrieval(rcard, retrieval_rank=index))
            if card and card.item_id not in seen:
                seen.add(card.item_id)
                card = _attach_retrieval(
                    card,
                    nearby_restaurant_ids=nearby_ids,
                    nearby_poi_km=_distance_rows(slot_dict),
                    retrieval_rank=index,
                    role=entity.get("role"),
                )
                pois.append(card)
                cluster_pois.append(card.name)
            elif card and nearby_ids:
                existing = next((item for item in pois if item.item_id == card.item_id), None)
                if existing is not None:
                    merged = dict(existing.facts)
                    merged["nearby_restaurant_ids"] = list(
                        dict.fromkeys([*(merged.get("nearby_restaurant_ids") or []), *nearby_ids])
                    )
                    dists = dict(merged.get("nearby_poi_km") or {})
                    dists.update(_distance_rows(slot_dict))
                    merged["nearby_poi_km"] = dists
                    pois[pois.index(existing)] = existing.model_copy(update={"facts": merged})
        for hotel in cluster.get("hotels") or []:
            if not isinstance(hotel, dict):
                continue
            hcard = _card_from_entity(hotel, "hotel", cid, theme, profile)
            if hcard and hcard.item_id not in seen:
                seen.add(hcard.item_id)
                hotels.append(hcard)
        cluster_summaries.append(
            {
                "cluster_id": cid,
                "theme": theme,
                "summary": str(cluster.get("summary") or ""),
                "poi_names": cluster_pois[:8],
            }
        )

    warnings: list[str] = []
    if status in {"unavailable", "disabled"}:
        warnings.append("Tourism knowledge retrieval was unavailable. Do not invent catalog items.")
    if not pois:
        warnings.append("No matching POIs were retrieved.")
    if not restaurants:
        warnings.append("No matching restaurants were retrieved.")
    if not hotels:
        warnings.append("No matching hotels were retrieved.")

    return RetrievedKnowledge(
        status=status,
        duration_days=raw.get("duration_days"),
        planning_lock=str(meta.get("planning_lock") or ""),
        pois=pois,
        restaurants=restaurants,
        hotels=hotels,
        clusters=cluster_summaries,
        warnings=warnings,
    )
