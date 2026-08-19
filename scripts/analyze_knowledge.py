"""One-off knowledge audit — coverage of planning-critical fields per entity type."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / "data" / "customized_packages" / "knowledge"

FILES = {
    "poi": "poi.json",
    "restaurant": "restaurant.json",
    "hotel": "hotel.json",
    "event": "event.json",
}

PRICE_FIELD = {
    "poi": "entry_fee",
    "restaurant": "average_cost_per_person",
    "hotel": "average_price_per_night",
    "event": "ticket_cost",
}


def empty(value) -> bool:
    return value in (None, "", [], {})


def audit(kind: str, rows: list[dict]) -> None:
    total = len(rows)
    price_key = PRICE_FIELD[kind]
    missing_price = 0
    missing_coords = 0
    missing_level = 0
    missing_hours = 0
    regions: Counter[str] = Counter()
    levels: Counter[str] = Counter()
    price_values: list[float] = []

    for row in rows:
        pricing = row.get("pricing") or {}
        operation = row.get("operation") or {}
        location = row.get("location") or {}
        coords = location.get("coordinates") or {}

        value = pricing.get(price_key)
        if empty(value):
            missing_price += 1
        else:
            try:
                price_values.append(float(value))
            except (TypeError, ValueError):
                pass

        if empty(coords.get("latitude")) or empty(coords.get("longitude")):
            missing_coords += 1

        level = pricing.get("pricing_level")
        if empty(level):
            missing_level += 1
        else:
            levels[str(level)] += 1

        if kind in ("poi", "restaurant") and empty(operation.get("opening_hours")):
            missing_hours += 1

        regions[str(location.get("region") or "?")] += 1

    print(f"\n=== {kind.upper()}  (total={total}) ===")
    print(f"missing {price_key:26s}: {missing_price:5d}  ({missing_price / total:.0%})")
    print(f"missing coordinates          : {missing_coords:5d}  ({missing_coords / total:.0%})")
    print(f"missing pricing_level        : {missing_level:5d}  ({missing_level / total:.0%})")
    if kind in ("poi", "restaurant"):
        print(f"missing opening_hours        : {missing_hours:5d}  ({missing_hours / total:.0%})")
    print(f"pricing_level spread         : {dict(levels.most_common())}")
    if price_values:
        price_values.sort()
        mid = price_values[len(price_values) // 2]
        print(
            f"known {price_key} JOD        : min={price_values[0]:g} "
            f"median={mid:g} max={price_values[-1]:g}"
        )
    print(f"regions ({len(regions)})            : {dict(regions.most_common(6))}")


def main() -> None:
    for kind, filename in FILES.items():
        path = KNOWLEDGE / filename
        rows = json.loads(path.read_text(encoding="utf-8"))
        audit(kind, rows)


if __name__ == "__main__":
    main()
