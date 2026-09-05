"""Copyleaks Internet plagiarism + AI detection integration.

Uses Copyleaks v3 Authenticity scan so the same scan can detect:
- Internet plagiarism/similarity
- AI-generated text

No local seed/corpus is required.
"""
import base64
import json
import re
import time
from typing import Any, Dict

import requests

from config import (
    COPYLEAKS_EMAIL,
    COPYLEAKS_API_KEY,
    COPYLEAKS_SANDBOX,
    COPYLEAKS_WEBHOOK_BASE_URL,
    COPYLEAKS_WEBHOOK_SECRET,
)

LOGIN_URL = "https://id.copyleaks.com/v3/account/login/api"
SUBMIT_URL = "https://api.copyleaks.com/v3/scans/submit/file/{scan_id}"

_token_cache = {"token": None, "expires_at": 0.0}


def configured() -> bool:
    return bool(
        COPYLEAKS_EMAIL
        and COPYLEAKS_API_KEY
        and COPYLEAKS_WEBHOOK_BASE_URL
    )


def _login() -> str:
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 300:
        return _token_cache["token"]

    if not COPYLEAKS_EMAIL or not COPYLEAKS_API_KEY:
        raise RuntimeError(
            "Copyleaks credentials are not configured. "
            "Set COPYLEAKS_EMAIL and COPYLEAKS_API_KEY in .env"
        )

    response = requests.post(
        LOGIN_URL,
        json={"email": COPYLEAKS_EMAIL, "key": COPYLEAKS_API_KEY},
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError(
            "Copyleaks login succeeded but no access token was returned"
        )

    _token_cache["token"] = token
    _token_cache["expires_at"] = now + 47 * 3600
    return token


def _scan_id(report_id: int) -> str:
    """Create a Copyleaks-compatible scan ID (3-36 chars)."""
    return re.sub(
        r"[^a-zA-Z0-9_-]",
        "-",
        f"plagiascan-{report_id}-{int(time.time())}",
    )[:36]


def submit_file(file_path: str, filename: str, report_id: int) -> str:
    """Submit a document for Internet plagiarism + AI detection."""
    if not configured():
        raise RuntimeError(
            "Copyleaks is not fully configured. Set COPYLEAKS_EMAIL, "
            "COPYLEAKS_API_KEY, and COPYLEAKS_WEBHOOK_BASE_URL in .env."
        )

    scan_id = _scan_id(report_id)

    with open(file_path, "rb") as fh:
        encoded = base64.b64encode(fh.read()).decode("utf-8")

    return _submit(encoded, filename, scan_id, report_id)


def submit_text(
    text: str,
    report_id: int,
    filename: str = "text-check.txt",
) -> str:
    """Submit pasted text for Internet plagiarism + AI detection."""
    if not configured():
        raise RuntimeError(
            "Copyleaks is not fully configured. Set COPYLEAKS_EMAIL, "
            "COPYLEAKS_API_KEY, and COPYLEAKS_WEBHOOK_BASE_URL in .env."
        )

    scan_id = _scan_id(report_id)
    encoded = base64.b64encode(text.encode("utf-8")).decode("utf-8")
    return _submit(encoded, filename, scan_id, report_id)


def _submit(
    encoded: str,
    filename: str,
    scan_id: str,
    report_id: int,
) -> str:
    token = _login()
    base = COPYLEAKS_WEBHOOK_BASE_URL.rstrip("/")

    payload = {
        "base64": encoded,
        "filename": filename[:255] or "document.txt",
        "properties": {
            "webhooks": {
                "status": (
                    f"{base}/api/copyleaks/webhook/"
                    f"{COPYLEAKS_WEBHOOK_SECRET}/{report_id}/{{STATUS}}"
                ),
                "newResult": (
                    f"{base}/api/copyleaks/webhook/"
                    f"{COPYLEAKS_WEBHOOK_SECRET}/{report_id}/new-result"
                ),
            },
            "sandbox": COPYLEAKS_SANDBOX,
            "scanning": {
                "internet": True,
            },
            "aiGeneratedText": {
                "detect": True,
                "sensitivity": 2,
            },
        },
    }

    response = requests.put(
        SUBMIT_URL.format(scan_id=scan_id),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    return scan_id


def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _percent(value, default=0.0):
    """Convert a provider score to a bounded percentage."""
    number = _num(value, default)
    if 0 <= number <= 1:
        number *= 100
    return max(0.0, min(100.0, number))


def _first(d: Dict[str, Any], *keys, default=None):
    for key in keys:
        if key in d and d[key] is not None:
            return d[key]
    return default


def _internet_score(item: Dict[str, Any]) -> float:
    score = _percent(
        _first(
            item,
            "score",
            "percentage",
            "matchPercentage",
            "similarity",
            "similarityPercent",
            "aggregatedScore",
            default=0,
        )
    )
    if score == 0:
        matched = _num(_first(item, "matchedWords", "identicalWords", default=0))
        total = _num(_first(item, "totalWords", default=0))
        if total > 0:
            score = _percent(matched / total)
    return round(score, 2)


def _dict_nodes(value):
    """Yield nested dictionaries so provider response variants can be read."""
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _dict_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _dict_nodes(child)


def _probability(data: Dict[str, Any], keys) -> float | None:
    value = _first(data, *keys, default=None)
    if value is None or isinstance(value, (dict, list)):
        return None
    return _percent(value)


def _extract_ai_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Extract Copyleaks AI summary from the completed webhook.

    Copyleaks places the AI summary in
    notifications.alerts[*].additionalData for the
    suspected-ai-text alert.
    """
    candidates = []
    for node in _dict_nodes(payload):
        additional = node.get("additionalData")
        if isinstance(additional, str):
            try:
                additional = json.loads(additional)
            except json.JSONDecodeError:
                additional = None
        if isinstance(additional, dict):
            candidates.extend(_dict_nodes(additional))
        candidates.append(node)

    for candidate in candidates:
        ai = _probability(
            candidate,
            (
                "ai", "aiProbability", "ai_probability", "aiGeneratedProbability",
                "aiGeneratedPercent", "aiPercentage", "aiScore",
            ),
        )
        human = _probability(
            candidate,
            ("human", "humanProbability", "human_probability", "humanPercentage"),
        )
        detected = _first(candidate, "aiGenerated", "isAiGenerated", "detected", default=None)
        if ai is None and human is None and not isinstance(detected, bool):
            continue
        if ai is None and isinstance(detected, bool):
            ai = 100.0 if detected else 0.0
        if human is None:
            human = max(0.0, 100.0 - (ai or 0.0))
        ai = ai or 0.0
        human = human or 0.0

        total = ai + human

        if total > 0:
            ai = ai * 100 / total
            human = human * 100 / total
        else:
            ai = 0.0
            human = 100.0

        confidence = _percent(_first(
            candidate,
            "confidence", "confidenceScore", "confidence_score",
            default=max(ai, human),
        ))
        return {
            "ai_probability": round(max(0.0, min(100.0, ai)), 2),
            "human_probability": round(max(0.0, min(100.0, human)), 2),
            "confidence_score": round(max(0.0, min(100.0, confidence)), 2),
            "ai_detected": True,
            "ai_model_version": str(
                candidate.get("modelVersion") or ""
            ),
        }

    # Missing AI data is distinct from a confirmed human result.
    return {
        "ai_probability": 0.0,
        "human_probability": 0.0,
        "confidence_score": 0.0,
        "ai_detected": False,
        "ai_model_version": "",
    }


def parse_completed(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize Copyleaks completed webhook into our report format."""
    results = payload.get("results") or {}
    if not isinstance(results, dict):
        raise ValueError("Copyleaks completed response has an invalid result structure")
    score = results.get("score") or payload.get("score") or {}
    if not isinstance(score, dict):
        raise ValueError("Copyleaks completed response has an invalid score structure")
    has_score = any(
        key in score for key in (
            "aggregatedScore", "score", "totalWords", "identicalWords", "matchedWords"
        )
    )
    internet = results.get("internet") or []
    if not has_score and not internet:
        raise ValueError("Copyleaks completed response contains no scan results")

    similarity = _percent(
        _first(score, "aggregatedScore", "score", default=0)
    )
    total_words = int(
        _num(_first(score, "totalWords", default=0))
    )
    identical_words = int(
        _num(
            _first(
                score,
                "identicalWords",
                "matchedWords",
                default=0,
            )
        )
    )

    if similarity <= 0 and total_words > 0:
        similarity = min(
            100.0,
            identical_words * 100.0 / total_words,
        )

    if not isinstance(internet, list):
        internet = [internet] if isinstance(internet, dict) else []
    ai = _extract_ai_summary(payload)

    return {
        "similarity_percent": round(
            similarity, 2
        ),
        "original_percent": round(
            max(0.0, min(100.0, 100.0 - similarity)), 2
        ),
        "matched_count": len(internet),
        "matched_words": identical_words,
        "total_words": total_words,
        "internet_results": [
            {
                **item,
                "score": _internet_score(item),
                "matched_text": _first(item, "matchedText", "text", "fragment", default=""),
                "source_text": _first(item, "title", "documentTitle", default="Online source"),
            }
            for item in internet if isinstance(item, dict)
        ],
        "ai_probability": ai["ai_probability"],
        "human_probability": ai["human_probability"],
        "confidence_score": ai["confidence_score"],
        "ai_detected": ai["ai_detected"],
        "ai_model_version": ai["ai_model_version"],
        "raw": payload,
    }


def parse_new_result(payload: Dict[str, Any]) -> Dict[str, Any]:
    internet = payload.get("internet")

    if isinstance(internet, list):
        item = internet[0] if internet and isinstance(internet[0], dict) else {}
    elif isinstance(internet, dict):
        item = internet
    else:
        item = payload

    return {
        "result_id": _first(item, "id", "resultId", default=""),
        "title": _first(
            item,
            "title",
            "documentTitle",
            default="Online source",
        ),
        "url": _first(item, "url", "link", default=""),
        "matched_words": int(
            _num(
                _first(
                    item,
                    "matchedWords",
                    "identicalWords",
                    default=0,
                )
            )
        ),
        "score": _internet_score(item),
        "matched_text": _first(item, "matchedText", "text", "fragment", default=""),
        "source_text": _first(item, "title", "documentTitle", default="Online source"),
    }
