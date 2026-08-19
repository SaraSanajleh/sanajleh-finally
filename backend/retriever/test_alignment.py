# -*- coding: utf-8 -*-
"""
ReTour Retriever — Adapter Alignment Guard
==========================================

Soundness guardrail for the wizard <-> knowledge adapter (QA batch 1).

Every option the wizard can show MUST translate, through the adapter tables, to a
value that ACTUALLY EXISTS in the knowledge base. If a mapping target is missing
from the data (typo, drift, a removed value), this test fails loudly — so a silent
"user picks X, matches nothing" regression can never ship again.

Run:  python test_alignment.py        (from backend/retriever/)
"""
import os
import json

from normalize import normalize_wizard_value, normalize_wizard_multi

# --- locate the knowledge JSON (../../data/customized_packages/knowledge) --------
_HERE = os.path.dirname(os.path.abspath(__file__))
_KB = os.path.normpath(os.path.join(
    _HERE, "..", "..", "data", "customized_packages", "knowledge"))


def _load(name):
    with open(os.path.join(_KB, name), encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else [data]


def _values(entities, *path, listval=True):
    """Distinct values of a (possibly nested, possibly list) field."""
    out = set()
    for e in entities:
        cur = e
        for k in path:
            cur = cur.get(k) if isinstance(cur, dict) else None
        if listval:
            for x in (cur or []):
                if x not in (None, ""):
                    out.add(str(x))
        elif cur not in (None, ""):
            out.add(str(cur))
    return out


# --- the wizard option CONTRACT (mirrors the frontend Step components) ------------
WIZARD_ACCESSIBILITY = ["Wheelchair", "Limited Walking", "Visual", "Hearing",
                        "Elder Friendly"]
WIZARD_CUISINE = ["Jordanian", "Arabic", "Mediterranean", "Italian", "Asian",
                  "International", "Seafood", "BBQ", "Fast Food", "Cafe & Desserts",
                  "Vegetarian", "Vegan", "Halal"]
WIZARD_ACCOMMODATION = ["hotel", "resort", "boutique", "eco_lodge", "desert_camp",
                        "no_pref"]

# values that are MEANT to reach a knowledge counterpart
SUPPORTED_ACCESS = {"Wheelchair Accessible", "Elderly Friendly"}
DIET_VALUES = {"Halal", "Vegetarian", "Vegan"}


def main():
    pois = _load("poi.json")
    rests = _load("restaurant.json")
    hotels = _load("hotel.json")

    # accessibility hard filter applies to POIs + hotels (see retrieval._HARD_MAP)
    kb_access = (_values(pois, "audience", "accessibility")
                 | _values(hotels, "audience", "accessibility"))
    kb_cuisine = _values(rests, "experience", "cuisine_types")
    kb_diet = _values(rests, "audience", "dietary_options")
    kb_hotel_cat = _values(hotels, "identity", "category", listval=False)

    failures = []

    # --- accessibility -------------------------------------------------------
    for opt in WIZARD_ACCESSIBILITY:
        canon = normalize_wizard_value("accessibility", opt)
        if canon in SUPPORTED_ACCESS and canon not in kb_access:
            failures.append(f"accessibility '{opt}' -> '{canon}' NOT in knowledge")
    reachable = {normalize_wizard_value("accessibility", o) for o in WIZARD_ACCESSIBILITY}
    for need in SUPPORTED_ACCESS:
        if need not in reachable:
            failures.append(f"supported accessibility '{need}' unreachable from wizard")

    # --- cuisine (incl. diet routing) ----------------------------------------
    for opt in WIZARD_CUISINE:
        if opt in DIET_VALUES:
            canon = normalize_wizard_value("dietary_options", opt)
            if canon not in kb_diet:
                failures.append(f"diet '{opt}' -> '{canon}' NOT in dietary_options")
        else:
            targets = normalize_wizard_multi("cuisine_types", opt)
            if not targets:
                failures.append(f"cuisine '{opt}' expands to NOTHING")
            for t in targets:
                if t not in kb_cuisine:
                    failures.append(f"cuisine '{opt}' -> '{t}' NOT in cuisine_types")

    # --- accommodation -------------------------------------------------------
    for opt in WIZARD_ACCOMMODATION:
        canon = normalize_wizard_value("accommodation", opt)
        if not canon:            # no_pref -> "" (intentional, no boost)
            continue
        if canon not in kb_hotel_cat:
            failures.append(f"accommodation '{opt}' -> '{canon}' NOT in hotel category")

    # --- report --------------------------------------------------------------
    print(f"knowledge: {len(pois)} POI, {len(rests)} restaurants, {len(hotels)} hotels")
    print(f"KB accessibility (POI+hotel): {sorted(kb_access)}")
    print(f"KB hotel categories        : {sorted(kb_hotel_cat)}")
    if failures:
        print("\nALIGNMENT FAILURES:")
        for f in failures:
            print("  x " + f)
        raise SystemExit(1)
    print("\nAll wizard options map to values that exist in the knowledge. OK")


if __name__ == "__main__":
    main()
