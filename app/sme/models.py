"""SME candidate and match models. Only fields supported by the datasets."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SMERecord(BaseModel):
    sme_id: str
    source_sme_id: str = ""
    sme_type: str
    name: str
    description: str = ""
    experience_years: int | None = None
    business_type: list[str] = Field(default_factory=list)
    specializations: list[str] = Field(default_factory=list)
    target_customer_types: list[str] = Field(default_factory=list)
    city: str = ""
    region: str = ""
    region_key: str = ""
    address: str = ""
    destinations_covered: list[str] = Field(default_factory=list)
    preferred_destinations: str = ""
    languages: list[str] = Field(default_factory=list)
    preferred_language: str = ""
    service_categories: list[str] = Field(default_factory=list)
    provides_guides: bool | None = None
    guide_types: list[str] = Field(default_factory=list)
    transportation_available: bool | None = None
    working_days: list[str] = Field(default_factory=list)
    working_hours: str = ""
    min_group: int | None = None
    max_group: int | None = None
    private_groups: bool | None = None
    group_tours: bool | None = None
    currency: str = "JOD"
    pricing_model: str = ""
    min_price: float | None = None
    max_price: float | None = None
    pricing_notes: str = ""
    preferred_experience_types: list[str] = Field(default_factory=list)
    rating: float | None = None
    review_count: int | None = None
    review_source: str = ""
    phone: str = ""
    email: str = ""
    website: str | None = None
    subscribed: bool = False
    latitude: float | None = None
    longitude: float | None = None
    geo_precision: str = "unknown"

    def known_for(self) -> list[str]:
        strengths: list[str] = []
        if self.description:
            sentences = [part.strip() for part in self.description.replace("!", ".").split(".") if part.strip()]
            for sentence in sentences[:2]:
                if 24 <= len(sentence) <= 220 and sentence not in strengths:
                    strengths.append(sentence)
        if self.destinations_covered:
            strengths.append("Takes travelers to " + ", ".join(self.destinations_covered[:4]))
        extras = [
            item
            for item in self.service_categories
            if item.lower() not in {"tour guiding", "tour planning & itinerary design"}
        ]
        if extras:
            strengths.append("Also offers " + ", ".join(extras[:3]))
        if self.private_groups:
            strengths.append("Private groups available")
        if self.transportation_available:
            strengths.append("Can arrange transportation")
        return strengths[:5]

    def spec_rows(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        if self.specializations:
            rows.append({"label": "Specializations", "value": ", ".join(self.specializations)})
        if self.experience_years:
            rows.append({"label": "Experience", "value": f"{self.experience_years} years"})
        if self.languages:
            rows.append({"label": "Languages", "value": ", ".join(self.languages)})
        if self.target_customer_types:
            rows.append({"label": "Best for", "value": ", ".join(self.target_customer_types)})
        if self.min_group is not None or self.max_group is not None:
            low = self.min_group if self.min_group is not None else 1
            high = self.max_group if self.max_group is not None else "open"
            rows.append({"label": "Group size", "value": f"{low}–{high}"})
        if self.min_price is not None:
            high = f"–{self.max_price:g}" if self.max_price is not None else "+"
            rows.append({"label": "From", "value": f"{self.min_price:g}{high} {self.currency}"})
        elif self.pricing_model:
            rows.append({"label": "Pricing", "value": self.pricing_model})
        if self.working_hours:
            rows.append({"label": "Hours", "value": self.working_hours})
        if self.rating is not None:
            reviews = f" ({self.review_count} reviews)" if self.review_count else ""
            rows.append({"label": "Rating", "value": f"{self.rating}{reviews}"})
        return rows

    def prompt_card(self) -> dict[str, Any]:
        return {
            "sme_id": self.sme_id,
            "sme_type": self.sme_type,
            "name": self.name,
            "description": self.description,
            "known_for": self.known_for(),
            "specs": self.spec_rows(),
            "specializations": self.specializations,
            "target_customer_types": self.target_customer_types,
            "city": self.city,
            "region": self.region,
            "destinations_covered": self.destinations_covered,
            "languages": self.languages,
            "service_categories": self.service_categories,
            "preferred_experience_types": self.preferred_experience_types,
            "transportation_available": self.transportation_available,
            "min_group": self.min_group,
            "max_group": self.max_group,
            "pricing_model": self.pricing_model,
            "min_price": self.min_price,
            "max_price": self.max_price,
            "currency": self.currency,
            "rating": self.rating,
            "review_count": self.review_count,
            "subscribed": self.subscribed,
        }


class SMEMatch(BaseModel):
    record: SMERecord
    score: float
    factors: dict[str, float] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    role: str = ""
    covers_regions: list[str] = Field(default_factory=list)
    package_role: str = ""

    def prompt_card(self) -> dict[str, Any]:
        card = self.record.prompt_card()
        card.update(
            {
                "match_score": round(self.score, 3),
                "match_reasons": self.reasons,
                "suggested_role": self.role,
                "package_role": self.package_role,
                "covers_regions": self.covers_regions,
                "known_for": self.record.known_for(),
                "specs": self.record.spec_rows(),
            }
        )
        return card
