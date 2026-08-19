"""One-off audit — real JOD price bands per pricing_level, used to ground estimates."""
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / "data" / "customized_packages" / "knowledge"

SPECS = {
    "poi": ("poi.json", "entry_fee"),
    "restaurant": ("restaurant.json", "average_cost_per_person"),
    "hotel": ("hotel.json", "average_price_per_night"),
}


def normalize_level(raw: object) -> str:
    text = str(raw or "").strip().lower()
    if not text:
        return "(missing)"
    if text in ("$", "budget", "inexpensive", "low"):
        return "low"
    if text in ("$$", "medium", "mediam", "moderate", "mid-range", "low-medium"):
        return "medium"
    if text in ("$$$", "high", "medium-high"):
        return "high"
    if text == "free":
        return "free"
    return text


def main() -> None:
    for kind, (filename, price_key) in SPECS.items():
        rows = json.loads((KNOWLEDGE / filename).read_text(encoding="utf-8"))
        buckets: dict[str, list[float]] = defaultdict(list)
        missing_by_level: dict[str, int] = defaultdict(int)

        for row in rows:
            pricing = row.get("pricing") or {}
            level = normalize_level(pricing.get("pricing_level"))
            value = pricing.get(price_key)
            if value in (None, "", [], {}):
                missing_by_level[level] += 1
                continue
            try:
                buckets[level].append(float(value))
            except (TypeError, ValueError):
                missing_by_level[level] += 1

        print(f"\n=== {kind.upper()} — {price_key} by pricing_level ===")
        for level in sorted(set(buckets) | set(missing_by_level)):
            values = sorted(buckets.get(level, []))
            missing = missing_by_level.get(level, 0)
            if values:
                p25 = values[int(len(values) * 0.25)]
                p75 = values[min(int(len(values) * 0.75), len(values) - 1)]
                print(
                    f"  {level:10s} n={len(values):4d} missing={missing:3d} "
                    f"min={values[0]:6.1f} p25={p25:6.1f} "
                    f"median={statistics.median(values):6.1f} p75={p75:6.1f} "
                    f"max={values[-1]:6.1f}"
                )
            else:
                print(f"  {level:10s} n=   0 missing={missing:3d}  (no numeric prices)")


if __name__ == "__main__":
    main()
