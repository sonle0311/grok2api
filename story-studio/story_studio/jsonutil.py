"""Extract a JSON object from an LLM reply. Ported from KTV gemini_service."""

import json
import re


def extract_json(text: str) -> dict:
    if not text or not str(text).strip():
        raise ValueError("empty LLM response")
    raw = str(text).strip()
    parsed = _parse(raw)
    if parsed is not None:
        return parsed
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", raw, flags=re.DOTALL).strip()
    for marker in ("```json", "```javascript", "```"):
        if cleaned.startswith(marker):
            cleaned = cleaned[len(marker):]
            break
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    parsed = _parse(cleaned)
    if parsed is not None:
        return parsed
    for pattern in (r"(\{[\s\S]*\})", r"(\[[\s\S]*\])"):
        match = re.search(pattern, cleaned)
        if not match:
            continue
        parsed = _parse(match.group(1))
        if parsed is not None:
            return parsed
    raise ValueError(f"cannot parse JSON: {raw[:300]}")


def _parse(text: str):
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(data, list):
        return {"items": data}
    if not isinstance(data, dict):
        return None
    if "response" in data and ("conversation_id" in data or "num_turns" in data):
        return extract_json(data["response"])
    if isinstance(data.get("content"), str):
        return extract_json(data["content"])
    result = data.get("result")
    if isinstance(result, str):
        return extract_json(result)
    if isinstance(result, dict):
        return result
    return data
