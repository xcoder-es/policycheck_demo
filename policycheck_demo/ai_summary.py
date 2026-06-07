from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger("policycheck.ai.summary")
HF_URL = "https://api-inference.huggingface.co/models/google/flan-t5-small"


def _timeout_seconds() -> float:
    try:
        return float(os.environ.get("HF_TIMEOUT_SECONDS", "15"))
    except ValueError:
        return 15.0


def generate_logged_portfolio_summary(metrics: dict[str, Any], fallback_summary: str) -> dict[str, Any]:
    token = os.environ.get("HF_TOKEN")
    timeout = _timeout_seconds()
    logger.info(
        "ai_summary_attempt",
        extra={"hf_token_present": bool(token), "expected_env_var": "HF_TOKEN", "timeout_seconds": timeout},
    )

    if not token:
        reason = "missing HF_TOKEN"
        logger.warning("ai_summary_fallback", extra={"reason": reason, "hf_token_present": False})
        return {"summary": fallback_summary, "source": "Deterministic fallback", "fallback_reason": reason, "hf_status_code": None}

    prompt = (
        "Write a concise executive summary for an insurance bordereaux validation. "
        "Use this deterministic validation data only: "
        f"total policies={metrics.get('total_policies')}, "
        f"compliant={metrics.get('compliant_policies')}, "
        f"warnings={metrics.get('warnings')}, "
        f"breaches={metrics.get('breaches')}, "
        f"high severity issues={metrics.get('high_severity_issues')}, "
        f"exposure reviewed={metrics.get('total_exposure_reviewed')}, "
        f"exposure outside authority={metrics.get('exposure_outside_authority')}, "
        f"most common issue={metrics.get('most_common_issue')}, "
        f"percentage compliant={metrics.get('percentage_compliant')}%."
    )

    try:
        response = requests.post(
            HF_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={"inputs": prompt[:6000], "parameters": {"max_length": 140, "min_length": 30, "do_sample": False}},
            timeout=timeout,
        )
        logger.info("ai_summary_hf_response", extra={"status_code": response.status_code, "hf_token_present": True})
        if response.status_code >= 500:
            reason = f"hugging_face_server_error_{response.status_code}"
            logger.warning("ai_summary_fallback", extra={"reason": reason, "status_code": response.status_code})
            return {"summary": fallback_summary, "source": "Deterministic fallback", "fallback_reason": reason, "hf_status_code": response.status_code}
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list) and payload:
            summary = payload[0].get("generated_text") or payload[0].get("summary_text")
            if summary and summary.strip():
                logger.info("ai_summary_success", extra={"status_code": response.status_code})
                return {"summary": summary.strip(), "source": "AI-assisted summary", "fallback_reason": None, "hf_status_code": response.status_code}
        reason = "empty_or_unexpected_hugging_face_payload"
        logger.warning("ai_summary_fallback", extra={"reason": reason, "status_code": response.status_code})
        return {"summary": fallback_summary, "source": "Deterministic fallback", "fallback_reason": reason, "hf_status_code": response.status_code}
    except requests.Timeout:
        reason = "hugging_face_timeout"
        logger.warning("ai_summary_fallback", extra={"reason": reason, "timeout_seconds": timeout})
        return {"summary": fallback_summary, "source": "Deterministic fallback", "fallback_reason": reason, "hf_status_code": None}
    except requests.RequestException as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        reason = exc.__class__.__name__
        logger.warning("ai_summary_fallback", extra={"reason": reason, "status_code": status_code})
        return {"summary": fallback_summary, "source": "Deterministic fallback", "fallback_reason": reason, "hf_status_code": status_code}
    except Exception as exc:
        reason = exc.__class__.__name__
        logger.exception("ai_summary_unexpected_error", extra={"reason": reason})
        return {"summary": fallback_summary, "source": "Deterministic fallback", "fallback_reason": reason, "hf_status_code": None}
