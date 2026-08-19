from app.planning.profile import normalize_tourist_profile
from app.retrieval.knowledge import KnowledgeCard
from app.retrieval.query import DayRetrievalQuery
from app.retrieval.ranker import belongs_to_region, collapse_same_site, score_card
from app.schemas.request.package_request import PackageRequest
from tests.fixtures.sample_payloads import VALID_PACKAGE_REQUEST


def _profile():
    payload = {
        **VALID_PACKAGE_REQUEST,
        "trip": {
            **VALID_PACKAGE_REQUEST["trip"],
            "duration": "3",
            "preferredRegions": ["Ajloun", "Jerash"],
        },
        "preferences": {
            **VALID_PACKAGE_REQUEST["preferences"],
            "interests": ["history", "culture"],
            "mustVisit": ["Jerash"],
        },
    }
    return normalize_tourist_profile(PackageRequest.model_validate(payload))


def _query(**kwargs) -> DayRetrievalQuery:
    data = {
        "day": 2,
        "region": "Jerash",
        "region_key": "jerash",
        "theme": "Jerash",
        "is_must_visit": True,
        "sights": 3,
        "meals": 2,
        "interests": ["history", "culture"],
    }
    data.update(kwargs)
    return DayRetrievalQuery.model_validate(data)


def test_irbid_souq_cannot_score_on_a_jerash_day() -> None:
    profile = _profile()
    query = _query()
    irbid = KnowledgeCard(
        item_id="poi_010020",
        entity_type="poi",
        name="Irbid Central Souq",
        region="Irbid Governorate",
        city="Irbid",
        region_key="irbid",
        summary="Market in Irbid",
    )
    jerash = KnowledgeCard(
        item_id="poi_jerash_site",
        entity_type="poi",
        name="Jerash Archaeological Site",
        region="Jerash Governorate",
        city="Jerash",
        region_key="jerash",
        summary="Roman ruins and the Oval Plaza",
        facts={"themes": ["Roman", "heritage"]},
    )
    assert belongs_to_region(irbid, "jerash") is False
    assert score_card(irbid, profile, query) is None
    ranked = score_card(jerash, profile, query)
    assert ranked is not None
    assert ranked.relevance > 0.5
    assert any("Jerash" in reason or "must-see" in reason.lower() for reason in ranked.why_selected)


def test_irbid_card_named_jerash_still_rejected() -> None:
    profile = _profile()
    fake = KnowledgeCard(
        item_id="poi_fake",
        entity_type="poi",
        name="Jerash Grill Irbid",
        region="Irbid Governorate",
        city="Irbid",
        region_key="irbid",
        summary="Restaurant in Irbid",
    )
    assert belongs_to_region(fake, "jerash") is False
    assert score_card(fake, profile, _query()) is None


def test_same_site_monuments_collapse_to_one_visit() -> None:
    site = KnowledgeCard(
        item_id="poi_site",
        entity_type="poi",
        name="Jerash Archaeological Site",
        region_key="jerash",
        relevance=0.9,
        facts={"visit_minutes": 180},
    )
    hip = KnowledgeCard(
        item_id="poi_hip",
        entity_type="poi",
        name="Hippodrome of Jerash",
        region_key="jerash",
        relevance=0.7,
        facts={"visit_minutes": 40},
    )
    theater = KnowledgeCard(
        item_id="poi_th",
        entity_type="poi",
        name="South Theater of Jerash",
        region_key="jerash",
        relevance=0.68,
        facts={"visit_minutes": 40},
    )
    collapsed = collapse_same_site([site, hip, theater])
    assert len(collapsed) == 1
    assert collapsed[0].item_id == "poi_site"


def test_stadium_is_not_a_religious_or_museum_stop() -> None:
    profile = _profile()
    query = _query(region="Karak", region_key="karak", interests=["religious_sites", "museums"])
    stadium = KnowledgeCard(
        item_id="poi_stadium",
        entity_type="poi",
        name="Al-Karak Municipal Stadium",
        region="Karak Governorate",
        city="Karak",
        region_key="karak",
        summary="Regional sports stadium hosting football matches",
        category="Sports",
    )
    shrine = KnowledgeCard(
        item_id="poi_shrine",
        entity_type="poi",
        name="Shrine of Prophet Noah",
        region="Karak Governorate",
        city="Karak",
        region_key="karak",
        summary="Traditional religious shrine",
        category="Religious Site",
    )
    castle = KnowledgeCard(
        item_id="poi_castle",
        entity_type="poi",
        name="Karak Castle",
        region="Karak Governorate",
        city="Karak",
        region_key="karak",
        summary="Crusader castle above Al-Karak",
        category="Heritage",
    )
    assert score_card(stadium, profile, query) is None
    ranked_shrine = score_card(shrine, profile, query)
    ranked_castle = score_card(castle, profile, query)
    assert ranked_shrine is not None
    assert ranked_castle is not None
    assert ranked_castle.relevance > ranked_shrine.relevance
