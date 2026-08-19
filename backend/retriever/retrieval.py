"""
ReTour Retriever — Station B5: Retrieval Engine
===============================================

Two layers:

  Layer 1 — search(): one hybrid search over a single collection.
      scope (collection) -> hard filter (metadata pre-filter)
      -> dense ranked list  ||  BM25 ranked list   (parallel)
      -> RRF fuse (ranks)   -> [rerank hook]        -> ranked candidates
      Each candidate also carries `similarity` (cosine, 1 - distance): additive,
      ordering unchanged — a real relevance signal for the Layer-2 cutoff.

  Layer 2 — build_hierarchy(): Planning-Oriented Evidence Packages (the vision).
      The fundamental unit is ONE realistic travel day (a Day Cluster) — not a
      city, not a region, not an embedding cluster.

      A) search POIs once (whole collection, untouched hybrid ranking = the JUDGE)
      B) allocate_days(): decide how many day clusters (~= trip DURATION, not the
         number of preferred regions) and the anchor region for each day, with an
         anchor-prioritization gate (merge/overflow) and semantic inference when
         the user gave no region.
      C) per day: select ANCHOR POIs (region identity, quality-gated, priority)
         then DISCOVERY POIs from THAT SAME requested region (surplus + same-governorate
         enrichment). Unrequested governorates never enter the package.
      D) attach restaurants to ANCHOR POIs only; hotels + events at cluster level.

Hard rules:
  - Grounded selection: agent picks from returned ids only (ids are explicit).
  - search()'s ranking is the JUDGE and is never modified; geography/region is a
    GATE applied on top; group/region matches are soft BOOSTS, never hard filters
    (except the genuinely non-negotiable dietary / accessibility constraints).
  - All numeric thresholds below are Station-2 tunables (measure, don't assert).
"""

import re
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable
from rank_bm25 import BM25Okapi

from normalize import normalize_wizard_value, region_key
from embedder import Embedder
from vector_store import VectorStore
from geo import haversine
from ranking import rrf_fuse, combine_fitness_proximity

# wizard hard-filter field -> (entity metadata field, entity_types it applies to)
# A hard constraint only gates the entity types where it is meaningful:
#   accessibility (wheelchair/elder) -> pois & hotels (long visit / overnight).
#   dietary (halal/vegan) -> restaurants only.
# groupType (suitable_for) is DELIBERATELY NOT here: it is a soft preference, not
#   a non-negotiable constraint. As a hard filter it silently starved whole entity
#   types (e.g. restaurants not tagged "Couples" vanished). It still influences
#   ranking softly (it is inside the dense text) and is applied as a boost below.
_HARD_MAP = {
    "accessibilityNeeds": ("accessibility", {"pois", "hotels"}),
    "cuisine_diet": ("dietary_options", {"restaurants"}),
}


# ---------------------------------------------------------------------
# BM25 index per collection (built once from stored sparse docs)
# ---------------------------------------------------------------------

class BM25Index:
    """Lexical index over a collection's sparse documents."""

    def __init__(self, ids: List[str], docs: List[str]):
        self._ids = ids
        self._bm25 = BM25Okapi([d.lower().split() for d in docs])

    def rank(self, query: str, n: int) -> List[str]:
        scores = self._bm25.get_scores(query.lower().split())
        order = sorted(range(len(self._ids)), key=lambda i: scores[i], reverse=True)
        return [self._ids[i] for i in order[:n]]


def build_bm25(store: VectorStore, coll_name: str) -> Optional[BM25Index]:
    data = store.get_all(coll_name)
    if not data["ids"]:
        return None
    return BM25Index(data["ids"], data["documents"])


# ---------------------------------------------------------------------
# Layer 1 — hybrid search over one collection
# ---------------------------------------------------------------------

def _hard_where(prefs: Dict[str, Any], coll_name: str) -> Optional[Dict[str, Any]]:
    """Build the hard-filter requirements, applying each constraint ONLY to the
    entity types where it is meaningful (see _HARD_MAP). Hard fields are stored
    as '|a|b|'; we require the normalized value present."""
    reqs = {}
    for wiz_field, (meta_field, applies_to) in _HARD_MAP.items():
        if coll_name not in applies_to:
            continue  # constraint not meaningful for this entity type
        vals = prefs.get(wiz_field)
        if not vals:
            continue
        norm = [normalize_wizard_value(meta_field, v)
                for v in (vals if isinstance(vals, list) else [vals])]
        reqs[meta_field] = norm
    return reqs or None


def _passes_hard(meta: Dict[str, Any], reqs: Optional[Dict[str, List[str]]]) -> bool:
    """Apply the hard filter in Python (portable, not tied to Chroma's engine).
    Stored fields are '|a|b|'; every required value must be present."""
    if not reqs:
        return True
    for meta_field, needed in reqs.items():
        stored = meta.get(meta_field, "") or ""
        for v in needed:
            if f"|{v}|" not in stored:
                return False
    return True


def search(store: VectorStore, bm25: Optional[BM25Index], embedder: Embedder,
           coll_name: str, query_text: str, prefs: Dict[str, Any],
           n: int, reranker: Optional[Callable] = None) -> List[Dict[str, Any]]:
    """One hybrid search: scope -> hard filter -> dense||BM25 -> RRF -> [rerank].
    Returns candidate records (id + metadata + similarity), best first.

    Hard filter is applied in Python over a wider retrieved pool, so it is
    portable across vector DBs and supports multi-value list membership.
    `similarity` (cosine, 1 - distance) is attached per candidate without
    affecting the fused ordering — it is the relevance signal Layer 2 gates on.
    """
    reqs = _hard_where(prefs, coll_name)
    pool = max(n * 5, 60)  # wider pool because we filter after retrieval

    # dense channel — retrieve wide, then hard-filter in Python
    qvec = embedder.encode([query_text])[0]
    dres = store.query(coll_name, qvec, n=pool, where=None)
    d_ids_all = dres["ids"][0] if dres.get("ids") else []
    d_meta_all = dres["metadatas"][0] if dres.get("metadatas") else []
    d_dist_all = dres["distances"][0] if dres.get("distances") else []
    meta_by_id = {i: m for i, m in zip(d_ids_all, d_meta_all)}
    # cosine space: similarity = 1 - distance
    sim_by_id = {i: (1.0 - float(d)) for i, d in zip(d_ids_all, d_dist_all)}

    # keep only hard-filter survivors, preserving dense order
    dense_ids = [i for i in d_ids_all if _passes_hard(meta_by_id[i], reqs)]
    allowed = set(dense_ids)

    # BM25 channel — lexical, restricted to the same survivors
    bm_ids: List[str] = []
    if bm25 is not None:
        for i in bm25.rank(query_text, n=pool):
            if i in allowed:
                bm_ids.append(i)

    # fuse by rank
    fused = rrf_fuse([dense_ids, bm_ids], k=60) if bm_ids else dense_ids

    # optional rerank hook (cross-encoder) on the head
    if reranker is not None and fused:
        fused = reranker(query_text, fused, meta_by_id)

    return [{"id": _id, "metadata": meta_by_id.get(_id, {}),
             "similarity": sim_by_id.get(_id)} for _id in fused[:n]]


# ---------------------------------------------------------------------
# Layer 2 — Planning-Oriented Evidence Packages (Day Clusters)
# ---------------------------------------------------------------------

def _coord(meta: Dict[str, Any]):
    """(lat, lon) or None. Null/0.0 coordinates -> None (e.g. region-level events)."""
    lat, lon = meta.get("lat"), meta.get("lon")
    if lat in (None, 0.0) or lon in (None, 0.0):
        return None
    return (float(lat), float(lon))


def _sim(rec: Dict[str, Any]) -> float:
    s = rec.get("similarity")
    return float(s) if s is not None else 0.0


# Wizard dests that are real trip stops, including names that are not governorates
# in the catalog (Dead Sea, Petra, Wadi Rum).
TOURIST_DESTS = {
    "irbid", "ajloun", "jerash", "amman", "zarqa", "balqa", "salt",
    "madaba", "dead sea", "karak", "tafilah", "petra", "wadi rum",
    "wadi musa", "aqaba", "maan", "ma'an",
}
TOURIST_DEST_HINTS = {
    "dead sea": ("dead sea", "sweimeh", "suweimeh", "panorama"),
    "petra": ("petra", "wadi musa", "siq", "khazneh", "treasury"),
    "wadi rum": ("wadi rum", "rum village", "disi"),
}
TOURIST_DEST_NEIGHBORS = {
    "dead sea": {"dead sea", "balqa", "madaba", "karak"},
    "petra": {"petra", "maan", "ma'an", "wadi musa"},
    "wadi rum": {"wadi rum", "maan", "ma'an", "aqaba"},
}
MUST_MAX_DAYS = 2


def _meta_hay(meta: Dict[str, Any]) -> str:
    return f"{meta.get('name') or ''} {meta.get('city') or ''} {meta.get('region') or ''}".lower()


def _region_match(meta: Dict[str, Any], token: str) -> bool:
    """A POI belongs to a region token if the token appears in its region string.
    Robust to the 'Amman' vs 'Amman Governorate' naming drift across the data."""
    if not token:
        return False
    return token in (meta.get("region") or "").lower()


def _dest_match(meta: Dict[str, Any], token: str) -> bool:
    """Match a wizard dest that is not stored as a governorate (Dead Sea → Sweimeh)."""
    key = region_key(token)
    hints = TOURIST_DEST_HINTS.get(key)
    if not hints:
        return False
    if not any(hint in _meta_hay(meta) for hint in hints):
        return False
    meta_key = _region_key_of(meta)
    allowed = TOURIST_DEST_NEIGHBORS.get(key)
    if allowed and meta_key and meta_key not in allowed:
        return False
    return True


def _day_region_tokens(day: Dict[str, Any]) -> List[str]:
    return [t for t in list(day.get("regions") or [])
            + list(day.get("hint_regions") or []) if t]


def _in_day_regions(meta: Dict[str, Any], day: Dict[str, Any]) -> bool:
    """True iff this entity's governorate is one the day was allocated to.

    Distance is irrelevant: Al-Husun (Irbid) sitting 23 km from Jerash must
    not ride along on a Jerash day."""
    tokens = _day_region_tokens(day)
    if not tokens:
        return False
    if any(_region_match(meta, t) or _dest_match(meta, t) for t in tokens):
        return True
    meta_key = _region_key_of(meta)
    return bool(meta_key) and any(region_key(t) == meta_key for t in tokens)


def _day_region_keys(day: Dict[str, Any]) -> set:
    keys = {region_key(t) for t in _day_region_tokens(day)}
    keys.discard("")
    return keys


def _centroid(recs: List[Dict[str, Any]]):
    pts = [c for c in (_coord(r["metadata"]) for r in recs) if c]
    if not pts:
        return None
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def _rank_map(records):
    """search() result (best-first) -> ({id: rank_pos}, {id: full_metadata}).
    rank_pos 0 = best; presence also means it survived the hard filter."""
    rank_pos, meta_map = {}, {}
    for i, r in enumerate(records):
        rank_pos[r["id"]] = i
        meta_map[r["id"]] = r["metadata"]
    return rank_pos, meta_map


def _stored_neighbors(poi_meta, bucket):
    """Precomputed neighbours of ONE poi from stored `nearby_json`.
    bucket in {pois,restaurants,hotels,events} -> [{id,name,distance_meters}]."""
    try:
        nb = json.loads(poi_meta.get("nearby_json", "{}"))
    except (json.JSONDecodeError, TypeError):
        return []
    return nb.get(bucket, []) or []


def _attach(neighbors, rank_pos, meta_map, count, boost_fn=None, allowed_keys=None,
            keep_fn=None):
    """Gate = neighbours only. Judge = full ranking. Distance = secondary weight.
    Optional `boost_fn(meta) -> float` adds soft preference bonuses (e.g. cuisine
    / group match). Returns up to `count` full-metadata cards, best first.
    `allowed_keys` keeps restaurants inside the POI's governorate.
    `keep_fn(meta) -> bool` is an extra hard keep (tourist-dest name match)."""
    pool_size = max(len(rank_pos), 1)
    scored = []
    for nb in neighbors:
        rid = nb.get("id")
        if rid not in rank_pos:      # didn't survive ranking / hard filter
            continue
        meta = meta_map.get(rid, {})
        if keep_fn is not None and not keep_fn(meta):
            continue
        if allowed_keys is not None and _region_key_of(meta) not in allowed_keys:
            continue
        fitness = 1.0 - (rank_pos[rid] / pool_size)          # the ranking, preserved
        dist_km = (nb.get("distance_meters") or 0) / 1000.0
        weight = combine_fitness_proximity(fitness, dist_km)  # Station-2 tunable
        if boost_fn is not None:
            weight += boost_fn(meta)
        scored.append((weight, rid, nb.get("distance_meters")))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [{"id": rid, "metadata": meta_map[rid], "distance_meters": dm}
            for _, rid, dm in scored[:count]]


def _region_key_of(meta: Dict[str, Any]) -> str:
    """Stored region_key if present (post-2b index), else canonicalize on the fly
    (so this also works before a re-index)."""
    return meta.get("region_key") or region_key(meta.get("region") or "")


def _region_attach(rank_pos, meta_map, region_keys, count, boost_fn=None,
                   centroid=None, keep_fn=None, day=None):
    """Attach cluster-level entities (hotels/events) by REGION, ordered by the
    hybrid ranking plus optional wizard boosts. Robust to null coordinates —
    common for hotels AND events — which the coordinate-based `nearby` path
    silently drops. Day-level entities belong to the day's region.

    centroid : if given and the entity HAS coordinates, closer-to-the-anchors
               scores higher (hotels shouldn't be geographically random).
    keep_fn  : optional hard predicate(meta)->bool (e.g. event month must match
               the travel month); a False drops the entity entirely.
    day      : when the wizard dest is not a governorate (Dead Sea), also keep
               hotels whose name/city matches that dest."""
    if not region_keys and day is None:
        return []
    pool = max(len(rank_pos), 1)
    cands = []
    for rid, m in meta_map.items():
        if rid not in rank_pos:
            continue
        key_ok = (not region_keys) or (_region_key_of(m) in region_keys)
        day_ok = day is not None and _in_day_regions(m, day)
        if region_keys and not key_ok and not day_ok:
            continue
        if keep_fn is not None and not keep_fn(m):
            continue
        fitness = 1.0 - (rank_pos[rid] / pool)
        weight = fitness + (boost_fn(m) if boost_fn else 0.0)
        if centroid is not None:
            c = _coord(m)
            if c is not None:
                d = haversine(c[0], c[1], centroid[0], centroid[1])
                weight += max(0.0, 0.20 * (1.0 - d / 30.0))   # nearer anchors -> higher
        cands.append((weight, rid))
    cands.sort(key=lambda x: x[0], reverse=True)
    return [{"id": rid, "metadata": meta_map[rid], "distance_meters": None}
            for _, rid in cands[:count]]


def _cluster_neighbors(cluster, bucket):
    """Union of the `bucket` neighbours of every POI in the cluster, de-duped by
    id (smallest stored distance kept). Keeps hotels/events inside the cluster's
    own geography — no global pool, no cluster[0] centroid hack.
    (Events region-join for null-coordinate events lands in Phase 2b.)"""
    best = {}
    for p in cluster:
        for nb in _stored_neighbors(p["metadata"], bucket):
            rid = nb.get("id")
            if rid is None:
                continue
            if rid not in best or (nb.get("distance_meters", 9e9) <
                                   best[rid].get("distance_meters", 9e9)):
                best[rid] = nb
    return list(best.values())


# --- explicit-intent anchors (regions / named places) ------------------------
#
#   mustVisit and preferredRegion mix REGION names ("Amman","Jerash") and PLACE
#   names ("Petra"). We classify each token data-drivenly: a token that appears
#   in some POI's `region` field is a REGION anchor; otherwise it is a PLACE
#   anchor (matched against POI name). Regions/must-visits are STRONG PLANNING
#   SIGNALS, not mandatory cluster definitions — the number of days follows the
#   trip DURATION, and the signals are distributed across those days.


def _anchor_tokens(prefs):
    """De-duplicated, lower-cased explicit-intent tokens from the wizard,
    preferredRegion first then mustVisit (priority order for the day gate)."""
    vals = []
    for key in ("preferredRegion", "mustVisit"):
        v = prefs.get(key) or []
        vals.extend(v if isinstance(v, list) else [v])
    out, seen = [], set()
    for s in vals:
        t = str(s).lower().strip()
        if t and t not in seen:
            seen.add(t); out.append(t)
    return out


def _classify_anchors(tokens, ranked):
    """Split tokens into (region_anchors, place_anchors).

    A wizard dest (Jerash, Dead Sea, Petra) stays a region even when the catalog
    stores it under another governorate. Anything else is a named place."""
    regions_present = {(p["metadata"].get("region") or "").lower() for p in ranked}
    region_anchors, place_anchors = [], []
    for t in tokens:
        key = region_key(t)
        if key in TOURIST_DESTS or any(t in r for r in regions_present if r):
            region_anchors.append(t)
        else:
            place_anchors.append(t)
    return region_anchors, place_anchors


# --- day allocation & anchor prioritization ----------------------------------
#
#   Rule:  number of Day Clusters ~= trip DURATION  (NOT number of regions).
#   If the user picked more regions than days -> keep the top `duration` as day
#   anchors, fold the overflow into the nearest day as discovery hints. If fewer
#   -> deepen the requested regions (second day in Jerash, not a surprise Irbid
#   day). Unrequested governorates are never inferred when the wizard named places.

_INFER_RADIUS_KM = 60.0   # inferred extra-day regions must be within this of the
                          #   explicit anchors' centroid (Station-2 tunable)


def _pois_in_regions(ranked, tokens):
    day = {"regions": list(tokens), "hint_regions": []}
    return [p for p in ranked if _in_day_regions(p["metadata"], day)]


def _region_centroid(tokens, ranked):
    return _centroid(_pois_in_regions(ranked, tokens))


def _covered(reg: str, tokens) -> bool:
    """Is region string `reg` already represented by one of `tokens`?"""
    return any(t and (t in reg or reg in t) for t in tokens)


def allocate_days(prefs: Dict[str, Any], duration: int,
                  ranked: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Decide the day clusters: how many (~= duration) and each day's anchor
    region(s). Returns a list of day plans:
        {"regions": [token,...], "forced_ids": set(), "hint_regions": [token,...]}
    """
    duration = max(int(duration or 1), 1)
    tokens = _anchor_tokens(prefs)
    region_anchors, place_anchors = _classify_anchors(tokens, ranked)

    days: List[Dict[str, Any]] = []
    used_regions: List[str] = []

    # 1) each region anchor -> its own day (priority = wizard order)
    for t in region_anchors:
        days.append({"regions": [t], "forced_ids": set(), "hint_regions": []})
        used_regions.append(t)

    # 2) each place anchor -> the region of the named POI; force-include that POI
    for t in place_anchors:
        poi = next((p for p in ranked
                    if t in (p["metadata"].get("name") or "").lower()), None)
        if poi is None:
            continue
        reg = (poi["metadata"].get("region") or "").lower()
        day = next((d for d in days if reg and _covered(reg, d["regions"])), None)
        if day is None:
            day = {"regions": [reg] if reg else [], "forced_ids": set(),
                   "hint_regions": []}
            days.append(day)
            if reg:
                used_regions.append(reg)
        day["forced_ids"].add(poi["id"])

    # 3a) more explicit anchors than days -> GATE: keep top `duration`, overflow
    #     becomes discovery hints on the geographically nearest kept day.
    if len(days) > duration:
        kept, overflow = days[:duration], days[duration:]
        for od in overflow:
            oc = _region_centroid(od["regions"], ranked)
            if oc is None:
                target = kept[0]
            else:
                target = min(kept, key=lambda d: (
                    haversine(oc[0], oc[1], *_region_centroid(d["regions"], ranked))
                    if _region_centroid(d["regions"], ranked) else 9e9))
            target["hint_regions"].extend(od["regions"])
            target["forced_ids"] |= od["forced_ids"]
        days = kept

    # 3b) fewer explicit anchors than days.
    #     Named explore dests get the extra days, capped at two. A must-visit
    #     may deepen once, then leftover days infer a nearby region. Never a
    #     third copy of the same dest, and never rewrite Dead Sea into Madaba.
    elif len(days) < duration:
        must_keys = {
            region_key(str(item))
            for item in (prefs.get("mustVisit") or [])
            if str(item).strip()
        }
        originals = list(days)
        explore = [
            day for day in originals
            if not any(region_key(token) in must_keys for token in day.get("regions") or [])
        ]
        must_days = [
            day for day in originals
            if any(region_key(token) in must_keys for token in day.get("regions") or [])
        ]
        deepen_from = (must_days + explore) if tokens else []
        if deepen_from:
            i = 0
            while len(days) < duration and i < 24:
                src = deepen_from[i % len(deepen_from)]
                copies = sum(1 for day in days if day.get("regions") == src.get("regions"))
                if copies >= MUST_MAX_DAYS:
                    i += 1
                    continue
                days.append({
                    "regions": list(src["regions"]),
                    "forced_ids": set(),
                    "hint_regions": [],
                    "deepen": True,
                })
                i += 1
        if len(days) < duration:
            explicit_c = _region_centroid(used_regions, ranked) if used_regions else None
            seen = list(used_regions)
            for poi in ranked:
                if len(days) >= duration:
                    break
                reg = (poi["metadata"].get("region") or "").lower()
                if not reg or _covered(reg, seen):
                    continue
                coord = _coord(poi["metadata"])
                if explicit_c and coord and haversine(
                        coord[0], coord[1], explicit_c[0], explicit_c[1]) > _INFER_RADIUS_KM:
                    continue
                days.append({"regions": [reg], "forced_ids": set(), "hint_regions": []})
                seen.append(reg)
            i = 0
            while len(days) < duration and days and i < 24:
                src = days[i % len(days)]
                copies = sum(1 for day in days if day.get("regions") == src.get("regions"))
                if copies >= 2:
                    i += 1
                    continue
                days.append({
                    "regions": list(src["regions"]),
                    "forced_ids": set(),
                    "hint_regions": [],
                    "deepen": True,
                })
                i += 1

    # 4) no anchors at all -> pure semantic inference ONLY when the wizard named
    #    no places. If the user named regions/must-visits we could not map, return
    #    empty rather than inventing a neighbouring governorate.
    if not days:
        if tokens:
            return []
        seen, order = set(), []
        for p in ranked:
            reg = (p["metadata"].get("region") or "").lower()
            if reg and reg not in seen:
                seen.add(reg); order.append(reg)
            if len(order) >= duration:
                break
        days = [{"regions": [r], "forced_ids": set(), "hint_regions": []}
                for r in order]

    return days[:duration]


# --- per-day selection: quality-driven anchors + discovery -------------------
#
#   Counts are NOT a fixed quota. Anchors are the day's identity — the strongest
#   POIs of the region the USER explicitly requested (so no tight semantic cutoff
#   filters them out). Discovery enriches THAT SAME requested region (surplus +
#   same-governorate POIs that clear the semantic cutoff). Unrequested
#   governorates never enter, even when they sit 15–25 km from an anchor.
#   A hard cluster CEILING protects the 3B context budget; there is no filler.

_ANCHOR_TARGET = 4        # target anchor POIs per day (surplus -> discovery)
_CAP_MAX = 10             # hard ceiling per day cluster (3B budget)
_CUTOFF_RATIO = 0.75      # DISCOVERY only: keep candidates with sim >= ratio*day-top
_DEDUP_KM = 0.3           # same-category within this distance = near-duplicate
                          #   (surgical: adjacent twins, not distinct institutions
                          #   a few blocks apart) — Station-2 tunable

# --- restaurant attachment (per POI + per cluster) ---
_REST_ANCHOR = 2          # restaurants per anchor POI
_REST_DISCOVERY = 1       # restaurants per discovery POI
_REST_CLUSTER_CAP = 8     # max restaurants per cluster (after de-dup)

# --- structured wizard-match boosts (2c) ---
#   A CLEAR, cumulative lift for an entity that satisfies a field the user
#   explicitly filled in the wizard. Soft (never a hard filter): a non-match is
#   not removed, it just misses the lift. Applied to the FULL ranked list before
#   selection, so a matching entity surfaces instead of depending on where the
#   semantic ranking happened to place it. Starting values — Station-2 tunable.
#   (star_rating / activity_level / occasion_suitability need the 2c-2 re-index.)
_BOOST_GROUP         = 0.12   # suitable_for matches groupType (couple/family/...)
_BOOST_GROUP_COMP    = 0.10   # suitable_for matches composition (Children/Seniors)
_BOOST_CUISINE       = 0.15   # cuisine_types matches a requested cuisine
_BOOST_ACCOMMODATION = 0.12   # category matches accommodationType (hotels)
_BOOST_STAR          = 0.35   # hotel star_rating == requested hotelRating: hotel is
                              # the MOST wizard-sensitive entity, so this is a strong
                              # (but still soft) lift — Station-2 tunable
_BOOST_LITERAL       = 0.20   # per explicit user term found verbatim (strong)
_LITERAL_CAP         = 0.45   # cap cumulative literal boost (don't let it dominate)

# words with no discriminating power -> excluded from literal matching
_STOPWORDS = {"the", "and", "with", "for", "near", "want", "would", "love", "like",
              "area", "old", "new", "very", "well", "that", "this", "some", "any",
              "our", "you", "your", "visit", "see", "trip", "day", "days", "have",
              "experience", "authentic", "really", "walking", "through", "around",
              "well-preserved", "preserved", "sites", "site", "places", "place"}

_MONTHS = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
           "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
           "december": 12}


def _loads(s):
    try:
        v = json.loads(s or "{}")
        return v if isinstance(v, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _parse_star(hotel_rating) -> Optional[int]:
    if not hotel_rating:
        return None
    m = re.search(r"\d+", str(hotel_rating))
    return int(m.group()) if m else None


def _literal_terms(prefs: Dict[str, Any]) -> set:
    """The user's explicit content terms (interests + mustVisit + freeText)."""
    raw = list(prefs.get("interests") or []) + list(prefs.get("mustVisit") or [])
    raw.append(prefs.get("freeText") or "")
    terms = set()
    for chunk in raw:
        for w in re.findall(r"[a-z]{3,}", str(chunk).lower()):
            if w not in _STOPWORDS:
                terms.add(w)
    return terms


def _stem_hit(term: str, words: set) -> bool:
    """Match term to any word, tolerant of plural/inflection (5-char stem)."""
    for w in words:
        if term == w or (len(term) >= 5 and len(w) >= 5 and term[:5] == w[:5]):
            return True
    return False


def _literal_words(meta: Dict[str, Any]) -> set:
    """Literal, user-typeable fields of an entity (name, themes, category)."""
    return set(re.findall(r"[a-z]{3,}", " ".join([
        meta.get("name", "") or "",
        (meta.get("themes", "") or "").replace("|", " "),
        meta.get("category", "") or "",
    ]).lower()))


def _travel_months(prefs: Dict[str, Any], duration: int) -> set:
    """The month(s) the trip spans (from startDate + duration)."""
    sd = (prefs.get("startDate") or "")[:10]
    try:
        d0 = datetime.strptime(sd, "%Y-%m-%d")
    except (ValueError, TypeError):
        return set()
    d1 = d0 + timedelta(days=max(int(duration) - 1, 0))
    return {d0.month, d1.month}


def _event_months(op: Dict[str, Any]) -> set:
    out = set()
    for m in (op.get("typical_months", []) or []):
        s = str(m).strip().lower()
        if s in _MONTHS:
            out.add(_MONTHS[s])
        elif s.isdigit():
            out.add(int(s))
    return out


def _group_composition(prefs: Dict[str, Any]) -> List[str]:
    """suitable_for tags implied by the party composition."""
    tags = []
    if (prefs.get("children") or 0) > 0:
        tags += ["Children", "Family"]
    if (prefs.get("seniors") or 0) > 0:
        tags += ["Seniors"]
    return tags


def _boost_prefs(prefs: Dict[str, Any]) -> Dict[str, Any]:
    """Pre-normalise the wizard fields that drive structured boosts (once)."""
    return {
        "group": (normalize_wizard_value("suitable_for", prefs.get("groupType"))
                  if prefs.get("groupType") else None),
        "group_comp": _group_composition(prefs),
        "cuisines": [normalize_wizard_value("cuisine_types", c)
                     for c in (prefs.get("cuisines") or [])],
        "accommodation": (prefs.get("accommodationType") or "").strip().lower() or None,
        "star": _parse_star(prefs.get("hotelRating")),
        "literal": _literal_terms(prefs),
    }


def _wizard_boost(meta: Dict[str, Any], bp: Dict[str, Any]) -> float:
    """Cumulative soft lift for matching explicit wizard fields."""
    b = 0.0
    sf = meta.get("suitable_for") or ""
    if bp.get("group") and f"|{bp['group']}|" in sf:
        b += _BOOST_GROUP
    for tag in bp.get("group_comp", []):
        if f"|{tag}|" in sf:
            b += _BOOST_GROUP_COMP
            break
    ct = meta.get("cuisine_types") or ""
    if any(c and f"|{c}|" in ct for c in bp.get("cuisines", [])):
        b += _BOOST_CUISINE
    at = bp.get("accommodation")
    if at and at in (meta.get("category") or "").lower():
        b += _BOOST_ACCOMMODATION
    # star rating (hotels): explicit wizard field -> STRONG signal, still soft
    star = bp.get("star")
    if star and meta.get("star_rating"):
        try:
            if int(meta.get("star_rating")) == star:
                b += _BOOST_STAR
        except (ValueError, TypeError):
            pass
    # literal match: a term the user explicitly wrote appears verbatim in the entity
    # (name/themes/category). This is what surfaces "Amman Citadel" when the user
    # wrote "citadels and castles" — user wrote it => it must surface.
    lit = bp.get("literal")
    if lit:
        words = _literal_words(meta)
        matched = sum(1 for t in lit if _stem_hit(t, words))
        if matched:
            b += min(matched * _BOOST_LITERAL, _LITERAL_CAP)
    return b


def _escore(rec: Dict[str, Any], bp: Dict[str, Any]) -> float:
    """Effective score = semantic similarity + structured wizard boosts."""
    return _sim(rec) + _wizard_boost(rec["metadata"], bp)


# --- placesToAvoid: real exclusion (not just a meta note) ---

def _avoid_tokens(places_to_avoid: str) -> List[str]:
    """Significant words from the free-text avoid field (named regions/places)."""
    if not places_to_avoid:
        return []
    return [w for w in re.findall(r"[a-z']+", places_to_avoid.lower()) if len(w) >= 3]


def _is_avoided(meta: Dict[str, Any], avoid: List[str]) -> bool:
    hay = " ".join([meta.get("name", "") or "", meta.get("region", "") or ""]).lower()
    return any(t in hay for t in avoid)


def _is_duplicate(cand, chosen) -> bool:
    """MMR proxy: same category within _DEDUP_KM of an already-chosen POI."""
    cc = _coord(cand["metadata"])
    ccat = (cand["metadata"].get("category") or "").lower()
    if cc is None or not ccat:
        return False
    for q in chosen:
        qc = _coord(q["metadata"])
        if qc is None:
            continue
        if (q["metadata"].get("category") or "").lower() == ccat and \
                haversine(cc[0], cc[1], qc[0], qc[1]) <= _DEDUP_KM:
            return True
    return False


_ANCHOR_CAT_CAP = 2       # at most N anchors of the SAME category (day diversity)


def _cat(m):
    return (m.get("category") or "").lower()


def select_anchors(day, ranked, used, bp):
    """Anchor POIs = the day's identity, from the region the USER requested.

    Because the user explicitly asked for this region, its POIs are NOT put
    through a tight semantic cutoff (that is what buried the Citadel/Theatre as
    'discovery'). We take the region's strongest POIs by EFFECTIVE score (semantic
    + wizard boosts), de-duplicated, up to _ANCHOR_TARGET. Forced named places are
    always kept. Region POIs beyond the target are returned as `surplus` — strong
    leftovers that discovery may use to enrich the day.

    DIVERSITY: no more than _ANCHOR_CAT_CAP anchors of the same category, so a day
    is NOT "3 museums". Over-represented strong POIs are deferred; if diversity
    leaves us short of the target we fill from them, and any remainder becomes
    surplus (discovery can still use it).

    Returns (anchors, surplus)."""
    cands = [p for p in ranked if p["id"] not in used and (
        p["id"] in day["forced_ids"]
        or _in_day_regions(p["metadata"], day))]
    if not cands:
        return [], []
    cands.sort(key=lambda p: _escore(p, bp), reverse=True)
    anchors, surplus, deferred = [], [], []
    catc: Dict[str, int] = {}
    for p in cands:
        if p["id"] in day["forced_ids"]:
            anchors.append(p)                          # user named it -> always in
            catc[_cat(p["metadata"])] = catc.get(_cat(p["metadata"]), 0) + 1
            continue
        if len(anchors) < _ANCHOR_TARGET:
            if _is_duplicate(p, anchors):
                used.add(p["id"])   # near-duplicate of a kept anchor -> consume
            elif catc.get(_cat(p["metadata"]), 0) >= _ANCHOR_CAT_CAP:
                deferred.append(p)  # category over-represented -> defer for diversity
            else:
                anchors.append(p)
                catc[_cat(p["metadata"])] = catc.get(_cat(p["metadata"]), 0) + 1
        else:
            surplus.append(p)                          # strong leftover for discovery
    # fallback: if diversity left us below target, fill from deferred (strongest first)
    for p in deferred:
        if len(anchors) >= _ANCHOR_TARGET:
            surplus.append(p)
        elif _is_duplicate(p, anchors):
            used.add(p["id"])
        else:
            anchors.append(p)
    return anchors, surplus


def select_discovery(day, ranked, used, anchors, surplus, bp, blocked_tokens):
    """Discovery enriches the day's requested governorate(s): strong surplus first,
    then other same-region POIs that clear the semantic cutoff. Unrequested
    governorates never enter — proximity is not a passport.

    `blocked_tokens` = OTHER days' explicit anchor regions (never bled across)."""
    day_top = max([_sim(a) for a in anchors] or [0.0])
    cutoff = _CUTOFF_RATIO * day_top
    room = _CAP_MAX - len(anchors)
    if room <= 0:
        return []

    chosen = list(anchors)
    discovery = []

    def eligible(pool):
        out = []
        for p in pool:
            if p["id"] in used or _sim(p) < cutoff:
                continue
            if any(_region_match(p["metadata"], t) for t in blocked_tokens):
                continue
            if not _in_day_regions(p["metadata"], day):
                continue
            out.append(p)
        out.sort(key=lambda p: _escore(p, bp), reverse=True)
        return out

    def take(cands):
        for p in cands:
            if len(discovery) >= room:
                break
            if p["id"] in used or _is_duplicate(p, chosen):
                continue
            discovery.append(p); chosen.append(p); used.add(p["id"])

    take(eligible(surplus))
    if len(discovery) < room:
        take(eligible(ranked))
    return discovery


def build_hierarchy(store: VectorStore, indexes: Dict[str, BM25Index],
                    embedder: Embedder, prefs: Dict[str, Any], duration: int,
                    reranker: Optional[Callable] = None,
                    rest_per_poi: int = 3, hotels_per_cluster: int = 4,
                    events_per_cluster: int = 3) -> Dict[str, Any]:
    """Planning-Oriented Evidence Package: ~= `duration` day clusters, each a
    realistic travel day (anchor POIs + discovery + restaurants on anchors +
    cluster-level hotels/events). search() is the untouched JUDGE; geography is
    the GATE; group/region are soft boosts."""
    query_text = prefs.get("query_text", "")
    bp = _boost_prefs(prefs)                         # structured wizard boosts
    avoid = _avoid_tokens(prefs.get("placesToAvoid", ""))

    def _ranked(coll):
        recs = search(store, indexes.get(coll), embedder, coll,
                      query_text, prefs, n=100000, reranker=reranker)
        if avoid:                                    # placesToAvoid: real exclusion
            recs = [r for r in recs if not _is_avoided(r["metadata"], avoid)]
        return recs

    # A) rank the WHOLE POI collection with the untouched hybrid ranking
    ranked_pois = _ranked("pois")

    # B) decide day clusters (~= duration) and each day's anchor region(s)
    day_plan = allocate_days(prefs, duration, ranked_pois)

    # C) pass 1: anchors (+ surplus) for every day, so a POI that anchors one day
    #    is never grabbed as another day's discovery.
    used: set = set()
    anchors_by_day, surplus_by_day = [], []
    for day in day_plan:
        anchors, surplus = select_anchors(day, ranked_pois, used, bp)
        for a in anchors:
            used.add(a["id"]); a["role"] = "anchor"
        anchors_by_day.append(anchors); surplus_by_day.append(surplus)

    # pass 2: discovery from the day's own requested region(s) only
    clusters = []
    for day, anchors, surplus in zip(day_plan, anchors_by_day, surplus_by_day):
        blocked = {t for other in day_plan if other is not day
                   for t in other["regions"]} - set(day["regions"])
        discovery = select_discovery(day, ranked_pois, used, anchors, surplus,
                                     bp, blocked)
        for d in discovery:
            d["role"] = "discovery"
        members = [p for p in anchors + discovery
                   if _in_day_regions(p["metadata"], day)]
        if members:                     # drop empty days (e.g. an empty region)
            clusters.append((day, members))

    # D) rank FULL secondary collections so every candidate has a rank position
    rest_rank, rest_meta = _rank_map(_ranked("restaurants"))
    hotel_rank, hotel_meta = _rank_map(_ranked("hotels"))
    event_rank, event_meta = _rank_map(_ranked("events"))

    def _boost(meta):
        return _wizard_boost(meta, bp)

    # event month is a HARD constraint: an event whose typical months don't overlap
    # the trip's month is simply wrong to suggest. Unknown months -> not excluded.
    travel_m = _travel_months(prefs, duration)

    def _event_keep(m):
        if not travel_m:
            return True
        em = _event_months(_loads(m.get("operation_json")))
        return True if not em else bool(em & travel_m)

    # E) assemble. Restaurants: EVERY POI gets >=1 if available (anchors up to
    #    _REST_ANCHOR, discovery up to _REST_DISCOVERY), de-duped across the
    #    cluster and capped at _REST_CLUSTER_CAP. A POI with no suitable nearby
    #    restaurant is flagged dining_available=False (a signal for the agent).
    #    Hotels + events: cluster level, by REGION (null-coord robust), boosted.
    out_clusters = []
    for ci, (day, cluster) in enumerate(clusters):
        day_keys = _day_region_keys(day)
        akeys = {_region_key_of(p["metadata"])
                 for p in cluster if p.get("role") == "anchor"}
        akeys.discard("")
        if not akeys:
            akeys = {_region_key_of(p["metadata"]) for p in cluster}
            akeys.discard("")
        if day_keys:
            akeys = (akeys & day_keys) or day_keys

        tourist = any(region_key(t) in TOURIST_DEST_HINTS for t in _day_region_tokens(day))
        # candidate restaurants per POI — same governorate as the POI / day
        cand_rest = {}
        for p in cluster:
            poi_key = _region_key_of(p["metadata"])
            allowed = {poi_key} if poi_key else set(akeys)
            if day_keys:
                overlap = allowed & day_keys
                if overlap:
                    allowed = overlap
            cand_rest[p["id"]] = _attach(
                _stored_neighbors(p["metadata"], "restaurants"),
                rest_rank, rest_meta, 6, boost_fn=_boost,
                allowed_keys=None if tourist else allowed,
                keep_fn=(lambda m, d=day: _in_day_regions(m, d)) if tourist else None)
        picked = {p["id"]: [] for p in cluster}
        seen_rest: set = set()
        cap_left = _REST_CLUSTER_CAP

        def _grab(pid, want):
            nonlocal cap_left
            for r in cand_rest[pid]:
                if cap_left <= 0 or len(picked[pid]) >= want:
                    break
                if r["id"] in seen_rest:
                    continue
                seen_rest.add(r["id"]); picked[pid].append(r); cap_left -= 1

        # round 1: guarantee >=1 per POI (anchors first)
        for p in cluster:
            _grab(p["id"], 1)
        # round 2: top up anchors toward _REST_ANCHOR
        for p in cluster:
            if p.get("role") == "anchor":
                _grab(p["id"], _REST_ANCHOR)

        poi_nodes = []
        for p in cluster:
            # dining_available reflects REALITY (a suitable restaurant is nearby),
            # not whether a unique card survived cluster de-dup. A downtown POI may
            # share its restaurant with a neighbour (listed once under that POI) yet
            # still have dining available here -> True with an empty own list.
            poi_nodes.append({
                "id": p["id"], "metadata": p["metadata"],
                "role": p.get("role", "discovery"),
                "restaurants": picked[p["id"]],
                "dining_available": bool(cand_rest[p["id"]]),
            })

        # explicit intra-day distances: for each POI, km to every OTHER POI in the
        # day (nearest first) so the agent can sequence/route without guessing.
        cl_coords = {p["id"]: _coord(p["metadata"]) for p in cluster}
        for node in poi_nodes:
            here = cl_coords.get(node["id"])
            dists = []
            if here is not None:
                for other in cluster:
                    if other["id"] == node["id"]:
                        continue
                    oc = cl_coords.get(other["id"])
                    if oc is None:
                        continue
                    dists.append({"poi_id": other["id"],
                                  "km": round(haversine(here[0], here[1],
                                                        oc[0], oc[1]), 1)})
                dists = [d for d in dists if d["km"] > 0.0]   # drop missing-coord noise
                dists.sort(key=lambda d: d["km"])
            node["distances_to_others"] = dists[:2]            # nearest 2 only

        anchor_centroid = _centroid([p for p in cluster
                                     if p.get("role") == "anchor"]) \
            or _centroid(cluster)

        out_clusters.append({
            "cluster_id": ci,
            "pois": poi_nodes,
            "hotels": _region_attach(hotel_rank, hotel_meta, akeys,
                                     hotels_per_cluster, boost_fn=_boost,
                                     centroid=anchor_centroid, day=day),
            "events": _region_attach(event_rank, event_meta, akeys,
                                     events_per_cluster, boost_fn=_boost,
                                     keep_fn=_event_keep, day=day),
        })

    return {"duration_days": duration, "clusters": out_clusters}