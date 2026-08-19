"""Show the PLANNING LOCK and headline picks for the last captured case."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.knowledge.planner_assist import _headline_poi, build_planning_lock  # noqa: E402
from app.schemas.request.package_request import PackageRequest  # noqa: E402

CASES = ROOT / "case_capture" / "cases"


def latest_case() -> Path:
    folders = [p for p in CASES.iterdir() if p.is_dir()]
    return max(folders, key=lambda p: p.name)


def main() -> None:
    case = latest_case()
    print(f"case: {case.name}\n")
    payload = json.loads((case / "02_retriever.json").read_text(encoding="utf-8"))
    request = PackageRequest.model_validate(
        json.loads((case / "01_input.json").read_text(encoding="utf-8"))
    )

    print("--- PLANNING LOCK ---")
    print(build_planning_lock(payload, request))

    print("\n--- headline pick per cluster ---")
    for cluster in payload.get("clusters") or []:
        names = [
            (node.get("poi") or {}).get("name")
            for node in (cluster.get("pois") or [])
        ]
        print(f"  cluster {cluster.get('cluster_id')} ({cluster.get('theme')})")
        print(f"    headline: {_headline_poi(cluster)}")
        print(f"    pois: {names[:6]}")


if __name__ == "__main__":
    main()
