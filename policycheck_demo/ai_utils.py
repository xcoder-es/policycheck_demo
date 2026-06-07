"""Lightweight extraction helpers for the PolicyCheck digital twin demo.

No local LLM runtime, OCR, torch, or transformers are required. The extractor is
heuristic-first so it stays stable on Render, with an optional remote Hugging
Face summary call when HF_TOKEN is configured.
"""

import os
import re
from datetime import datetime
from typing import Dict, List, Optional

import requests


def _hf_summarize(text: str, max_length: int) -> Optional[str]:
    token = os.environ.get("HF_TOKEN")
    if not token:
        return None
    try:
        response = requests.post(
            "https://api-inference.huggingface.co/models/google/flan-t5-small",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "inputs": text[:6000],
                "parameters": {"max_length": max_length, "min_length": 30, "do_sample": False},
            },
            timeout=20,
        )
        if response.status_code >= 500:
            return None
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list) and payload:
            return payload[0].get("generated_text") or payload[0].get("summary_text")
    except Exception:
        return None
    return None


def summarize(text: str, max_length: int = 120) -> str:
    remote_summary = _hf_summarize(text, max_length)
    if remote_summary:
        return remote_summary
    return text[:max_length] + ("..." if len(text) > max_length else "")


def _normalise_text(text: str) -> str:
    return (
        text.replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u00a0", " ")
        .replace("\r", "\n")
    )


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", _normalise_text(text)).strip()


def _parse_date(value: str) -> Optional[datetime]:
    value = value.strip().strip(".,;:").replace(",", "")
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    return None


def _extract_dates(text: str) -> List[datetime]:
    compact_text = _compact(text)
    patterns = [
        r"\b\d{1,2}/\d{1,2}/\d{4}\b",
        r"\b\d{1,2}-\d{1,2}-\d{4}\b",
        r"\b\d{4}-\d{1,2}-\d{1,2}\b",
        r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?,?\s+\d{4}\b",
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b",
    ]
    dates: List[datetime] = []
    for pattern in patterns:
        for match in re.findall(pattern, compact_text, flags=re.IGNORECASE):
            parsed = _parse_date(match)
            if parsed:
                dates.append(parsed)
    return dates


def _extract_date_after_label(text: str, labels: List[str]) -> Optional[datetime]:
    date_pattern = (
        r"(\d{1,2}/\d{1,2}/\d{4}|\d{1,2}-\d{1,2}-\d{4}|\d{4}-\d{1,2}-\d{1,2}|"
        r"\d{1,2}\s+[A-Za-z]{3,9}\.?,?\s+\d{4}|[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{4})"
    )
    for label in labels:
        match = re.search(rf"{label}\s*(?:date)?\s*[:\-]?\s*{date_pattern}", text, flags=re.IGNORECASE)
        if match:
            parsed = _parse_date(match.group(1))
            if parsed:
                return parsed
    return None


def _extract_labeled_value(text: str, labels: List[str], max_chars: int = 220) -> Optional[str]:
    label_pattern = "|".join(labels)
    match = re.search(rf"(?:{label_pattern})\s*[:\-]\s*(.+)", _normalise_text(text), flags=re.IGNORECASE)
    if not match:
        return None
    value = re.split(r"\n|(?:\s{2,})", match.group(1).strip())[0]
    return value[:max_chars].strip(" .;") or None


def _split_list(value: Optional[str]) -> List[str]:
    if not value:
        return []
    cleaned = re.sub(r"\b(?:and|or)\b", ",", value, flags=re.IGNORECASE)
    cleaned = re.sub(r"\([^)]*\)", "", cleaned)
    return [item.strip(" .;:-") for item in re.split(r",|;|\|/", cleaned) if item.strip(" .;:-")]


def _extract_money(text: str) -> Optional[float]:
    compact_text = _compact(text)
    patterns = [
        r"(?:authority\s+limit|limit\s+of\s+authority|maximum\s+limit|sum\s+insured|limit)\D{0,40}(?:USD|EUR|GBP|NZD|AUD|CAD|US\$|€|£|\$)?\s*([0-9]{1,3}(?:,[0-9]{3})+(?:\.\d{1,2})?|[0-9]+(?:\.\d{1,2})?)",
        r"(?:USD|EUR|GBP|NZD|AUD|CAD|US\$|€|£|\$)\s*([0-9]{1,3}(?:,[0-9]{3})+(?:\.\d{1,2})?|[0-9]+(?:\.\d{1,2})?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, compact_text, flags=re.IGNORECASE)
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except ValueError:
                continue
    return None


def _extract_agreement_name(text: str) -> Optional[str]:
    value = _extract_labeled_value(
        text,
        [r"agreement\s+name", r"binding\s+authority\s+agreement", r"baa\s+name", r"agreement"],
    )
    if value:
        return value
    for line in _normalise_text(text).splitlines()[:12]:
        stripped = line.strip(" -")
        if stripped and ("binding authority" in stripped.lower() or "agreement" in stripped.lower()):
            return stripped[:120]
    return None


def extract_fields_from_baa(text: str) -> Dict[str, object]:
    """Extract structured BAA fields from plain text."""
    normalised = _normalise_text(text)
    compact_text = _compact(normalised)

    start_date = _extract_date_after_label(compact_text, [r"start", r"commencement", r"inception", r"effective\s+from", r"effective", r"from"])
    end_date = _extract_date_after_label(compact_text, [r"end", r"expiry", r"expiration", r"expires", r"termination", r"to"])

    if not start_date or not end_date:
        dates = _extract_dates(normalised)
        if dates:
            start_date = start_date or min(dates)
            end_date = end_date or max(dates)

    territories_raw = _extract_labeled_value(normalised, [r"territories", r"territory", r"territorial\s+limits", r"geographical\s+scope"])
    classes_raw = _extract_labeled_value(normalised, [r"classes\s+of\s+business", r"class\s+of\s+business", r"business\s+classes", r"line\s+of\s+business", r"lines\s+of\s+business"])
    endorsements_raw = _extract_labeled_value(normalised, [r"required\s+endorsements", r"mandatory\s+endorsements", r"endorsements", r"clauses"])

    return {
        "agreement_name": _extract_agreement_name(normalised),
        "start_date": start_date,
        "end_date": end_date,
        "territory": _split_list(territories_raw),
        "class_of_business": _split_list(classes_raw),
        "authority_limit": _extract_money(compact_text),
        "required_endorsements": _split_list(endorsements_raw),
    }


def extract_policy_fields(text: str) -> Dict[str, object]:
    """Attempt to extract high-level fields from a policy document."""
    normalised = _normalise_text(text)
    compact_text = _compact(normalised)
    bind_date = _extract_date_after_label(compact_text, [r"bind", r"bound", r"inception", r"effective", r"start"])
    if not bind_date:
        dates = _extract_dates(normalised)
        bind_date = dates[0] if dates else None

    territory_raw = _extract_labeled_value(normalised, [r"territory", r"territorial\s+limits"])
    class_raw = _extract_labeled_value(normalised, [r"class\s+of\s+business", r"line\s+of\s+business", r"class"])
    endorsements_raw = _extract_labeled_value(normalised, [r"endorsements", r"clauses"])

    return {
        "bind_date": bind_date,
        "territory": territory_raw,
        "class_of_business": class_raw,
        "sum_insured": _extract_money(compact_text),
        "endorsements": _split_list(endorsements_raw),
    }
