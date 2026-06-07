from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger("policycheck.ai.summary")
HF_URL = "https://api-inference.huggingface.co/models/google/flan-t5-small"
HF_TOKEN_ENV_NAMES = ("HF_TOKEN", "HUGGINGFACE_API_TOKEN", "HUGGING_FACE_HUB_TOKEN")


def _timeout_seconds() -> float:
    try:
        return float(os.environ.get("HF_TIMEOUT_SECONDS", "20"))
    except ValueError:
        return 20.0


def _token_config() -> tuple[str | None, str | None]:
    for name in HF_TOKEN_ENV_NAMES:
        token = os.environ.get(name)
        if token:
            return token, name
    return None, None


def _fallback(
    fallback_summary: str,
    reason: str,
    *,
    status_code: int | None = None,
    token_env_name: str | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    logger.warning(
        "ai_summary_fallback reason=%s hf_token_present=%s hf_token_env=%s status_code=%s timeout_seconds=%s",
        reason,
        bool(token_env_name),
        token_env_name or "none",
        status_code,
        timeout_seconds,
    )
    return {
        "summary": fallback_summary,
        "source": "Deterministic fallback",
        "fallback_reason": reason,
        "hf_status_code": status_code,
        "hf_token_env": token_env_name,
    }


def generate_logged_portfolio_summary(metrics: dict[str, Any], fallback_summary: str) -> dict[str, Any]:
    token, token_env_name = _token_config()
    timeout = _timeout_seconds()
    logger.info(
        "ai_summary_attempt hf_token_present=%s hf_token_env=%s expected_env_vars=%s timeout_seconds=%s",
        bool(token),
        token_env_name or "none",
        ",".join(HF_TOKEN_ENV_NAMES),
        timeout,
    )
    if not token:
        return _fallback(
            fallback_summary,
            "missing_hugging_face_token",
            token_env_name=token_env_name,
            timeout_seconds=timeout,
        )

    prompt = (
        "Write a concise executive summary for an insurance bordereaux validation. "
        "Use this deterministic validation data only. Do not invent facts. "
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
            json={
                "inputs": prompt[:6000],
                "parameters": {"max_new_tokens": 120, "do_sample": False, "return_full_text": False},
                "options": {"wait_for_model": True},
            },
            timeout=timeout,
        )
        logger.info(
            "ai_summary_hf_response status_code=%s hf_token_present=%s hf_token_env=%s",
            response.status_code,
            True,
            token_env_name,
        )
        if response.status_code >= 500:
            return _fallback(
                fallback_summary,
                f"hugging_face_server_error_{response.status_code}",
                status_code=response.status_code,
                token_env_name=token_env_name,
                timeout_seconds=timeout,
            )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list) and payload:
            summary = payload[0].get("generated_text") or payload[0].get("summary_text")
            if summary and summary.strip():
                logger.info(
                    "ai_summary_success status_code=%s hf_token_env=%s",
                    response.status_code,
                    token_env_name,
                )
                return {
                    "summary": summary.strip(),
                    "source": "AI-assisted summary",
                    "fallback_reason": None,
                    "hf_status_code": response.status_code,
                    "hf_token_env": token_env_name,
                }
        if isinstance(payload, dict) and payload.get("error"):
            return _fallback(
                fallback_summary,
                f"hugging_face_payload_error:{str(payload.get('error'))[:120]}",
                status_code=response.status_code,
                token_env_name=token_env_name,
                timeout_seconds=timeout,
            )
        return _fallback(
            fallback_summary,
            f"empty_or_unexpected_hugging_face_payload:{type(payload).__name__}",
            status_code=response.status_code,
            token_env_name=token_env_name,
            timeout_seconds=timeout,
        )
    except requests.Timeout:
        return _fallback(
            fallback_summary,
            "hugging_face_timeout",
            token_env_name=token_env_name,
            timeout_seconds=timeout,
        )
    except requests.RequestException as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        return _fallback(
            fallback_summary,
            exc.__class__.__name__,
            status_code=status_code,
            token_env_name=token_env_name,
            timeout_seconds=timeout,
        )
    except Exception as exc:
        reason = exc.__class__.__name__
        logger.exception(
            "ai_summary_unexpected_error reason=%s hf_token_present=%s hf_token_env=%s",
            reason,
            bool(token_env_name),
            token_env_name or "none",
        )
        return {
            "summary": fallback_summary,
            "source": "Deterministic fallback",
            "fallback_reason": reason,
            "hf_status_code": None,
            "hf_token_env": token_env_name,
        }
