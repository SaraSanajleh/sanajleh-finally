"""
ReTour Retriever — Station B3: Neighbors + Clustering
=====================================================

Two independent geo functions over entity coordinates:

  1. Nearby (Decision 3) — precomputed at INGESTION time, stored per entity.
     For each entity, find its closest entities OF EACH TYPE (nearest
     restaurants / hotels / pois / events). Used later at RANKING time when
     the agent needs a restaurant/hotel near a chosen POI (Decision 5, phase B).

  2. Clustering (Decision 6) — run at REQUEST time on the RETRIEVED POIs only
     (a few dozen), never on the full corpus. Groups POIs geographically so the
     agent distributes clusters over days instead of untangling a flat list.

Notes:
  - Distance is Haversine (great-circle) — a deliberate approximation of road
    distance. Fine-grained temporal feasibility is the agent's job.
  - Gemini's `nearby` field is IGNORED (ids empty / invented). We compute ours.
  - Clustering uses DBSCAN + fallback: a noise point (label -1) becomes its own
    singleton cluster, so we never return zero regions.
"""

from math import radians, sin, cos, asin, sqrt
from typing import Optional
from sklearn.cluster import DBSCAN

_EARTH_KM = 6371.0


# ---------------------------------------------------------------------
# Distance
# ---------------------------------------------------------------------

def haversine(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance between two lat/lon points, in kilometers."""
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * _EARTH_KM * asin(sqrt(a))


def _coords(entity: dict) -> Optional[tuple]:
    """Extract (lat, lon) or None if missing."""
    c = entity.get("location", {}).get("coordinates", {})
    lat, lon = c.get("latitude"), c.get("longitude")
    if lat is None or lon is None:
        return None
    return float(lat), float(lon)


# plural bucket names in the schema's `nearby` object, per neighbor type
_BUCKET = {"poi": "pois", "restaurant": "restaurants",
           "hotel": "hotels", "event": "events"}


# ---------------------------------------------------------------------
# 1. Nearby — ingestion-time precompute
# ---------------------------------------------------------------------

def compute_nearby(entities: list, k: int = 5) -> dict:
    """For every entity, find the k closest entities OF EACH TYPE.

    Returns: { entity_id: { "pois":[{id,name,distance_meters},...],
                            "restaurants":[...], "hotels":[...], "events":[...] } }
    Entities without coordinates get empty buckets (flagged, never crash).
    """
    prepared = []
    for e in entities:
        prepared.append((e.get("id"), e.get("entity_type"), _coords(e),
                         e.get("identity", {}).get("name")))

    result = {}
    for eid, _etype, ecoord, _ in prepared:
        buckets = {"pois": [], "restaurants": [], "hotels": [], "events": []}
        if ecoord is None:
            result[eid] = buckets
            continue

        scored = {"pois": [], "restaurants": [], "hotels": [], "events": []}
        for oid, otype, ocoord, oname in prepared:
            if oid == eid or ocoord is None:
                continue
            bucket = _BUCKET.get(otype)
            if bucket is None:
                continue
            d = haversine(ecoord[0], ecoord[1], ocoord[0], ocoord[1])
            scored[bucket].append((d, oid, oname))

        for bucket, items in scored.items():
            items.sort(key=lambda x: x[0])
            buckets[bucket] = [
                {"id": oid, "name": oname, "distance_meters": round(d * 1000)}
                for d, oid, oname in items[:k]
            ]
        result[eid] = buckets

    return result


# ---------------------------------------------------------------------
# 2. Clustering — request-time, on retrieved POIs
# ---------------------------------------------------------------------

def cluster_pois(pois: list, eps_km: float = 30.0, min_samples: int = 3) -> list:
    """Cluster retrieved POIs geographically with DBSCAN + singleton fallback.

    Returns: list of clusters; each cluster is a list of the input POI dicts.
             Noise points become their own singleton clusters (never dropped).
    """
    if not pois:
        return []

    pts, idx_with, without = [], [], []
    for i, p in enumerate(pois):
        c = _coords(p)
        if c is None:
            without.append(i)
        else:
            pts.append(c)
            idx_with.append(i)

    clusters = {}
    if pts:
        n = len(pts)
        dist = [[0.0] * n for _ in range(n)]
        for a in range(n):
            for b in range(a + 1, n):
                d = haversine(pts[a][0], pts[a][1], pts[b][0], pts[b][1])
                dist[a][b] = dist[b][a] = d

        labels = DBSCAN(eps=eps_km, min_samples=min_samples,
                        metric="precomputed").fit_predict(dist)

        singleton_seed = 1000
        for local_i, label in enumerate(labels):
            if label == -1:
                key = f"s{singleton_seed}"
                singleton_seed += 1
            else:
                key = f"c{label}"
            clusters.setdefault(key, []).append(pois[idx_with[local_i]])

    for j, i in enumerate(without):
        clusters[f"nocoord{j}"] = [pois[i]]

    return list(clusters.values())


# ---------------------------------------------------------------------
# Self-check
# ---------------------------------------------------------------------
if __name__ == "__main__":
    def poi(pid, lat, lon, name):
        return {"id": pid, "entity_type": "poi",
                "identity": {"name": name},
                "location": {"coordinates": {"latitude": lat, "longitude": lon}}}

    def rest(rid, lat, lon, name):
        return {"id": rid, "entity_type": "restaurant",
                "identity": {"name": name},
                "location": {"coordinates": {"latitude": lat, "longitude": lon}}}

    d = haversine(31.95, 35.93, 29.53, 35.00)
    assert 250 < d < 350, d

    entities = [
        poi("poi_1", 31.95, 35.93, "Amman POI"),
        rest("rest_1", 31.96, 35.94, "Amman Rest"),
        rest("rest_2", 29.53, 35.00, "Aqaba Rest"),
    ]
    nb = compute_nearby(entities, k=5)
    assert nb["poi_1"]["restaurants"][0]["id"] == "rest_1"

    petra = [poi(f"p{i}", 30.32 + i*0.01, 35.45, f"Petra {i}") for i in range(3)]
    dead = poi("dead", 31.50, 35.47, "Dead Sea")
    irbid = poi("irbid", 32.55, 35.85, "Irbid")
    clusters = cluster_pois(petra + [dead, irbid], eps_km=30, min_samples=3)
    sizes = sorted(len(c) for c in clusters)
    assert sizes == [1, 1, 3], sizes

    spread = [poi("a", 29.5, 35.0, "Aqaba"), poi("b", 31.5, 35.5, "DeadSea"),
              poi("c", 32.5, 35.8, "Irbid"), poi("d", 30.3, 35.4, "Petra")]
    cl2 = cluster_pois(spread, eps_km=10, min_samples=3)
    assert len(cl2) == 4, len(cl2)

    print("All checks passed — neighbors + clustering work correctly.")
