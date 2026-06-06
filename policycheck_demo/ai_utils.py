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
from datetime import datetime
from typing import Dict, List, Optional

try:
    from transformers import pipeline
    _transformers_available = True
except ImportError:
    _transformers_available = False

_summarizer = None

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
    """Summarise a block of text using a small T5 model.

    If the summarizer cannot be loaded, this function returns the
    first ``max_length`` characters of the input text as a naive
    approximation of a summary.
    """
    summarizer = _get_summarizer()
    if summarizer is None:
        # Fallback: return the leading characters of the text
        return text[:max_length] + ("…" if len(text) > max_length else "")
    # Transformers summarizer expects a list of documents
    try:
        summary = summarizer(text, max_length=max_length, min_length=30, do_sample=False)
        return summary[0]["summary_text"]
    except Exception:
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