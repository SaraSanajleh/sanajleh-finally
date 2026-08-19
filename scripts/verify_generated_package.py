"""Generate a package for the captured case and audit it against the fixed rules.

Checks the failures the feedback reported, on whatever the model actually returns:
meal times, day span, hotel star honesty, destination coverage, budget completeness.

    python scripts/verify_generated_package.py [api_port]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "case_capture" / "cases"

MEAL_WINDOWS = {
    "breakfast": (7 * 60, 10 * 60),
    "lunch": (12 * 60, 15 * 60),
    "dinner": (18 * 60 + 30, 22 * 60),
}


def minutes(clock: str) -> int:
    match = re.match(r"^(\d{1,2}):(\d{2})", str(clock or ""))
    return int(match.group(1)) * 60 + int(match.group(2)) if match else -1


def main() -> None:
    port = sys.argv[1] if len(sys.argv) > 1 else "8000"
    case = max((p for p in CASES.iterdir() if p.is_dir()), key=lambda p: p.name)
    body = json.loads((case / "01_input.json").read_text(encoding="utf-8"))

    print(f"case: {case.name}\ngenerating (this takes about a minute)...\n")
    resp = httpx.post(
        f"http://127.0.0.1:{port}/api/v1/packages/generate", json=body, timeout=600
    )
    resp.raise_for_status()
    data = resp.json()
    package = data.get("package") or data
    (ROOT / "case_capture" / "last_verified_package.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    problems: list[str] = []

    for day in package.get("daily_itinerary") or []:
        num = day.get("day_number")
        acts = day.get("activities") or []
        print(f"Day {num}: {day.get('day_title')}")
        for act in acts:
            print(
                f"  {act.get('start_time')}-{act.get('end_time')}  "
                f"{str(act.get('activity_title'))[:52]:54s} {act.get('estimated_cost')}"
            )

        starts = [minutes(a.get("start_time")) for a in acts]
        if starts != sorted(starts):
            problems.append(f"day {num}: activities are not in chronological order")

        for act in acts:
            title = str(act.get("activity_title") or "").lower()
            start = minutes(act.get("start_time"))
            for meal, (lo, hi) in MEAL_WINDOWS.items():
                if meal in title and not (lo <= start <= hi):
                    problems.append(
                        f"day {num}: {meal} at {act.get('start_time')} is outside "
                        f"its window"
                    )

        ends = [minutes(a.get("end_time")) for a in acts if minutes(a.get("end_time")) >= 0]
        if ends and max(ends) < 19 * 60:
            problems.append(
                f"day {num}: last activity ends {max(ends)//60:02d}:{max(ends)%60:02d}, "
                f"the day never reaches the evening"
            )

        # density: a day of two sights and two meals is a lunch and a dinner, not a day out
        meal_words = ("breakfast", "lunch", "dinner", "brunch")
        sights = [
            a for a in acts
            if not any(w in str(a.get("activity_title") or "").lower() for w in meal_words)
        ]
        seeing = sum(
            max(minutes(a.get("end_time")) - minutes(a.get("start_time")), 0) for a in sights
        )
        gaps = [
            (minutes(b.get("start_time")) - minutes(a.get("end_time")), a, b)
            for a, b in zip(acts, acts[1:])
        ]
        worst = max(gaps, key=lambda g: g[0], default=None)
        print(f"  -> {len(sights)} sights, {seeing} min sightseeing, "
              f"largest gap {worst[0] if worst else 0} min")
        if len(sights) < 3:
            problems.append(f"day {num}: only {len(sights)} sights scheduled")
        if seeing < 240:
            problems.append(f"day {num}: {seeing} min of sightseeing (under four hours)")
        if worst and worst[0] > 90:
            problems.append(
                f"day {num}: {worst[0]} min of dead time after "
                f"'{str(worst[1].get('activity_title'))[:34]}'"
            )
        print()

    # alternatives must offer something the trip does not already contain
    scheduled = {
        re.sub(r"^(lunch|dinner|breakfast)\s*(at|in)?\s*", "",
               " ".join(str(a.get("activity_title") or "").lower().split()))
        for day in package.get("daily_itinerary") or []
        for a in day.get("activities") or []
    }
    for day in package.get("daily_itinerary") or []:
        for alt in day.get("activity_alternatives") or []:
            name = " ".join(str(alt.get("alternative_activity") or "").lower().split())
            if name in scheduled:
                problems.append(
                    f"day {day.get('day_number')}: alternative '{name}' is already in the trip"
                )

    # inclusions the itinerary does not contain
    plan_text = " ".join(
        f"{a.get('activity_title')} {a.get('description')} {a.get('smart_tip')}"
        for day in package.get("daily_itinerary") or []
        for a in day.get("activities") or []
    ).lower()
    for line in (package.get("trip_description") or {}).get("included") or []:
        for word in ("guide", "tour", "transfer", "transport", "insurance"):
            if word in str(line).lower() and word not in plan_text:
                problems.append(f"included claims '{line}' but no activity contains it")

    # nothing may appear twice in the whole trip
    seen: dict[str, int] = {}
    for day in package.get("daily_itinerary") or []:
        for act in day.get("activities") or []:
            key = " ".join(str(act.get("activity_title") or "").lower().split())
            key = re.sub(r"^(lunch|dinner|breakfast)\s*(at|in)?\s*", "", key)
            if not key:
                continue
            if key in seen:
                problems.append(
                    f"'{key}' appears on days {seen[key]} and {day.get('day_number')}"
                )
            seen[key] = day.get("day_number")

    text = json.dumps(package, ensure_ascii=False).lower()

    # every named area is visited, and nothing else is
    named = [
        str(x).lower()
        for x in (body["trip"].get("preferredRegions") or [])
        + (body.get("preferences", {}).get("mustVisit") or [])
    ]
    for area in named:
        if area and area not in text:
            problems.append(f"requested destination missing: {area}")

    # the traveller's own numbers, not the model's memory of them
    details = package.get("trip_details") or {}
    heads = sum(
        int(body["travelers"].get(k) or 0) for k in ("adults", "children", "seniors")
    )
    if str(details.get("number_of_travelers") or "") != str(heads):
        problems.append(
            f"number_of_travelers is {details.get('number_of_travelers')!r}, expected {heads}"
        )
    if not (details.get("trip_type") or []):
        problems.append("trip_type is empty")

    budget = package.get("budget_summary") or {}
    total = budget.get("total_estimated_cost")
    print(f"budget total: {total}  (traveller budget: {body['trip']['totalBudget']} JOD)")
    for item in budget.get("items") or []:
        print(
            f"  {str(item.get('category'))[:46]:48s} "
            f"{str(item.get('estimated_cost')):12s} {str(item.get('notes'))[:70]}"
        )
    categories = " ".join(
        str(i.get("category") or "").lower() for i in (budget.get("items") or [])
    )
    lodging_priced = any(
        re.search(r"\d", str(i.get("estimated_cost") or ""))
        for i in (budget.get("items") or [])
        if "accommodation" in str(i.get("category") or "").lower()
    )
    if "remaining budget" in categories and not lodging_priced:
        problems.append(
            "leftover is called 'Remaining Budget' while accommodation is unpriced"
        )

    # a claimed star rating must be the one actually booked
    wanted = re.search(r"(\d)", str(body["accommodation"].get("rating") or ""))
    if wanted:
        claimed = set(re.findall(r"(\d)[- ]star", text))
        print(f"\nrequested {wanted.group(1)}-star; ratings named in the text: {sorted(claimed)}")
        if claimed and wanted.group(1) not in claimed:
            print(
                "  (no hotel of the requested tier was named — check the explanation "
                "says so instead of claiming the request was met)"
            )

    print("\n" + ("=" * 60))
    if problems:
        print("PROBLEMS FOUND:")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)
    print("All audited rules pass.")


if __name__ == "__main__":
    main()
