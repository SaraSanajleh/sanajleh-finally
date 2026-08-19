"""Extract and parse JSON from LLM text responses."""

from __future__ import annotations

import json
import re

from app.core.exceptions import LLMResponseParseError


_JSON_FENCE_PATTERN = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)
_JSON_OBJECT_PATTERN = re.compile(r"\{[\s\S]*\}")
_MISSING_DAY_BRACE = re.compile(r"\}\s*,?\s*(\"(?:day_number|day_title)\"\s*:)")
_UNCLOSED_STRING_ARRAY = re.compile(
    r'("(?:tips|included|not_included|highlights|special_touches)"\s*:\s*\['
    r'(?:\s*"(?:\\.|[^"\\])*"\s*,?\s*)+)'
    r"\}"
)


def _close_open_containers(text: str) -> str:
    """Append missing ] and } in LIFO order based on unclosed containers."""
    stack: list[str] = []
    in_string = False
    escape = False
    for ch in text:
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            stack.append("}")
        elif ch == "[":
            stack.append("]")
        elif ch in ("}", "]") and stack and stack[-1] == ch:
            stack.pop()
    return text + "".join(reversed(stack))


def _package_parse_score(parsed: dict) -> int:
    """Prefer repaired objects that still contain the itinerary spine."""
    score = 0
    if isinstance(parsed.get("days"), list) and parsed["days"]:
        score += 50
    if isinstance(parsed.get("daily_itinerary"), list) and parsed["daily_itinerary"]:
        score += 50
    for key in (
        "trip_title",
        "welcome_message",
        "budget_summary",
        "trip_details",
        "explanations",
        "why_you_will_love_this",
        "trip_description",
    ):
        if key in parsed:
            score += 2
    # Nested mistake: itinerary buried under trip_description — still salvageable.
    desc = parsed.get("trip_description")
    if isinstance(desc, dict) and isinstance(desc.get("daily_itinerary"), list):
        score += 40
    return score


def _try_repair_truncated_json(text: str) -> dict | None:
    """
    Best-effort repair when the model hits max_tokens mid-object.

    Tries closing open containers on the full fragment first, then walks
    backward. Prefers repairs that still include daily_itinerary.
    """
    start = text.find("{")
    if start < 0:
        return None

    fragment = text[start:].strip()
    best: dict | None = None
    best_score = -1

    for end in range(len(fragment), max(len(fragment) // 2, 20), -1):
        candidate = fragment[:end].rstrip()

        # Dangling `"key":` with no value → drop that key.
        candidate = re.sub(r',?\s*"[^"]*"\s*:\s*$', "", candidate)
        # Trailing comma before we close containers.
        candidate = re.sub(r",\s*$", "", candidate)

        # Close an unfinished string using a structural walk (not raw quote count —
        # escaped quotes inside strings make count('"') % 2 unreliable).
        if not candidate.endswith('"'):
            in_string = False
            escape = False
            for ch in candidate:
                if in_string:
                    if escape:
                        escape = False
                    elif ch == "\\":
                        escape = True
                    elif ch == '"':
                        in_string = False
                    continue
                if ch == '"':
                    in_string = True
            if in_string:
                candidate += '"'

        repaired = _close_open_containers(candidate)
        try:
            parsed = json.loads(repaired)
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            continue
        score = _package_parse_score(parsed)
        if score > best_score:
            best = parsed
            best_score = score
            # Perfect enough: itinerary present at root.
            if score >= 50:
                return best
    return best


def _fix_common_llm_json_syntax(text: str) -> str:
    """Repair frequent gpt-oss / cloud-model JSON mistakes (still a full object)."""
    # `},"day_number":` → `}, {"day_number":`  (forgot `{` between itinerary days)
    text = _MISSING_DAY_BRACE.sub(r"}, {\1", text)
    # `"tips":["..."},{` → `"tips":["..."]}, {`  (forgot `]` on string arrays)
    text = _UNCLOSED_STRING_ARRAY.sub(r"\1]}", text)
    return text


def _sanitize_llm_text(text: str) -> str:
    """Normalize fancy punctuation that often breaks JSON from cloud models."""
    replacements = {
        "\u2011": "-",  # non-breaking hyphen
        "\u2013": "-",  # en dash
        "\u2014": "-",  # em dash
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\ufeff": "",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    # Strip control chars except newline/tab/cr.
    return "".join(ch for ch in text if ch >= " " or ch in "\n\t\r")


def extract_json_object(text: str) -> dict:
    """
    Extract a JSON object from raw LLM output.

    Handles markdown fences, surrounding prose, thinking traces, and lightly
    truncated JSON.
    """
    cleaned = _sanitize_llm_text(text.strip())
    if not cleaned:
        raise LLMResponseParseError("LLM returned empty response")

    fence_match = _JSON_FENCE_PATTERN.search(cleaned)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    # If the model buried JSON after a long thinking preamble, start at the
    # first real schema KEY (`"welcome_message":`), not prose that names fields.
    schema_key = re.search(
        r'"(?:welcome_message|daily_itinerary|trip_title|budget_summary|'
        r'essential_travel_tips|Essential Travel Tips)"\s*:',
        cleaned,
    )
    if schema_key:
        brace = cleaned.rfind("{", 0, schema_key.start() + 1)
        if brace >= 0:
            cleaned = cleaned[brace:]

    cleaned = _fix_common_llm_json_syntax(cleaned)

    for candidate in (cleaned, _close_open_containers(cleaned)):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    object_match = _JSON_OBJECT_PATTERN.search(cleaned)
    if object_match:
        chunk = _fix_common_llm_json_syntax(object_match.group(0))
        try:
            parsed = json.loads(chunk)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError as exc:
            repaired = _try_repair_truncated_json(chunk)
            if repaired is not None:
                return repaired
            raise LLMResponseParseError(
                f"Failed to parse JSON object: {exc}. "
                "Response looks truncated or invalid — retry with shorter text fields."
            ) from exc

    repaired = _try_repair_truncated_json(cleaned)
    if repaired is not None:
        return repaired

    preview = cleaned[:240].replace("\n", " ")
    raise LLMResponseParseError(
        "No valid JSON object found in LLM response"
        + (f" (starts with: {preview!r})" if preview else "")
    )
