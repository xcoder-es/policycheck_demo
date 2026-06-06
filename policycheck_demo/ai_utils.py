"""
ai_utils.py
-----------

This module provides helper functions that demonstrate the use of an
open‑source language model to extract structured information from
insurance documents.  It is deliberately lightweight and may not
produce perfect results on arbitrary input, but it illustrates how
modern AI techniques can enrich an underwriting workflow.

The key functions are:

* ``summarize(text)`` – produce a concise summary using a pre‑trained
  text‑to‑text model (T5 small).  If the required model is not
  available or cannot be downloaded in the execution environment, the
  function gracefully falls back to returning a short excerpt from the
  original text.
* ``extract_fields_from_baa(text)`` – attempt to extract important
  fields from a BAA document.  It first summarises the document and
  then uses simple pattern matching to look for dates, territories,
  classes of business, and monetary limits.  In a production system
  you would use a fine‑tuned model or rules engine.
* ``extract_policy_fields(text)`` – similar to the above but aimed at
  individual policy documents.
"""

import re
import os
import requests
from datetime import datetime
from typing import Dict, List, Optional

try:
    # The local transformers pipeline is optional; in many deployments we
    # prefer to call the Hugging Face Inference API instead of loading
    # models locally. If transformers cannot be imported the summarizer
    # will fall back to the remote API or a naive truncation.
    from transformers import pipeline
    _transformers_available = True
except ImportError:
    _transformers_available = False

_summarizer = None

# -----------------------------------------------------------------------------
# Hugging Face Inference API integration
#
# To avoid downloading and storing large model weights in memory‑limited
# environments (e.g. Render free tier), we first attempt to call the
# Hugging Face Inference API. The API requires a personal access token with
# permission to make inference calls. Set the token in the environment
# variable ``HF_TOKEN``. See https://huggingface.co/settings/tokens
#
# The API endpoint returns a list of objects with either ``generated_text``
# or ``summary_text`` keys depending on the model.

def _hf_summarize(text: str, max_length: int) -> Optional[str]:
    """Attempt to summarise text via the Hugging Face Inference API.

    If a token is not configured or the API call fails, return ``None`` so that
    the caller can fall back to another strategy.
    """
    token = os.environ.get("HF_TOKEN")
    if not token:
        return None
    url = "https://api-inference.huggingface.co/models/google/flan-t5-small"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "inputs": text,
        "parameters": {
            "max_length": max_length,
            "min_length": 30,
            "do_sample": False,
        },
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        # A 503 status code indicates the model is loading; retry logic could be
        # added here if desired, but for simplicity we bail out and fall back.
        if response.status_code >= 500:
            return None
        response.raise_for_status()
        result = response.json()
        if isinstance(result, dict) and result.get("error"):
            return None
        if isinstance(result, list) and result:
            item = result[0]
            # flan‑t5 returns ``generated_text``, whereas other summarization models
            # may return ``summary_text``.
            return item.get("generated_text") or item.get("summary_text")
        return None
    except Exception:
        return None

def _get_summarizer():
    """Lazily load the T5 summarizer.

    Loading the model may download weights (~240MB) on first use.  If
    ``transformers`` is not installed or the download fails, None is
    returned and the caller must fall back to another strategy.
    """
    global _summarizer
    if _summarizer is not None:
        return _summarizer
    if not _transformers_available:
        return None
    try:
        model_name = "t5-small"
        _summarizer = pipeline(
            "summarization", model=model_name, tokenizer=model_name, framework="pt"
        )
        return _summarizer
    except Exception:
        # model download failure or missing dependencies (e.g. torch)
        return None


def summarize(text: str, max_length: int = 120) -> str:
    """Summarise a block of text using an available summarization strategy.

    The function attempts the following strategies in order:

    1. Call the Hugging Face Inference API if an access token is provided in
       the ``HF_TOKEN`` environment variable. This avoids loading large models
       locally and is ideal for memory‑constrained deployments.
    2. Use a local Transformers pipeline (T5‑small) if the ``transformers``
       and ``torch`` libraries are installed and the model can be loaded.
    3. Fall back to returning the first ``max_length`` characters of the
       original text as a naive approximation.
    """
    # First try the remote inference API
    remote_summary = _hf_summarize(text, max_length)
    if remote_summary:
        return remote_summary
    # If remote call failed or not configured, try local summarizer
    summarizer = _get_summarizer()
    if summarizer is not None:
        try:
            result = summarizer(text, max_length=max_length, min_length=30, do_sample=False)
            return result[0].get("summary_text", text[:max_length] + ("…" if len(text) > max_length else ""))
        except Exception:
            pass
    # Final fallback: return the leading characters
    return text[:max_length] + ("…" if len(text) > max_length else "")


def _extract_dates(text: str) -> List[datetime]:
    """Extract date strings from text and parse them into datetime objects.

    This uses a simple regular expression to find dates in DD/MM/YYYY or
    YYYY-MM-DD formats.  In practice you may need a more robust date
    parser (e.g. dateparser library).
    """
    date_patterns = [
        r"(\d{1,2}/\d{1,2}/\d{4})",
        r"(\d{4}-\d{1,2}-\d{1,2})",
    ]
    dates: List[datetime] = []
    for pattern in date_patterns:
        for match in re.findall(pattern, text):
            try:
                # Try both day-first and year-first formats
                if "/" in match:
                    dates.append(datetime.strptime(match, "%d/%m/%Y"))
                else:
                    dates.append(datetime.strptime(match, "%Y-%m-%d"))
            except ValueError:
                continue
    return dates


def _extract_money(text: str) -> Optional[float]:
    """Extract the first monetary amount from text (e.g. 2,000,000).

    Returns None if no number with thousands separators is found.
    """
    match = re.search(r"\b([0-9]{1,3}(?:,[0-9]{3})+)\b", text)
    if match:
        amount_str = match.group(1).replace(",", "")
        try:
            return float(amount_str)
        except ValueError:
            return None
    return None


def extract_fields_from_baa(text: str) -> Dict[str, object]:
    """Attempt to extract key fields from a BAA document.

    The function returns a dictionary with the following keys:
        * ``start_date`` and ``end_date`` (datetime objects or None)
        * ``territory`` (list of territories, if any identified)
        * ``class_of_business`` (list of classes of business)
        * ``authority_limit`` (float or None)
        * ``required_endorsements`` (list of strings)

    This is a best‑effort extraction using simple heuristics.  It
    illustrates how you might apply a language model to capture
    structured data from unstructured documents, but it does not
    guarantee accuracy.
    """
    summary = summarize(text)
    result: Dict[str, object] = {
        "start_date": None,
        "end_date": None,
        "territory": [],
        "class_of_business": [],
        "authority_limit": None,
        "required_endorsements": [],
    }
    # Dates: pick earliest and latest dates found in the summary
    dates = _extract_dates(summary)
    if dates:
        result["start_date"] = min(dates)
        result["end_date"] = max(dates)
    # Territory: look for sequences of country names separated by commas
    territory_match = re.search(
        r"(?:territory|territories|territorial)\s*:\s*([A-Za-z,\s]+)", summary, re.IGNORECASE
    )
    if territory_match:
        territories = [t.strip() for t in territory_match.group(1).split(",") if t.strip()]
        result["territory"] = territories
    # Class of business
    class_match = re.search(
        r"classes?\s+of\s+business\s*:\s*([A-Za-z,\s]+)", summary, re.IGNORECASE
    )
    if class_match:
        classes = [c.strip() for c in class_match.group(1).split(",") if c.strip()]
        result["class_of_business"] = classes
    # Authority limit
    amount = _extract_money(summary)
    result["authority_limit"] = amount
    # Endorsements: look for “endorsements: list” pattern
    end_match = re.search(
        r"endorsements?\s*:\s*([A-Za-z,\s]+)", summary, re.IGNORECASE
    )
    if end_match:
        endorsements = [e.strip() for e in end_match.group(1).split(",") if e.strip()]
        result["required_endorsements"] = endorsements
    return result


def extract_policy_fields(text: str) -> Dict[str, object]:
    """Attempt to extract high‑level fields from a policy document.

    Returns a dictionary containing keys ``bind_date``, ``territory``,
    ``class_of_business``, ``sum_insured`` and ``endorsements``.  All
    fields are optional; missing values are set to None or empty lists.
    As with the BAA extractor, this uses naive heuristics and is
    intended only as a demonstration.
    """
    summary = summarize(text)
    result: Dict[str, object] = {
        "bind_date": None,
        "territory": None,
        "class_of_business": None,
        "sum_insured": None,
        "endorsements": [],
    }
    # Bind date: look for a single date
    dates = _extract_dates(summary)
    if dates:
        result["bind_date"] = dates[0]
    # Territory: pick first country name after 'territory:'
    territory_match = re.search(
        r"territory\s*:\s*([A-Za-z\s]+)", summary, re.IGNORECASE
    )
    if territory_match:
        result["territory"] = territory_match.group(1).strip()
    # Class of business
    class_match = re.search(
        r"class\s+of\s+business\s*:\s*([A-Za-z\s]+)", summary, re.IGNORECASE
    )
    if class_match:
        result["class_of_business"] = class_match.group(1).strip()
    # Sum insured
    amount = _extract_money(summary)
    result["sum_insured"] = amount
    # Endorsements
    end_match = re.search(
        r"endorsements?\s*:\s*([A-Za-z,\s]+)", summary, re.IGNORECASE
    )
    if end_match:
        endorsements = [e.strip() for e in end_match.group(1).split(",") if e.strip()]
        result["endorsements"] = endorsements
    return result