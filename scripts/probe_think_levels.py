"""Ask the configured Ollama model how it behaves under each `think` setting.

Prints, per setting, whether the call succeeds and how the token budget splits between
the thinking channel and the content channel — the split that decides whether a package
ever gets written.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config.settings import get_llm_settings  # noqa: E402

PROMPT = (
    'Return only this JSON object, nothing else: '
    '{"trip_title":"X","daily_itinerary":[{"day_number":"1","day_title":"A"}]}'
)


def probe(base_url: str, model: str, think) -> None:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.3, "num_predict": 512},
    }
    if think is not None:
        payload["think"] = think
    try:
        resp = httpx.post(f"{base_url.rstrip('/')}/api/chat", json=payload, timeout=180)
    except httpx.HTTPError as exc:
        print(f"  think={think!r:10s} -> transport error: {exc}")
        return
    if resp.status_code != 200:
        print(f"  think={think!r:10s} -> HTTP {resp.status_code}: {resp.text[:160]}")
        return
    data = resp.json()
    message = data.get("message") or {}
    print(
        f"  think={think!r:10s} -> done={data.get('done_reason')!r:10s} "
        f"thinking={len(message.get('thinking') or ''):6d} chars  "
        f"content={len(message.get('content') or ''):5d} chars  "
        f"{json.dumps(message.get('content') or '')[:70]}"
    )


def main() -> None:
    llm = get_llm_settings()
    print(f"model={llm.model_name} base={llm.ollama_base_url}\n")
    for think in (None, False, "low", "medium", "high"):
        probe(llm.ollama_base_url, llm.model_name, think)


if __name__ == "__main__":
    main()
