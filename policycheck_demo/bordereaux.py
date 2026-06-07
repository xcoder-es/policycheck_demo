"""Bordereaux parsing, generation, validation and reporting helpers.

The module is deliberately lightweight: standard library only, deterministic
validation rules, no database and no heavy dataframe dependencies.
"""

from __future__ import annotations

import csv
import io
import json
import random
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional, Tuple

from .models import BAA

MAX_CSV_BYTES = 512_000
MAX_CSV_ROWS = 500
DEFAULT_SYNTHETIC_ROWS = 50
ALLOWED_SYNTHETIC_COUNTS = {25, 50, 100}

CANONICAL_COLUMNS = [
    "policy_number",
    "insured_name",
    "bind_date",
    "territory",
    "class_of_business",
    "sum_insured",
    "premium",
    "endorsements",
    "broker",
    "status",
]

COLUMN_SYNONYMS: Dict[str, List[str]] = {
    "policy_number": ["policy_number", "policy no", "policy_no", "policy id", "policy ref", "reference", "policy reference", "policy"],
    "insured_name": ["insured_name", "insured", "client", "policyholder", "customer", "name"],
    "bind_date": ["bind_date", "inception_date", "effective_date", "start_date", "bound_date", "date_bound", "inception"],
    "territory": ["territory", "country", "risk_country", "location", "risk location", "risk_territory"],
    "class_of_business": ["class_of_business", "business_class", "class", "line_of_business", "insurance_line", "cob", "product"],
    "sum_insured": ["sum_insured", "limit", "tsi", "exposure", "insured_value", "value", "limit_of_liability"],
    "premium": ["premium", "gross_premium", "written_premium", "gwp", "net_premium"],
    "endorsements": ["endorsements", "clauses", "required_clauses", "wordings", "conditions", "endorsement"],
    "broker": ["broker", "intermediary", "producer", "placing_broker", "broker_name"],
    "status": ["status", "policy_status", "stage", "state"],
}

REQUIRED_FOR_VALIDATION = ["policy_number", "bind_date", "territory", "class_of_business", "sum_insured", "endorsements"]

SYNTHETIC_INSUREDS = [
    "Northstar Logistics Ltd", "Atlas Retail Group", "Evergreen Hospitality", "Rivergate Manufacturing",
    "Summit Digital Services", "Harbourline Marine", "Cobalt Property Holdings", "Meridian Health Partners",
    "BluePeak Construction", "Asteria Financial Services", "Kingswell Food Group", "NovaTech Systems",
    "Orchard & Lane Estates", "Crownbridge Events", "SignalPoint Media", "Fjordline Energy",
]

SYNTHETIC_BROKERS = [
    "Alderstone Risk Partners", "Marlow & Co Brokers", "Northgate Specialty", "Helios Wholesale",
    "Cavendish Insurance Markets", "Greenwich Placement Services", "Sterling Binder Solutions",
]

FALLBACK_TERRITORIES = ["United Kingdom", "Ireland", "Spain", "Portugal", "France", "Germany", "Netherlands", "Belgium"]
FALLBACK_CLASSES = ["Property", "Casualty", "Cyber", "Professional Indemnity", "Marine Cargo"]
INVALID_TERRITORIES = ["United States", "Canada", "Brazil", "Australia", "Singapore"]
INVALID_CLASSES = ["Aviation", "Political Risk", "Life", "Nuclear", "Motor Fleet"]


@dataclass
class ParseResult:
    rows: List[Dict[str, str]]
    errors: List[str]
    warnings: List[str]
    mapping: Dict[str, str]
    missing_columns: List[str]


def normalise_header(value: str) -> str:
    """Normalise a CSV header so deterministic synonym matching is tolerant."""
    return re.sub(r"[^a-z0-9]+", "", (value or "").strip().lower())


def map_columns(fieldnames: Iterable[str]) -> Tuple[Dict[str, str], List[str]]:
    headers = [field for field in fieldnames if field]
    normalised_to_original = {normalise_header(header): header for header in headers}
    mapping: Dict[str, str] = {}

    for canonical, synonyms in COLUMN_SYNONYMS.items():
        for synonym in synonyms:
            normalised = normalise_header(synonym)
            if normalised in normalised_to_original:
                mapping[canonical] = normalised_to_original[normalised]
                break

    missing = [column for column in REQUIRED_FOR_VALIDATION if column not in mapping]
    return mapping, missing


def parse_bordereaux_csv(content: bytes) -> ParseResult:
    """Parse and map a bordereaux CSV upload without raising UI-breaking errors."""
    errors: List[str] = []
    warnings: List[str] = []

    if not content:
        return ParseResult([], ["The uploaded CSV file is empty."], [], {}, REQUIRED_FOR_VALIDATION[:])

    if len(content) > MAX_CSV_BYTES:
        return ParseResult([], ["The CSV file is too large for this demo. Please upload a file under 512 KB."], [], {}, [])

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1", errors="ignore")
        warnings.append("The CSV was not UTF-8 encoded, so it was read using a tolerant fallback decoder.")

    if not text.strip():
        return ParseResult([], ["The uploaded CSV file does not contain any data."], warnings, {}, REQUIRED_FOR_VALIDATION[:])

    try:
        reader = csv.DictReader(io.StringIO(text))
    except csv.Error:
        return ParseResult([], ["The uploaded file could not be parsed as CSV."], warnings, {}, [])

    if not reader.fieldnames:
        return ParseResult([], ["The CSV must include a header row."], warnings, {}, REQUIRED_FOR_VALIDATION[:])

    mapping, missing_columns = map_columns(reader.fieldnames)
    if not mapping:
        return ParseResult([], ["No recognisable bordereaux columns were found. Please include headers such as policy_number, bind_date, territory and sum_insured."], warnings, mapping, missing_columns)

    if missing_columns:
        warnings.append("Some recommended columns were not recognised: " + ", ".join(missing_columns) + ". Missing values will be reported as validation issues.")

    rows: List[Dict[str, str]] = []
    for index, raw_row in enumerate(reader, start=1):
        if index > MAX_CSV_ROWS:
            warnings.append(f"Only the first {MAX_CSV_ROWS} rows were processed to keep the demo lightweight.")
            break
        if not raw_row or not any((value or "").strip() for value in raw_row.values()):
            continue
        row = {column: "" for column in CANONICAL_COLUMNS}
        for canonical, source_header in mapping.items():
            row[canonical] = (raw_row.get(source_header) or "").strip()
        rows.append(row)

    if not rows:
        errors.append("The CSV did not contain any data rows after the header.")

    return ParseResult(rows, errors, warnings, mapping, missing_columns)


def parse_date(value: str) -> Optional[datetime]:
    value = (value or "").strip().replace(",", "")
    if not value:
        return None
    formats = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y"]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def parse_money(value: str) -> Optional[float]:
    value = (value or "").strip()
    if not value:
        return None
    cleaned = re.sub(r"[^0-9.\-]", "", value)
    if cleaned in {"", ".", "-"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def split_values(value: str) -> List[str]:
    if not value:
        return []
    cleaned = re.sub(r"\b(?:and|or)\b", ",", value, flags=re.IGNORECASE)
    return [part.strip(" .;:-") for part in re.split(r",|;|\||/", cleaned) if part.strip(" .;:-")]


def normalise_value(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def contains_required_endorsement(required: str, provided: List[str]) -> bool:
    required_norm = normalise_value(required)
    return any(required_norm == normalise_value(item) or required_norm in normalise_value(item) for item in provided)


def make_issue(issue_type: str, severity: str, message: str) -> Dict[str, str]:
    return {"type": issue_type, "severity": severity, "message": message}


def validate_row_against_baa(row: Dict[str, str], baa: BAA) -> Dict[str, object]:
    issues: List[Dict[str, str]] = []

    policy_number = (row.get("policy_number") or "").strip()
    if not policy_number:
        issues.append(make_issue("Missing policy number", "medium", "Policy number is missing."))

    bind_date_raw = row.get("bind_date", "")
    bind_date = parse_date(bind_date_raw)
    if not bind_date:
        issues.append(make_issue("Invalid bind date", "high", "Bind date is missing or malformed."))
    elif not (baa.start_date <= bind_date <= baa.end_date):
        issues.append(make_issue("Outside BAA period", "high", f"Bind date {bind_date.date()} is outside the reviewed BAA period."))

    allowed_territories = {normalise_value(item) for item in baa.territory if item}
    territory = row.get("territory", "")
    if not territory:
        issues.append(make_issue("Missing territory", "medium", "Territory is missing."))
    elif allowed_territories and normalise_value(territory) not in allowed_territories:
        issues.append(make_issue("Outside territory", "high", f"Territory '{territory}' is not permitted by the BAA."))

    allowed_classes = {normalise_value(item) for item in baa.class_of_business if item}
    class_of_business = row.get("class_of_business", "")
    if not class_of_business:
        issues.append(make_issue("Missing class", "medium", "Class of business is missing."))
    elif allowed_classes and normalise_value(class_of_business) not in allowed_classes:
        issues.append(make_issue("Unsupported class", "high", f"Class of business '{class_of_business}' is not permitted by the BAA."))

    sum_insured = parse_money(row.get("sum_insured", ""))
    if sum_insured is None:
        issues.append(make_issue("Invalid exposure", "medium", "Sum insured is missing or malformed."))
        sum_insured = 0.0
    elif baa.authority_limit and sum_insured > baa.authority_limit:
        issues.append(make_issue("Above authority limit", "high", f"Sum insured {sum_insured:,.0f} exceeds authority limit {baa.authority_limit:,.0f}."))

    provided_endorsements = split_values(row.get("endorsements", ""))
    missing_endorsements = [endorsement for endorsement in baa.required_endorsements if endorsement and not contains_required_endorsement(endorsement, provided_endorsements)]
    if missing_endorsements:
        issues.append(make_issue("Missing endorsement", "medium", "Missing required endorsements: " + ", ".join(missing_endorsements) + "."))

    highest = "low"
    if any(issue["severity"] == "high" for issue in issues):
        highest = "high"
    elif any(issue["severity"] == "medium" for issue in issues):
        highest = "medium"

    if any(issue["severity"] == "high" for issue in issues):
        status = "Breach"
    elif issues:
        status = "Warning"
    else:
        status = "Compliant"

    return {
        "row": row,
        "policy_number": policy_number or "Unnumbered policy",
        "insured_name": row.get("insured_name") or "Unknown insured",
        "status": status,
        "severity": highest,
        "issues": issues,
        "issue_text": "; ".join(issue["message"] for issue in issues) or "No issues detected.",
        "issue_count": len(issues),
        "sum_insured_value": sum_insured,
        "bind_date_display": bind_date.date().isoformat() if bind_date else (bind_date_raw or "Missing"),
    }


def build_metrics(validated_rows: List[Dict[str, object]]) -> Dict[str, object]:
    total = len(validated_rows)
    compliant = sum(1 for item in validated_rows if item["status"] == "Compliant")
    warning_rows = sum(1 for item in validated_rows if item["status"] == "Warning")
    breach_rows = sum(1 for item in validated_rows if item["status"] == "Breach")
    high_issues = sum(1 for item in validated_rows for issue in item["issues"] if issue["severity"] == "high")
    exposure_reviewed = sum(float(item.get("sum_insured_value") or 0) for item in validated_rows)
    exposure_outside_authority = sum(
        float(item.get("sum_insured_value") or 0)
        for item in validated_rows
        if any(issue["type"] == "Above authority limit" for issue in item["issues"])
    )
    issue_counter = Counter(issue["type"] for item in validated_rows for issue in item["issues"])
    most_common_issue = issue_counter.most_common(1)[0][0] if issue_counter else "None"
    percentage_compliant = round((compliant / total) * 100, 1) if total else 0.0

    return {
        "total_policies": total,
        "compliant_policies": compliant,
        "warnings": warning_rows,
        "breaches": breach_rows,
        "high_severity_issues": high_issues,
        "total_exposure_reviewed": exposure_reviewed,
        "exposure_outside_authority": exposure_outside_authority,
        "most_common_issue": most_common_issue,
        "percentage_compliant": percentage_compliant,
    }


def validate_bordereaux(baa: BAA, rows: List[Dict[str, str]]) -> Dict[str, object]:
    validated_rows = [validate_row_against_baa(row, baa) for row in rows]
    return {"rows": validated_rows, "metrics": build_metrics(validated_rows)}


def choose_allowed(values: List[str], fallback: List[str]) -> List[str]:
    clean = [value for value in values if value]
    return clean or fallback


def generate_synthetic_bordereaux(baa: BAA, count: int = DEFAULT_SYNTHETIC_ROWS) -> List[Dict[str, str]]:
    if count not in ALLOWED_SYNTHETIC_COUNTS:
        count = DEFAULT_SYNTHETIC_ROWS

    rng = random.Random(f"{baa.name}-{baa.start_date.date()}-{baa.end_date.date()}-{count}")
    territories = choose_allowed(baa.territory, FALLBACK_TERRITORIES)
    classes = choose_allowed(baa.class_of_business, FALLBACK_CLASSES)
    endorsements = [endorsement for endorsement in baa.required_endorsements if endorsement]
    authority_limit = baa.authority_limit if baa.authority_limit > 0 else 2_000_000
    period_days = max((baa.end_date - baa.start_date).days, 1)

    rows: List[Dict[str, str]] = []
    for index in range(1, count + 1):
        pattern = index % 10
        bind_date = baa.start_date + timedelta(days=rng.randint(0, period_days))
        territory = rng.choice(territories)
        class_of_business = rng.choice(classes)
        sum_insured = rng.uniform(authority_limit * 0.25, authority_limit * 0.92)
        provided_endorsements = endorsements[:]

        if pattern == 1:
            territory = rng.choice(INVALID_TERRITORIES)
        elif pattern == 2:
            bind_date = baa.end_date + timedelta(days=rng.randint(7, 90))
        elif pattern == 3:
            sum_insured = rng.uniform(authority_limit * 1.08, authority_limit * 1.65)
        elif pattern == 4:
            class_of_business = rng.choice(INVALID_CLASSES)
        elif pattern == 5 and provided_endorsements:
            provided_endorsements = provided_endorsements[:-1]
        elif pattern == 6:
            territory = rng.choice(INVALID_TERRITORIES)
            sum_insured = rng.uniform(authority_limit * 1.1, authority_limit * 1.8)
        elif pattern == 7:
            bind_date = baa.start_date - timedelta(days=rng.randint(10, 120))
            class_of_business = rng.choice(INVALID_CLASSES)

        premium = max(sum_insured * rng.uniform(0.008, 0.035), 250)
        rows.append(
            {
                "policy_number": f"PC-SYN-{index:04d}",
                "insured_name": rng.choice(SYNTHETIC_INSUREDS),
                "bind_date": bind_date.strftime("%Y-%m-%d"),
                "territory": territory,
                "class_of_business": class_of_business,
                "sum_insured": f"{round(sum_insured, 2)}",
                "premium": f"{round(premium, 2)}",
                "endorsements": ", ".join(provided_endorsements),
                "broker": rng.choice(SYNTHETIC_BROKERS),
                "status": "Synthetic portfolio",
            }
        )
    return rows


def rows_to_json(rows: List[Dict[str, str]]) -> str:
    return json.dumps(rows, separators=(",", ":"))


def rows_from_json(value: str) -> List[Dict[str, str]]:
    if not value:
        return []
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    rows: List[Dict[str, str]] = []
    for item in payload[:MAX_CSV_ROWS]:
        if isinstance(item, dict):
            rows.append({column: str(item.get(column, "") or "") for column in CANONICAL_COLUMNS})
    return rows


def generate_exception_report_csv(validated_rows: List[Dict[str, object]], checked_at: Optional[str] = None) -> str:
    checked_at = checked_at or datetime.utcnow().isoformat(timespec="seconds") + "Z"
    output = io.StringIO()
    fieldnames = CANONICAL_COLUMNS + ["validation_status", "severity", "issues", "issue_count", "checked_at"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for item in validated_rows:
        row = {column: (item["row"].get(column, "") if isinstance(item.get("row"), dict) else "") for column in CANONICAL_COLUMNS}
        row.update(
            {
                "validation_status": item.get("status", ""),
                "severity": item.get("severity", ""),
                "issues": item.get("issue_text", ""),
                "issue_count": item.get("issue_count", 0),
                "checked_at": checked_at,
            }
        )
        writer.writerow(row)
    return output.getvalue()


def deterministic_portfolio_summary(metrics: Dict[str, object]) -> str:
    total = metrics.get("total_policies", 0)
    compliant = metrics.get("compliant_policies", 0)
    breaches = metrics.get("breaches", 0)
    warnings = metrics.get("warnings", 0)
    common = metrics.get("most_common_issue") or "None"
    percent = metrics.get("percentage_compliant", 0)
    return (
        f"The bordereaux contains {total} policies. {compliant} policies are compliant "
        f"({percent}% of the portfolio), with {warnings} warnings and {breaches} breaches. "
        f"The most common exception pattern is {common}. High-risk items should be reviewed before submission, reconciliation or binder sign-off."
    )
