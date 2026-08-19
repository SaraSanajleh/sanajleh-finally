"""One-off LLM latency benchmark — not part of test suite."""
import asyncio
import json
import time

import httpx

from app.schemas.request.package_request import PackageRequest
from app.services.prompt_service import PromptService
from tests.fixtures.sample_payloads import VALID_PACKAGE_REQUEST


def build_prompt(duration: str) -> str:
    data = {
        **VALID_PACKAGE_REQUEST,
        "trip": {**VALID_PACKAGE_REQUEST["trip"], "duration": duration},
    }
    req = PackageRequest.model_validate(data)
    ps = PromptService()
    profile = json.dumps(req.model_dump(mode="json"), indent=2)
    return ps.build_package_prompt(
        user_profile=profile,
        trip_preferences="{}",
        knowledge_context="{}",
    )


async def run_once(prompt: str, num_predict: int, label: str) -> None:
    payload = {
        "model": "qwen3.5:397b-cloud",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.4, "num_predict": num_predict},
    }
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=600) as client:
        response = await client.post("http://127.0.0.1:11434/api/chat", json=payload)
        data = response.json()
    elapsed = time.perf_counter() - t0
    ev = data.get("eval_count") or 0
    ed = (data.get("eval_duration") or 0) / 1e9
    ld = (data.get("load_duration") or 0) / 1e6
    ped = (data.get("prompt_eval_duration") or 0) / 1e6
    tps = round(ev / ed, 2) if ed else 0
    out_len = len((data.get("message") or {}).get("content") or "")
    print(
        f"{label}: total_sec={round(elapsed, 1)} gen_tokens={ev} "
        f"tps={tps} load_ms={round(ld)} prompt_eval_ms={round(ped)} out_chars={out_len}"
    )


async def main() -> None:
    for duration in ("1", "5"):
        prompt = build_prompt(duration)
        print(
            f"\n=== duration={duration}d prompt_chars={len(prompt)} "
            f"est_tokens={len(prompt) // 4} ==="
        )
        await run_once(prompt, 256, f"warmup_{duration}d")
        await run_once(prompt, 2048, f"full_{duration}d")


if __name__ == "__main__":
    asyncio.run(main())
