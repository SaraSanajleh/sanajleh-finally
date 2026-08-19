"""Match one guide and one operator to the whole package — never one SME per day."""

from __future__ import annotations

from collections import defaultdict

from app.config.settings import AppSettings, get_app_settings
from app.planning.geo import region_key, regions_mentioned, wizard_region_keys
from app.planning.profile import TouristProfile
from app.sme.loader import load_sme_catalog
from app.sme.models import SMEMatch, SMERecord

INTEREST_ALIASES: dict[str, tuple[str, ...]] = {
    "history": ("history", "heritage", "historical", "culture"),
    "archaeology": ("archaeology", "archaeological", "heritage", "history"),
    "nature": ("nature", "forest", "eco", "wildlife", "hiking"),
    "hiking": ("hiking", "trekking", "nature", "adventure"),
    "adventure": ("adventure", "hiking", "trekking", "desert"),
    "desert": ("desert", "wadi rum", "bedouin"),
    "culture": ("culture", "cultural", "heritage", "local"),
    "food": ("food", "cuisine", "culinary", "gastronomy"),
    "local_experiences": ("local", "community", "authentic", "experience"),
    "eco_tourism": ("eco", "nature", "sustainable", "community"),
    "wildlife": ("wildlife", "nature", "birds"),
    "beaches": ("beach", "aqaba", "red sea", "diving", "snorkel"),
    "religious_sites": ("religious", "church", "mosque", "pilgrim", "biblical"),
    "museums": ("museum", "heritage", "history"),
    "photography": ("photography", "scenic", "views"),
    "wellness": ("wellness", "spa", "dead sea"),
    "camping": ("camp", "desert", "nature"),
}

GROUP_ALIASES: dict[str, tuple[str, ...]] = {
    "solo": ("solo", "individual"),
    "couple": ("couple", "couples", "romantic"),
    "family": ("family", "families", "children"),
    "friends": ("friends", "group", "groups"),
    "business": ("business", "corporate"),
}


def _blob(record: SMERecord) -> str:
    parts = [
        record.name,
        record.description,
        record.city,
        record.region,
        record.preferred_destinations,
        " ".join(record.specializations),
        " ".join(record.service_categories),
        " ".join(record.preferred_experience_types),
        " ".join(record.destinations_covered),
        " ".join(record.business_type),
    ]
    return " ".join(parts).lower()


def _covered_regions(record: SMERecord) -> set[str]:
    keys = set()
    if record.region_key:
        keys.add(record.region_key)
    city_key = region_key(record.city)
    if city_key:
        keys.add(city_key)
    keys.update(
        regions_mentioned(
            " ".join(
                [
                    record.preferred_destinations,
                    record.description,
                    record.city,
                    record.region,
                    *record.destinations_covered,
                ]
            )
        )
    )
    return {key for key in keys if key}


def score_sme(
    record: SMERecord,
    profile: TouristProfile,
    settings: AppSettings,
    route_keys: list[str] | None = None,
) -> SMEMatch | None:
    hay = _blob(record)
    factors: dict[str, float] = {}
    reasons: list[str] = []
    trip_keys = {key for key in (route_keys or profile.region_keys) if key}
    must_keys = wizard_region_keys(profile.must_visit)
    covered = _covered_regions(record)
    overlap = covered & trip_keys if trip_keys else covered

    if trip_keys and not overlap:
        return None

    coverage = len(overlap) / max(len(trip_keys), 1) if trip_keys else 0.6
    must_hit = (len(overlap & must_keys) / max(len(must_keys), 1)) if must_keys else coverage
    factors["coverage"] = min(1.0, 0.65 * coverage + 0.35 * must_hit)
    if overlap:
        reasons.append("Covers " + ", ".join(sorted(overlap)))

    if record.region_key in trip_keys or region_key(record.city) in trip_keys:
        factors["location"] = 1.0
        reasons.append(f"Based in {record.city or record.region}")
    else:
        factors["location"] = 0.55 * coverage

    spec_blob = " ".join(record.specializations + record.preferred_experience_types).lower()
    interest_hits: list[str] = []
    strong_hits: list[str] = []
    for interest in profile.interests:
        aliases = INTEREST_ALIASES.get(interest.lower(), (interest.lower(),))
        if any(alias in spec_blob for alias in aliases):
            strong_hits.append(interest)
            interest_hits.append(interest)
        elif any(alias in hay for alias in aliases):
            interest_hits.append(interest)
    if profile.interests:
        factors["interests"] = min(
            1.0,
            (0.8 * len(strong_hits) + 0.35 * len(interest_hits)) / max(len(profile.interests), 1),
        )
        if not interest_hits:
            factors["interests"] = min(factors["interests"], 0.12)
    else:
        factors["interests"] = 0.4
    if interest_hits:
        reasons.insert(0, "Fits what you asked for: " + ", ".join(interest_hits[:4]))

    group_aliases = GROUP_ALIASES.get(profile.group_type, (profile.group_type,))
    targets = " ".join(record.target_customer_types).lower()
    if any(alias in targets for alias in group_aliases):
        factors["traveler"] = 1.0
        reasons.append(f"Works with {profile.group_type} travelers")
    elif profile.has_children and "famil" in targets:
        factors["traveler"] = 0.9
        reasons.append("Family-oriented")
    else:
        factors["traveler"] = 0.35

    lang = profile.preferred_language.lower()
    spoken = " ".join(record.languages).lower()
    if lang and lang in spoken:
        factors["language"] = 1.0
        reasons.append(f"Speaks {profile.preferred_language}")
    elif spoken:
        factors["language"] = 0.4
    else:
        factors["language"] = 0.0

    party = profile.total_travelers
    if record.min_group is not None and party < record.min_group:
        factors["capacity"] = 0.0
    elif record.max_group is not None and party > record.max_group:
        factors["capacity"] = 0.15
        reasons.append("Group size may exceed usual capacity")
    else:
        factors["capacity"] = 1.0

    pref_score = 0.0
    pref_hits = 0
    for pref in profile.sme_preferences:
        key = pref.lower()
        if "highly rated" in key and record.rating is not None and record.rating >= 4.5:
            pref_score += 1.0
            pref_hits += 1
            reasons.append("Highly rated in the SME directory")
        elif "eco" in key and any(token in hay for token in ("eco", "nature", "sustainable")):
            pref_score += 1.0
            pref_hits += 1
            reasons.append("Nature / eco-aligned services")
        elif "community" in key and any(token in hay for token in ("community", "local", "village")):
            pref_score += 1.0
            pref_hits += 1
            reasons.append("Community-based tourism signals")
        elif "luxury" in key and "luxury" in hay:
            pref_score += 1.0
            pref_hits += 1
            reasons.append("Luxury services listed")
        elif "family-owned" in key and any(token in hay for token in ("freelance", "family", "local")):
            pref_score += 0.6
            pref_hits += 1
    factors["sme_preferences"] = (pref_score / pref_hits) if pref_hits else 0.0

    if profile.ai_priority == "authentic" and any(token in hay for token in ("local", "heritage", "culture")):
        factors["priority"] = 0.8
    elif profile.ai_priority == "family" and ("famil" in targets or profile.has_children):
        factors["priority"] = 0.8
    elif profile.ai_priority == "sustainable" and any(token in hay for token in ("eco", "nature")):
        factors["priority"] = 0.8
    else:
        factors["priority"] = 0.3

    multi_region = len(trip_keys) > 1
    if record.sme_type == "tour_operator" and record.transportation_available and multi_region:
        factors["logistics"] = 1.0
        reasons.append("Transportation across the itinerary")
    elif record.sme_type == "tour_operator" and record.transportation_available:
        factors["logistics"] = 0.7
    else:
        factors["logistics"] = 0.2 if record.sme_type == "tour_operator" else 0.0

    if record.sme_type == "tour_operator":
        weights = {
            "coverage": 0.26,
            "location": 0.10,
            "logistics": 0.16,
            "interests": 0.22,
            "traveler": 0.10,
            "capacity": 0.06,
            "language": 0.04,
            "sme_preferences": 0.04,
            "priority": 0.02,
        }
    else:
        weights = {
            "coverage": 0.16,
            "location": 0.12,
            "interests": 0.34,
            "traveler": 0.12,
            "language": 0.10,
            "capacity": 0.06,
            "sme_preferences": 0.06,
            "priority": 0.04,
            "logistics": 0.0,
        }

    relevance = sum(factors.get(key, 0.0) * weight for key, weight in weights.items())
    boost = 0.0
    if record.subscribed and relevance >= settings.sme_min_match_score:
        boost = min(settings.sme_subscription_boost_cap, 0.05)
        reasons.append("Participating ReTour partner (relevance still required)")
    score = min(1.0, relevance + boost)
    if score < settings.sme_min_match_score:
        return None

    if record.sme_type == "tour_guide":
        role = "Trip guide"
        package_role = "guide"
    elif record.sme_type == "tour_operator":
        role = "Trip operator"
        package_role = "operator"
    else:
        role = record.sme_type.replace("_", " ").title()
        package_role = record.sme_type

    return SMEMatch(
        record=record,
        score=score,
        factors=factors,
        reasons=reasons[:8],
        role=role,
        covers_regions=sorted(overlap),
        package_role=package_role,
    )


def match_smes(
    profile: TouristProfile,
    settings: AppSettings | None = None,
    limit: int = 16,
    route_keys: list[str] | None = None,
) -> list[SMEMatch]:
    """Ranked candidates for search/debug. Package generation uses select_package_smes."""
    settings = settings or get_app_settings()
    matches: list[SMEMatch] = []
    for record in load_sme_catalog():
        match = score_sme(record, profile, settings, route_keys=route_keys)
        if match is not None:
            matches.append(match)
    matches.sort(key=lambda item: item.score, reverse=True)

    selected: list[SMEMatch] = []
    type_counts: dict[str, int] = defaultdict(int)
    city_counts: dict[str, int] = defaultdict(int)
    for match in matches:
        if type_counts[match.record.sme_type] >= max(limit // 2, 3) and len(selected) >= 4:
            continue
        if city_counts[match.record.city] >= 3:
            continue
        selected.append(match)
        type_counts[match.record.sme_type] += 1
        city_counts[match.record.city] += 1
        if len(selected) >= limit:
            break
    return selected


def _best_of_type(matches: list[SMEMatch], sme_type: str) -> SMEMatch | None:
    pool = [item for item in matches if item.record.sme_type == sme_type]
    if not pool:
        return None
    if sme_type == "tour_guide":
        return max(
            pool,
            key=lambda item: (
                item.factors.get("interests", 0.0),
                item.score,
                len(item.covers_regions),
                item.record.experience_years or 0,
            ),
        )
    return max(
        pool,
        key=lambda item: (
            item.factors.get("coverage", 0.0),
            item.factors.get("logistics", 0.0),
            item.factors.get("interests", 0.0),
            item.score,
        ),
    )


def select_package_smes(
    profile: TouristProfile,
    settings: AppSettings | None = None,
    route_keys: list[str] | None = None,
) -> list[SMEMatch]:
    """Exactly one tour guide and one tour operator for the whole package."""
    settings = settings or get_app_settings()
    ranked: list[SMEMatch] = []
    for record in load_sme_catalog():
        match = score_sme(record, profile, settings, route_keys=route_keys)
        if match is not None:
            ranked.append(match)
    team = [item for item in (_best_of_type(ranked, "tour_guide"), _best_of_type(ranked, "tour_operator")) if item]
    return team


def sme_catalog_index() -> dict[str, SMERecord]:
    return {record.sme_id: record for record in load_sme_catalog()}
