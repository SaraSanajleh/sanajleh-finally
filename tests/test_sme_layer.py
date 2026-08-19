"""SME loader and matching tests — no hallucinated businesses."""

from __future__ import annotations

from app.planning.profile import normalize_tourist_profile
from app.schemas.request.package_request import PackageRequest
from app.sme.loader import load_json_records, load_sme_catalog, normalize_sme_record
from app.sme.matcher import match_smes, score_sme, select_package_smes
from app.config.settings import get_app_settings
from tests.fixtures.sample_payloads import VALID_PACKAGE_REQUEST


def test_sme_catalog_loads_guides_and_operators() -> None:
    catalog = load_sme_catalog()
    assert len(catalog) >= 200
    types = {record.sme_type for record in catalog}
    assert "tour_guide" in types
    assert all(":SME-" in record.sme_id for record in catalog)


def test_concatenated_json_repair_does_not_change_source(tmp_path) -> None:
    path = tmp_path / "broken.json"
    path.write_text(
        '[{"sme_id":"SME-A","sme_type":"tour_guide","business_profile":{"name":"A"}}]'
        '[{"sme_id":"SME-B","sme_type":"tour_operator","business_profile":{"name":"B"}}]',
        encoding="utf-8",
    )
    rows = load_json_records(path)
    assert {row["sme_id"] for row in rows} == {"SME-A", "SME-B"}


def test_irrelevant_sme_is_excluded() -> None:
    request = PackageRequest.model_validate(VALID_PACKAGE_REQUEST)
    profile = normalize_tourist_profile(request)
    raw = {
        "sme_id": "SME-IRRELEVANT",
        "sme_type": "tour_guide",
        "business_profile": {
            "name": "Zarqa City Walker",
            "specializations": ["Shopping"],
            "target_customer_types": ["Business"],
        },
        "location": {"city": "Zarqa", "region": "Zarqa Governorate"},
        "service_area": {"destinations_covered": ["Zarqa"], "preferred_destinations": "Zarqa"},
        "languages": {"spoken": ["Arabic"]},
    }
    record = normalize_sme_record(raw)
    assert record is not None
    match = score_sme(record, profile, get_app_settings())
    assert match is None


def test_relevant_guide_can_match_northern_family_trip() -> None:
    payload = {**VALID_PACKAGE_REQUEST}
    payload["trip"] = {
        **VALID_PACKAGE_REQUEST["trip"],
        "preferredRegions": ["Ajloun", "Jerash"],
        "duration": "3",
    }
    payload["preferences"] = {
        **VALID_PACKAGE_REQUEST["preferences"],
        "interests": ["history", "nature", "hiking"],
        "mustVisit": ["Ajloun", "Jerash"],
        "placesToAvoid": "",
    }
    payload["travelers"] = {
        **VALID_PACKAGE_REQUEST["travelers"],
        "groupType": "family",
        "children": 1,
        "childrenAges": ["8"],
    }
    request = PackageRequest.model_validate(payload)
    profile = normalize_tourist_profile(request)
    matches = match_smes(profile, limit=8)
    assert matches
    assert all(":SME-" in m.record.sme_id for m in matches)
    assert all(m.score >= 0.35 for m in matches)
    assert all(m.reasons for m in matches)
    assert any(m.record.known_for() for m in matches)
    assert any(m.record.spec_rows() for m in matches)


def test_package_gets_one_guide_and_one_operator() -> None:
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "preferredRegions": ["Ajloun", "Jerash"],
            "duration": "3",
        },
        "preferences": {
            **VALID_PACKAGE_REQUEST["preferences"],
            "interests": ["history", "nature", "hiking"],
            "mustVisit": ["Ajloun", "Jerash"],
            "placesToAvoid": "",
        },
        "travelers": {
            **VALID_PACKAGE_REQUEST["travelers"],
            "groupType": "family",
            "children": 1,
            "childrenAges": ["8"],
        },
    }
    profile = normalize_tourist_profile(PackageRequest.model_validate(payload))
    team = select_package_smes(profile)
    types = [item.record.sme_type for item in team]
    assert types.count("tour_guide") == 1
    assert types.count("tour_operator") == 1
    assert len(team) == 2
    assert all(item.covers_regions for item in team)
    guide = next(item for item in team if item.record.sme_type == "tour_guide")
    assert any("asked for" in reason.lower() or "fits" in reason.lower() for reason in guide.reasons)
    assert not any(reason.lower().startswith("distinguished by") for reason in guide.reasons)
    known = guide.record.known_for()
    assert known
    assert not any("years specializing" in line.lower() for line in known)
