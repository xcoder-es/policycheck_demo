"""PolicyCheck demo package.

The package initialiser keeps the legacy app import path stable while routing
portfolio summaries through the logged Hugging Face helper. This preserves the
existing Render entrypoint and avoids making AI mandatory.
"""

from . import ai_utils
from .ai_summary import generate_logged_portfolio_summary


def _logged_generate_portfolio_summary(metrics: dict, fallback_summary: str) -> str:
    return str(generate_logged_portfolio_summary(metrics, fallback_summary)["summary"])


ai_utils.generate_portfolio_summary = _logged_generate_portfolio_summary
