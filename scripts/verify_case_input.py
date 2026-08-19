"""Show the evidence and PLANNING LOCK a raw wizard input would produce.

Takes a wizard JSON file (the same body the frontend posts) rather than a captured case,
so a new scenario can be checked before spending a generation on it.

    python scripts/verify_case_input.py path/to/input.json [port]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.knowledge.planner_assist import build_planning_lock  # noqa: E402
from app.knowledge.wizard_payload import package_request_to_wizard_payload  # noqa: E402
from app.schemas.request.package_request import PackageRequest  # noqa: E402


def main() -> None:
    body_path = Path(sys.argv[1])
    port = sys.argv[2] if len(sys.argv) > 2 else "8001"
    request = PackageRequest.model_validate(
        json.loads(body_path.read_text(encoding="utf-8"))
    )

    resp = httpx.post(
        f"http://127.0.0.1:{port}/api/v1/knowledge/search",
        json=package_request_to_wizard_payload(request),
        timeout=300,
    )
    resp.raise_for_status()
    data = resp.json()

    for cluster in data.get("clusters") or []:
        pois = [(n.get("poi") or {}) for n in (cluster.get("pois") or [])]
        print(f"cluster {cluster.get('cluster_id')} — {cluster.get('theme')}")
        for poi in pois:
            fee = (poi.get("facts") or {}).get("entry_fee")
            mins = (poi.get("facts") or {}).get("average_visit_minutes")
            print(f"    {str(poi.get('name'))[:44]:46s} fee={str(fee):6s} min={str(mins):5s} "
                  f"{poi.get('city')}")
        print(
            "  hotels: "
            + str([
                f"{h.get('name')} ({(h.get('facts') or {}).get('star_rating')}*)"
                for h in (cluster.get("hotels") or [])
            ])
        )
        print()

    print("--- PLANNING LOCK ---")
    print(build_planning_lock(data, request))


if __name__ == "__main__":
    main()
