"""Persist each package-generation case for RAG evaluation."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.utils.logging import get_logger

logger = get_logger(__name__)

_CASES_ROOT = Path(__file__).resolve().parents[2] / "case_capture" / "cases"
_INDEX_PATH = _CASES_ROOT / "index.jsonl"
_LAST_RAG = Path(__file__).resolve().parents[2] / "case_capture" / "last_retriever_response.json"


def cases_root() -> Path:
    return _CASES_ROOT


def build_rag_preview(knowledge: dict[str, Any]) -> dict[str, Any]:
    """Compact RAG summary for UI evaluation (not the full evidence package)."""
    meta = knowledge.get("meta") or {}
    clusters_out: list[dict[str, Any]] = []
    for cluster in knowledge.get("clusters") or []:
        if not isinstance(cluster, dict):
            continue
        pois = cluster.get("pois") or []
        hotels = cluster.get("hotels") or []
        events = cluster.get("events") or []
        poi_names: list[str] = []
        restaurants: list[str] = []
        for slot in pois:
            if not isinstance(slot, dict):
                continue
            poi = slot.get("poi") if isinstance(slot.get("poi"), dict) else slot
            if isinstance(poi, dict) and poi.get("name"):
                poi_names.append(str(poi["name"]))
            for rest in slot.get("restaurants") or []:
                if isinstance(rest, dict) and rest.get("name"):
                    restaurants.append(str(rest["name"]))
        clusters_out.append(
            {
                "cluster_id": cluster.get("cluster_id"),
                "theme": cluster.get("theme") or "",
                "poi_count": len(pois),
                "hotel_count": len(hotels),
                "event_count": len(events),
                "poi_names": poi_names[:12],
                "hotel_names": [
                    str(h.get("name"))
                    for h in hotels
                    if isinstance(h, dict) and h.get("name")
                ][:6],
                "sample_restaurants": restaurants[:6],
                "event_names": [
                    str(e.get("name"))
                    for e in events
                    if isinstance(e, dict) and e.get("name")
                ][:6],
            }
        )

    return {
        "status": meta.get("rag_status") or "unknown",
        "source": meta.get("source"),
        "duration_days": knowledge.get("duration_days"),
        "cluster_count": len(clusters_out),
        "clusters": clusters_out,
    }


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _safe_slug(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", (text or "").strip()).strip("-").lower()
    return (slug or "case")[:max_len]


def new_case_id(trip_title: str | None = None) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    suffix = _safe_slug(trip_title or "package")
    return f"{stamp}-{suffix}"


def save_generation_case(
    *,
    request_payload: dict[str, Any],
    knowledge: dict[str, Any],
    package: dict[str, Any],
    metadata: dict[str, Any],
    case_id: str | None = None,
) -> str:
    """
    Write one evaluation folder under case_capture/cases/{case_id}/.

    Files:
      01_input.json
      02_retriever.json          (full RAG knowledge)
      02_retriever_preview.json  (compact for quick review)
      03_output.json
      manifest.json
    """
    preview = build_rag_preview(knowledge)
    trip = package.get("trip") if isinstance(package.get("trip"), dict) else {}
    title = str(package.get("trip_title") or trip.get("title") or "")
    cid = case_id or new_case_id(title)
    case_dir = _CASES_ROOT / cid
    case_dir.mkdir(parents=True, exist_ok=True)

    _write_json(case_dir / "01_input.json", request_payload)
    _write_json(case_dir / "02_retriever.json", knowledge)
    _write_json(case_dir / "02_retriever_preview.json", preview)
    _write_json(
        case_dir / "03_output.json",
        {"metadata": metadata, "package": package},
    )

    created_at = datetime.now(timezone.utc).isoformat()
    manifest = {
        "caseId": cid,
        "createdAt": created_at,
        "trip_title": title,
        "rag": preview,
        "paths": {
            "input": "01_input.json",
            "knowledge": "02_retriever.json",
            "knowledge_preview": "02_retriever_preview.json",
            "output": "03_output.json",
        },
    }
    _write_json(case_dir / "manifest.json", manifest)

    # Keep legacy single-file dump for quick tail inspection.
    try:
        _write_json(_LAST_RAG, knowledge)
    except OSError as exc:
        logger.warning("Could not write last_retriever_response.json: %s", exc)

    try:
        _CASES_ROOT.mkdir(parents=True, exist_ok=True)
        with _INDEX_PATH.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "caseId": cid,
                        "createdAt": created_at,
                        "trip_title": title,
                        "rag_status": preview.get("status"),
                        "cluster_count": preview.get("cluster_count"),
                        "themes": [c.get("theme") for c in preview.get("clusters") or []],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    except OSError as exc:
        logger.warning("Could not append case index: %s", exc)

    logger.info("Case captured for evaluation: %s", case_dir)
    return cid


def list_cases(limit: int = 50) -> list[dict[str, Any]]:
    """Newest-first case summaries from manifests."""
    if not _CASES_ROOT.exists():
        return []

    items: list[dict[str, Any]] = []
    for path in sorted(_CASES_ROOT.iterdir(), reverse=True):
        if not path.is_dir():
            continue
        manifest_path = path / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            items.append(data)
        if len(items) >= limit:
            break
    return items


def load_case(case_id: str) -> dict[str, Any] | None:
    case_dir = _CASES_ROOT / case_id
    if not case_dir.is_dir():
        return None

    def _read(name: str) -> Any:
        path = case_dir / name
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    manifest = _read("manifest.json") or {"caseId": case_id}
    return {
        "caseId": case_id,
        "manifest": manifest,
        "input": _read("01_input.json"),
        "knowledge": _read("02_retriever.json"),
        "knowledge_preview": _read("02_retriever_preview.json"),
        "output": _read("03_output.json"),
    }


def load_case_knowledge(case_id: str) -> dict[str, Any] | None:
    path = _CASES_ROOT / case_id / "02_retriever.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None
