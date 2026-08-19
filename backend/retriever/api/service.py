"""
ReTour Retriever — Service layer.

Loads the index ONCE at startup; each request searches and wraps the hierarchical
result into the FINAL, committed contract (see models.py).

Card philosophy (curated, decision-supporting, ordered):
  - identity + role + why (alignment) + FLAT location come first;
  - `facts` = a curated, TYPE-SPECIFIC set of planning fields the agent needs to
    choose / schedule / cost / route / explain — nothing decorative;
  - no neighbour graph, no redundancy (context-length research);
  - graceful: if a metadata blob is missing (older index), the card degrades to
    fewer fields instead of crashing.
"""
import os
import re
import json
from collections import Counter
from typing import Dict, Any, List, Optional

from embedder import MiniLMEmbedder
from vector_store import VectorStore
from indexer import build_index
from retrieval import build_bm25, build_hierarchy
from query_builder import build_query
from normalize import normalize_wizard_value


def _loads(s):
    try:
        v = json.loads(s or "{}")
        return v if isinstance(v, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _pipe_list(s):
    """'|a|b|' -> ['a','b']."""
    return [x for x in (s or "").split("|") if x]


def _clean(d):
    """Drop empty values so the card carries only real, decision-supporting fields."""
    out = {}
    for k, v in d.items():
        if v in (None, "", [], {}):
            continue
        out[k] = v
    return out


class RetrieverService:
    def __init__(self, embedder, store, bm25_indexes, rest_per_poi,
                 hotels_per_cluster, events_per_cluster):
        self._embedder = embedder
        self._store = store
        self._bm25 = bm25_indexes
        self._rest_per_poi = rest_per_poi
        self._hotels_per_cluster = hotels_per_cluster
        self._events_per_cluster = events_per_cluster

    @classmethod
    def load(cls, data_dir, embedder_model, index_path,
             rest_per_poi, hotels_per_cluster, events_per_cluster):
        paths = [os.path.join(data_dir, f) for f in os.listdir(data_dir)
                 if f.endswith(".json")]
        embedder = MiniLMEmbedder(embedder_model)
        store = VectorStore(path=index_path)
        build_index(paths, embedder, store)
        bm25 = {c: build_bm25(store, c)
                for c in ["pois", "hotels", "restaurants", "events"]}
        return cls(embedder, store, bm25, rest_per_poi,
                   hotels_per_cluster, events_per_cluster)

    def search(self, wizard: Dict[str, Any]) -> Dict[str, Any]:
        q = build_query(wizard)
        raw = build_hierarchy(
            self._store, self._bm25, self._embedder, q["prefs"], q["duration"],
            rest_per_poi=self._rest_per_poi,
            hotels_per_cluster=self._hotels_per_cluster,
            events_per_cluster=self._events_per_cluster)
        interests = [i.lower() for i in wizard.get("interests", [])]
        return self._wrap(raw, q["meta"], interests, q["prefs"])

    # ------------------------------------------------------------------
    # alignment / why (deterministic)
    # ------------------------------------------------------------------

    @staticmethod
    def _region_tokens(prefs):
        toks = []
        for key in ("preferredRegion", "mustVisit"):
            v = prefs.get(key) or []
            toks.extend(v if isinstance(v, list) else [v])
        return [str(t).lower().strip() for t in toks if str(t).strip()]

    @staticmethod
    def _interest_hits(meta, interests):
        words = re.findall(r"[a-z]+", " ".join([
            meta.get("category", "") or "",
            meta.get("name", "") or "",
            (meta.get("themes", "") or "").replace("|", " ")]).lower())
        hits = []
        for raw in interests:
            i = (raw or "").lower()
            if not i:
                continue
            for w in words:
                if i == w or i in w or w in i or (
                        len(i) >= 5 and len(w) >= 5 and i[:5] == w[:5]):
                    hits.append(raw)
                    break
        return hits

    def _why(self, meta, interests, region_tokens, distance_m=None, cuisine_norm=None):
        why = [f"matches {i} interest" for i in self._interest_hits(meta, interests)]
        region = (meta.get("region", "") or "").lower()
        if any(t in region for t in region_tokens if t):
            why.append(f"in requested region: {meta.get('region', '')}")
        if cuisine_norm and meta.get("entity_type") == "restaurant":
            ct = meta.get("cuisine_types", "") or ""
            for cn in cuisine_norm:
                if cn and f"|{cn}|" in ct:
                    why.append(f"serves preferred cuisine: {cn}")
                    break
        if distance_m is not None:
            why.append(f"~{int(distance_m)} m away" if distance_m < 1000
                       else f"~{distance_m / 1000:.1f} km away")
        return why

    # ------------------------------------------------------------------
    # location (flat) + type-specific facts
    # ------------------------------------------------------------------

    @staticmethod
    def _location(m):
        loc = _loads(m.get("location_json"))
        # Some knowledge rows set location keys to null — coerce to "" for API schema.
        return {
            "region": m.get("region") or loc.get("region") or "",
            "city": loc.get("city") or "",
            "district": loc.get("district") or "",
            "address": loc.get("address") or "",
            "latitude": m.get("lat"),
            "longitude": m.get("lon"),
        }

    def _facts(self, m):
        et = m.get("entity_type", "")
        idn = _loads(m.get("identity_json"))
        exp = _loads(m.get("experience_json"))
        op = _loads(m.get("operation_json"))
        pr = _loads(m.get("pricing_json"))
        aud = _loads(m.get("audience_json"))
        ctx = _loads(m.get("context_json"))
        sub = idn.get("subcategory", "")
        cat = m.get("category", "")
        themes = _pipe_list(m.get("themes"))
        suitable = aud.get("suitable_for", []) or _pipe_list(m.get("suitable_for"))

        if et == "restaurant":
            f = {
                "category": cat, "subcategory": sub,
                "cuisine_types": exp.get("cuisine_types", []) or _pipe_list(m.get("cuisine_types")),
                "meal_types": exp.get("meal_types", []),
                "signature_dishes": exp.get("signature_dishes", []),
                "service_style": exp.get("service_style", ""),
                "atmosphere": exp.get("atmosphere", ""),
                "best_visit_time": exp.get("best_visit_time", []),
                "average_cost_per_person": pr.get("average_cost_per_person"),
                "currency": pr.get("currency", ""),
                "pricing_level": pr.get("pricing_level", ""),
                "dietary_options": aud.get("dietary_options", []),
                "occasion_suitability": aud.get("occasion_suitability", []),
                "suitable_for": suitable,
                "opening_hours": op.get("opening_hours", ""),
                "closing_hours": op.get("closing_hours", ""),
                "average_dining_minutes": op.get("average_dining_minutes"),
                "notes": ctx.get("notes", ""),
            }
        elif et == "hotel":
            f = {
                "category": cat, "subcategory": sub,
                "star_rating": exp.get("star_rating"),
                "room_types": exp.get("room_types", []),
                "amenities": exp.get("amenities", []),
                "view_types": exp.get("view_types", []),
                "best_for": exp.get("best_for", []),
                "average_price_per_night": pr.get("average_price_per_night"),
                "currency": pr.get("currency", ""),
                "pricing_level": pr.get("pricing_level", ""),
                "suitable_for": suitable,
                "check_in": op.get("check_in", ""),
                "check_out": op.get("check_out", ""),
                "notes": ctx.get("notes", ""),
            }
        elif et == "event":
            f = {
                "category": cat, "subcategory": sub, "themes": themes,
                "typical_months": op.get("typical_months", []),
                "typical_seasons": op.get("typical_seasons", []),
                "recurrence": op.get("recurrence", ""),
                "duration_minutes": op.get("duration_minutes"),
                "ticket_cost": pr.get("ticket_cost"),
                "currency": pr.get("currency", ""),
                "pricing_level": pr.get("pricing_level", ""),
                "indoor_outdoor": exp.get("indoor_outdoor", ""),
                "highlights": exp.get("highlights", []),
                "languages": aud.get("languages", []),
                "minimum_age": aud.get("minimum_age"),
                "suitable_for": suitable,
            }
        else:  # poi
            f = {
                "category": cat, "subcategory": sub, "themes": themes,
                "opening_hours": op.get("opening_hours", ""),
                "closing_hours": op.get("closing_hours", ""),
                "closed_days": op.get("closed_days", []),
                "average_visit_minutes": op.get("average_visit_minutes"),
                "booking_required": op.get("booking_required"),
                "best_visit_time": exp.get("best_visit_time", []),
                "activity_level": exp.get("activity_level", ""),
                "indoor_outdoor": exp.get("indoor_outdoor", ""),
                "entry_fee": pr.get("entry_fee"),
                "currency": pr.get("currency", ""),
                "pricing_level": pr.get("pricing_level", ""),
                "highlights": exp.get("highlights", []),
                "notes": ctx.get("notes", ""),
                "suitable_for": suitable,
            }
        # STABLE schema: every field of the type is ALWAYS present (empty if the
        # knowledge lacks it) so the agent can rely on the shape — never dropped.
        return f

    def _card(self, rec, interests, region_tokens, role="",
              distance_m=None, cuisine_norm=None):
        m = rec.get("metadata", {})
        loc = self._location(m)
        card = {
            "id": rec.get("id", ""),
            "entity_type": m.get("entity_type", ""),
            "name": m.get("name", ""),
            "role": role,
            "region": loc["region"], "city": loc["city"],
            "district": loc["district"], "address": loc["address"],
            "latitude": loc["latitude"], "longitude": loc["longitude"],
            "why_retrieved": self._why(m, interests, region_tokens,
                                       distance_m, cuisine_norm),
            "facts": self._facts(m),
        }
        return card

    # ------------------------------------------------------------------
    # cluster theme / summary
    # ------------------------------------------------------------------

    @staticmethod
    def _role_of(raw_role):
        return "anchor" if raw_role in ("requested", "anchor") else "discovery"

    def _theme(self, primary_region, cluster_pois, interests):
        seen, matched = set(), []
        for p in cluster_pois:
            for i in self._interest_hits(p.get("metadata", {}), interests):
                if i not in seen:
                    seen.add(i); matched.append(i)
        focus = ", ".join(matched) if matched else ", ".join(interests)
        if primary_region and focus:
            return f"{primary_region} \u00b7 {focus}"
        return primary_region or focus or "Day cluster"

    @staticmethod
    def _summary(primary_region, n_anchor, n_disc, n_rest, n_hotels, n_events):
        loc = primary_region or "This area"
        parts = [f"{loc}: {n_anchor} anchor + {n_disc} discovery POIs"]
        if n_rest:
            parts.append(f"{n_rest} restaurants")
        if n_hotels:
            parts.append(f"{n_hotels} hotels")
        if n_events:
            parts.append(f"{n_events} events")
        return "; ".join(parts) + "."

    # ------------------------------------------------------------------
    # wrap
    # ------------------------------------------------------------------

    def _wrap(self, raw, meta, interests, prefs):
        region_tokens = self._region_tokens(prefs)
        cuisine_norm = [normalize_wizard_value("cuisine_types", c)
                        for c in (prefs.get("cuisines") or [])]
        clusters = []
        for cl in raw.get("clusters", []):
            poi_nodes = []
            anchor_regions, all_regions = [], []
            n_anchor = n_disc = n_rest = 0

            for pn in cl.get("pois", []):
                role = self._role_of(pn.get("role", "discovery"))
                region = pn.get("metadata", {}).get("region", "")
                if region:
                    all_regions.append(region)
                if role == "anchor":
                    n_anchor += 1
                    if region:
                        anchor_regions.append(region)
                else:
                    n_disc += 1

                rests = [self._card(r, interests, region_tokens,
                                    distance_m=r.get("distance_meters"),
                                    cuisine_norm=cuisine_norm)
                         for r in pn.get("restaurants", [])]
                n_rest += len(rests)
                poi_nodes.append({
                    "poi": self._card(pn, interests, region_tokens, role=role),
                    "restaurants": rests,
                    "dining_available": pn.get("dining_available", bool(rests)),
                    "distances_to_others": pn.get("distances_to_others", []),
                })

            hotels = [self._card(h, interests, region_tokens) for h in cl.get("hotels", [])]
            events = [self._card(e, interests, region_tokens) for e in cl.get("events", [])]

            pool = anchor_regions or all_regions
            primary_region = Counter(pool).most_common(1)[0][0] if pool else ""

            clusters.append({
                "cluster_id": cl.get("cluster_id", 0),
                "theme": self._theme(primary_region, cl.get("pois", []), interests),
                "pois": poi_nodes,
                "hotels": hotels,
                "events": events,
                "summary": self._summary(primary_region, n_anchor, n_disc,
                                         n_rest, len(hotels), len(events)),
            })

        return {"duration_days": raw.get("duration_days", 0),
                "clusters": clusters, "meta": meta}