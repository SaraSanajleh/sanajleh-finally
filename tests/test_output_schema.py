"""Tourism package schema and grounding tests."""

from __future__ import annotations

import json

import pytest

from app.planning.profile import normalize_tourist_profile
from app.retrieval.knowledge import KnowledgeCard, RetrievedKnowledge
from app.schemas.request.package_request import PackageRequest
from app.schemas.response.package_response import TourismPackage
from app.sme.models import SMERecord
from app.validation.package import (
    apply_profile_facts,
    ground_and_repair,
    parse_package_json,
    validate_schema,
)
from app.validators.package_response_validator import validate_tourism_package
from tests.fixtures.sample_payloads import VALID_PACKAGE_REQUEST, VALID_PACKAGE_RESPONSE


def test_warnings_without_code_are_accepted() -> None:
    payload = {
        **VALID_PACKAGE_RESPONSE,
        "warnings": [
            {"message": "No 4-star hotel in this cluster; lodging set to not_available."},
            "No matching restaurant for dinner.",
        ],
    }
    package = TourismPackage.model_validate(payload)
    assert package.warnings[0].code == "note"
    assert "4-star" in package.warnings[0].message
    assert package.warnings[1].message.startswith("No matching")


def test_valid_package_schema() -> None:
    package = TourismPackage.model_validate(VALID_PACKAGE_RESPONSE)
    assert package.trip_title == "Anniversary Jordan Discovery"
    assert package.days[0].schedule[0].item_id == "poi_test_petra"


def test_malformed_llm_json_is_rejected() -> None:
    with pytest.raises(Exception):
        validate_tourism_package("sorry I cannot help with that")


def test_parse_recovers_days_key() -> None:
    payload = parse_package_json(json.dumps(VALID_PACKAGE_RESPONSE))
    package = validate_schema(payload)
    assert len(package.days) == 1


def test_ungrounded_items_are_removed() -> None:
    request = PackageRequest.model_validate(VALID_PACKAGE_REQUEST)
    profile = normalize_tourist_profile(request)
    package = apply_profile_facts(TourismPackage.model_validate(VALID_PACKAGE_RESPONSE), profile)
    knowledge = RetrievedKnowledge(
        status="ok",
        pois=[
            KnowledgeCard(
                item_id="poi_test_petra",
                entity_type="poi",
                name="Petra Visitor Center",
                region="Ma'an Governorate",
            )
        ],
    )
    sme_index = {
        "SME-000001": SMERecord(
            sme_id="SME-000001",
            source_sme_id="SME-000001",
            sme_type="tour_guide",
            name="Ahmad Momani",
            city="Ajloun",
            region="Ajloun Governorate",
        )
    }
    data = package.model_dump(mode="python")
    data["days"][0]["schedule"].append(
        {
            "type": "poi",
            "item_id": "FAKE-999",
            "name": "Invented Castle",
            "location": "Narnia",
        }
    )
    package = TourismPackage.model_validate(data)
    repaired, _ = ground_and_repair(package, profile, knowledge, sme_index, [])
    names = [item.name for item in repaired.days[0].schedule]
    assert "Invented Castle" not in names
    assert "Petra Visitor Center" in names


def test_avoided_item_is_stripped() -> None:
    payload = {**VALID_PACKAGE_REQUEST}
    payload["preferences"] = {
        **VALID_PACKAGE_REQUEST["preferences"],
        "placesToAvoid": "Petra",
    }
    request = PackageRequest.model_validate(payload)
    profile = normalize_tourist_profile(request)
    package = apply_profile_facts(TourismPackage.model_validate(VALID_PACKAGE_RESPONSE), profile)
    knowledge = RetrievedKnowledge(
        status="ok",
        pois=[
            KnowledgeCard(
                item_id="poi_test_petra",
                entity_type="poi",
                name="Petra Visitor Center",
                region="Ma'an Governorate",
            )
        ],
    )
    repaired, _ = ground_and_repair(package, profile, knowledge, {}, [])
    assert repaired.days[0].schedule == []
    assert any(w.code == "avoided_item_removed" for w in repaired.warnings)


def test_day_count_is_enforced() -> None:
    request = PackageRequest.model_validate(VALID_PACKAGE_REQUEST)
    profile = normalize_tourist_profile(request)
    package = apply_profile_facts(TourismPackage.model_validate(VALID_PACKAGE_RESPONSE), profile)
    knowledge = RetrievedKnowledge(status="ok")
    repaired, errors = ground_and_repair(package, profile, knowledge, {}, [])
    assert len(repaired.days) == 6
    assert errors
