from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger("policycheck.ai.summary")
HF_LEGACY_URL = "https://api-inference.huggingface.co/models/google/flan-t5-small"
HF_ROUTER_URL = "https://router.huggingface.co/v1/chat/completions"
HF_TOKEN_ENV_NAMES = ("HF_TOKEN", "HUGGINGFACE_API_TOKEN", "HUGGING_FACE_HUB_TOKEN")
DEFAULT_HF_SUMMARY_MODEL = "deepseek-ai/DeepSeek-V4-Pro"


def _timeout_seconds() -> float:
    try:
        return float(os.environ.get("HF_TIMEOUT_SECONDS", "20"))
    except ValueError:
        return 20.0


def _summary_model() -> str:
    return os.environ.get("HF_SUMMARY_MODEL", DEFAULT_HF_SUMMARY_MODEL)


def _token_config() -> tuple[str | None, str | None]:
    for name in HF_TOKEN_ENV_NAMES:
        token = os.environ.get(name)
        if token:
            return token, name
    return None, None


def _safe_body(response: requests.Response, max_chars: int = 220) -> str:
    return response.text.replace("\n", " ").replace("\r", " ")[:max_chars]


def _fallback(
    fallback_summary: str,
    reason: str,
    *,
    status_code: int | None = None,
    token_env_name: str | None = None,
    timeout_seconds: float | None = None,
    endpoint: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    logger.warning(
        "ai_summary_fallback reason=%s hf_token_present=%s hf_token_env=%s endpoint=%s model=%s status_code=%s timeout_seconds=%s",
        reason,
        bool(token_env_name),
        token_env_name or "none",
        endpoint or "none",
        model or "none",
        status_code,
        timeout_seconds,
    )
    return {
        "summary": fallback_summary,
        "source": "Deterministic fallback",
        "fallback_reason": reason,
        "hf_status_code": status_code,
        "hf_token_env": token_env_name,
        "hf_endpoint": endpoint,
        "hf_model": model,
    }


def _build_prompt(metrics: dict[str, Any]) -> str:
    return (
        "Write a concise executive summary for an insurance bordereaux validation. "
        "Use this deterministic validation data only. Do not invent facts. "
        "Do not claim legal or regulatory certainty. "
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


def _parse_router_payload(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    message = first.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
    text = first.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    return None


def _parse_legacy_payload(payload: Any) -> str | None:
    if isinstance(payload, list) and payload:
        first = payload[0]
        if isinstance(first, dict):
            summary = first.get("generated_text") or first.get("summary_text")
            if isinstance(summary, str) and summary.strip():
                return summary.strip()
    return None


def _request_router_summary(token: str, token_env_name: str, prompt: str, timeout: float) -> tuple[str | None, int | None, str | None]:
    model = _summary_model()
    try:
        response = requests.post(
            HF_ROUTER_URL,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You write concise executive summaries from deterministic insurance validation metrics.",
                    },
                    {"role": "user", "content": prompt[:6000]},
                ],
                "max_tokens": 140,
                "temperature": 0,
                "stream": False,
            },
            timeout=timeout,
        )
        logger.info(
            "ai_summary_hf_response endpoint=router status_code=%s hf_token_present=True hf_token_env=%s model=%s",
            response.status_code,
            token_env_name,
            model,
        )
        if response.status_code >= 400:
            logger.warning(
                "ai_summary_router_http_error status_code=%s model=%s body=%s",
                response.status_code,
                model,
                _safe_body(response),
            )
        if response.status_code >= 500:
            return None, response.status_code, f"router_server_error_{response.status_code}"
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and payload.get("error"):
            return None, response.status_code, f"router_payload_error:{str(payload.get('error'))[:120]}"
        summary = _parse_router_payload(payload)
        if summary:
            return summary, response.status_code, None
        return None, response.status_code, f"router_unexpected_payload:{type(payload).__name__}"
    except requests.Timeout:
        return None, None, "router_timeout"
    except requests.ConnectionError:
        return None, None, "router_connection_error"
    except requests.RequestException as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        return None, status_code, f"router_{exc.__class__.__name__}"


def _request_legacy_summary(token: str, token_env_name: str, prompt: str, timeout: float) -> tuple[str | None, int | None, str | None]:
    try:
        response = requests.post(
            HF_LEGACY_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={
                "inputs": prompt[:6000],
                "parameters": {"max_new_tokens": 120, "do_sample": False, "return_full_text": False},
                "options": {"wait_for_model": True},
            },
            timeout=timeout,
        )
        logger.info(
            "ai_summary_hf_response endpoint=legacy status_code=%s hf_token_present=True hf_token_env=%s model=google/flan-t5-small",
            response.status_code,
            token_env_name,
        )
        if response.status_code >= 500:
            return None, response.status_code, f"legacy_server_error_{response.status_code}"
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and payload.get("error"):
            return None, response.status_code, f"legacy_payload_error:{str(payload.get('error'))[:120]}"
        summary = _parse_legacy_payload(payload)
        if summary:
            return summary, response.status_code, None
        return None, response.status_code, f"legacy_unexpected_payload:{type(payload).__name__}"
    except requests.Timeout:
        return None, None, "legacy_timeout"
    except requests.ConnectionError:
        return None, None, "legacy_connection_error"
    except requests.RequestException as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        return None, status_code, f"legacy_{exc.__class__.__name__}"


def generate_logged_portfolio_summary(metrics: dict[str, Any], fallback_summary: str) -> dict[str, Any]:
    token, token_env_name = _token_config()
    timeout = _timeout_seconds()
    model = _summary_model()
    logger.info(
        "ai_summary_attempt hf_token_present=%s hf_token_env=%s expected_env_vars=%s endpoint=router_primary legacy_fallback=True model=%s timeout_seconds=%s",
        bool(token),
        token_env_name or "none",
        ",".join(HF_TOKEN_ENV_NAMES),
        model,
        timeout,
    )
    if not token:
        return _fallback(
            fallback_summary,
            "missing_hugging_face_token",
            token_env_name=token_env_name,
            timeout_seconds=timeout,
            endpoint="none",
            model=model,
        )

    prompt = _build_prompt(metrics)
    summary, status_code, reason = _request_router_summary(token, token_env_name or "unknown", prompt, timeout)
    if summary:
        logger.info("ai_summary_success endpoint=router status_code=%s hf_token_env=%s model=%s", status_code, token_env_name, model)
        return {
            "summary": summary,
            "source": "AI-assisted summary",
            "fallback_reason": None,
            "hf_status_code": status_code,
            "hf_token_env": token_env_name,
            "hf_endpoint": "router",
            "hf_model": model,
        }

    logger.warning(
        "ai_summary_router_failed reason=%s status_code=%s hf_token_env=%s model=%s; trying legacy endpoint",
        reason,
        status_code,
        token_env_name,
        model,
    )
    legacy_summary, legacy_status, legacy_reason = _request_legacy_summary(token, token_env_name or "unknown", prompt, timeout)
    if legacy_summary:
        logger.info(
            "ai_summary_success endpoint=legacy status_code=%s hf_token_env=%s model=google/flan-t5-small",
            legacy_status,
            token_env_name,
        )
        return {
            "summary": legacy_summary,
            "source": "AI-assisted summary",
            "fallback_reason": None,
            "hf_status_code": legacy_status,
            "hf_token_env": token_env_name,
            "hf_endpoint": "legacy",
            "hf_model": "google/flan-t5-small",
        }

    return _fallback(
        fallback_summary,
        f"router_failed:{reason};legacy_failed:{legacy_reason}",
        status_code=legacy_status or status_code,
        token_env_name=token_env_name,
        timeout_seconds=timeout,
        endpoint="router+legacy",
        model=f"{model}|google/flan-t5-small",
    )
