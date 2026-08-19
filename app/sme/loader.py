"""Load SME guide and operator files without modifying the source datasets."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

from app.config.settings import AppSettings, get_app_settings
from app.planning.geo import centroid_for, region_key
from app.sme.models import SMERecord
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _iter_json_values(text: str) -> Iterator[Any]:
    decoder = json.JSONDecoder()
    idx = 0
    length = len(text)
    while idx < length:
        while idx < length and text[idx].isspace():
            idx += 1
        if idx >= length:
            break
        try:
            value, end = decoder.raw_decode(text, idx)
        except json.JSONDecodeError:
            idx += 1
            continue
        yield value
        idx = end


def load_json_records(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8-sig")
    records: list[dict[str, Any]] = []
    for value in _iter_json_values(text):
        if isinstance(value, list):
            records.extend(item for item in value if isinstance(item, dict))
        elif isinstance(value, dict):
            records.append(value)
    return records


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _as_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def normalize_sme_record(raw: dict[str, Any]) -> SMERecord | None:
    sme_id = str(raw.get("sme_id") or "").strip()
    if not sme_id:
        return None
    profile = raw.get("business_profile") if isinstance(raw.get("business_profile"), dict) else {}
    contact = raw.get("contact") if isinstance(raw.get("contact"), dict) else {}
    location = raw.get("location") if isinstance(raw.get("location"), dict) else {}
    service_area = raw.get("service_area") if isinstance(raw.get("service_area"), dict) else {}
    languages = raw.get("languages") if isinstance(raw.get("languages"), dict) else {}
    services = raw.get("services") if isinstance(raw.get("services"), dict) else {}
    guides = raw.get("guides") if isinstance(raw.get("guides"), dict) else {}
    transport = raw.get("transportation") if isinstance(raw.get("transportation"), dict) else {}
    availability = raw.get("availability") if isinstance(raw.get("availability"), dict) else {}
    capacity = raw.get("capacity") if isinstance(raw.get("capacity"), dict) else {}
    pricing = raw.get("pricing") if isinstance(raw.get("pricing"), dict) else {}
    prefs = raw.get("preferences") if isinstance(raw.get("preferences"), dict) else {}
    reviews = raw.get("reviews") if isinstance(raw.get("reviews"), dict) else {}

    city = str(location.get("city") or "")
    region = str(location.get("region") or "")
    key = region_key(region) or region_key(city)
    centroid = centroid_for(key) or centroid_for(city)
    lat = lon = None
    precision = "unknown"
    if centroid:
        lat, lon = centroid
        precision = "city_centroid"

    sme_type = str(raw.get("sme_type") or "unknown")
    unique_id = f"{sme_type}:{sme_id}:{key or 'jordan'}"
    return SMERecord(
        sme_id=unique_id,
        source_sme_id=sme_id,
        sme_type=sme_type,
        name=str(profile.get("name") or sme_id),
        description=str(profile.get("description") or ""),
        experience_years=_as_int(profile.get("experience_years")),
        business_type=_as_list(profile.get("business_type")),
        specializations=_as_list(profile.get("specializations")),
        target_customer_types=_as_list(profile.get("target_customer_types")),
        city=city,
        region=region,
        region_key=key,
        address=str(location.get("address") or ""),
        destinations_covered=_as_list(service_area.get("destinations_covered")),
        preferred_destinations=", ".join(_as_list(service_area.get("preferred_destinations"))),
        languages=_as_list(languages.get("spoken")),
        preferred_language=str(languages.get("preferred_language") or ""),
        service_categories=_as_list(services.get("service_categories")),
        provides_guides=_as_bool(guides.get("provides_guides")),
        guide_types=_as_list(guides.get("guide_types")),
        transportation_available=_as_bool(transport.get("available")),
        working_days=_as_list(availability.get("working_days")),
        working_hours=str(availability.get("working_hours") or ""),
        min_group=_as_int(capacity.get("minimum_group_size")),
        max_group=_as_int(capacity.get("maximum_group_size")),
        private_groups=_as_bool(capacity.get("private_groups")),
        group_tours=_as_bool(capacity.get("group_tours")),
        currency=str(pricing.get("currency") or "JOD"),
        pricing_model=str(pricing.get("pricing_model") or ""),
        min_price=_as_float(pricing.get("min_price")),
        max_price=_as_float(pricing.get("max_price")),
        pricing_notes=str(pricing.get("notes") or ""),
        preferred_experience_types=_as_list(prefs.get("preferred_experience_types")),
        rating=_as_float(reviews.get("rating")),
        review_count=_as_int(reviews.get("review_count")),
        review_source=str(reviews.get("source") or ""),
        phone=str(contact.get("phone") or contact.get("mobile") or ""),
        email=str(contact.get("email") or ""),
        website=contact.get("website"),
        subscribed=bool(raw.get("subscribed") or raw.get("retour_subscriber")),
        latitude=lat,
        longitude=lon,
        geo_precision=precision,
    )


def _collect_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.json") if path.is_file())


def load_sme_catalog(data_dir: str | None = None) -> tuple[SMERecord, ...]:
    return _load_sme_catalog(data_dir)


@lru_cache
def _load_sme_catalog(data_dir: str | None = None) -> tuple[SMERecord, ...]:
    settings = get_app_settings()
    root = Path(data_dir or settings.sme_data_dir)
    if not root.is_absolute():
        root = settings.project_root / root
    records: dict[str, SMERecord] = {}
    files = _collect_files(root)
    for path in files:
        try:
            raw_rows = load_json_records(path)
        except OSError as exc:
            logger.warning("Could not read SME file %s: %s", path, exc)
            continue
        for raw in raw_rows:
            record = normalize_sme_record(raw)
            if record is None:
                continue
            records[record.sme_id] = record
    logger.info("Loaded %s unique SME records from %s files", len(records), len(files))
    return tuple(records.values())


def get_sme_by_id(sme_id: str) -> SMERecord | None:
    for record in load_sme_catalog():
        if record.sme_id == sme_id:
            return record
    return None
