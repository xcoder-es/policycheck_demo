from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import io

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .ai_utils import extract_fields_from_baa, extract_policy_fields, generate_portfolio_summary
from .bordereaux import (
    ALLOWED_SYNTHETIC_COUNTS,
    DEFAULT_SYNTHETIC_ROWS,
    deterministic_portfolio_summary,
    generate_exception_report_csv,
    generate_synthetic_bordereaux,
    parse_bordereaux_csv,
    rows_from_json,
    rows_to_json,
    validate_bordereaux,
)
from .checker import check_bordereau_delays, check_policy_against_baa
from .dashboard import build_dashboard_data
from .models import BAA, Policy
from .pdf_utils import extract_text_from_pdf_bytes

app = FastAPI()
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

BAA_FORM_KEYS = [
    "baa_name",
    "baa_start_date",
    "baa_end_date",
    "baa_territory",
    "baa_class",
    "baa_authority_limit",
    "baa_endorsements",
    "baa_text",
]


def empty_baa_form() -> Dict[str, str]:
    return {key: "" for key in BAA_FORM_KEYS}


def index_context(
    baa_form=None,
    baa_extraction_message=None,
    baa_extraction_error=None,
    bordereaux_errors=None,
    bordereaux_warnings=None,
):
    return {
        "baa_form": baa_form or empty_baa_form(),
        "baa_extraction_message": baa_extraction_message,
        "baa_extraction_error": baa_extraction_error,
        "bordereaux_errors": bordereaux_errors or [],
        "bordereaux_warnings": bordereaux_warnings or [],
        "allowed_row_counts": sorted(ALLOWED_SYNTHETIC_COUNTS),
        "default_row_count": DEFAULT_SYNTHETIC_ROWS,
    }


def form_from_baa_inputs(
    baa_name,
    baa_start_date,
    baa_end_date,
    baa_territory,
    baa_class,
    baa_authority_limit,
    baa_endorsements,
    baa_text,
):
    return {
        "baa_name": baa_name or "",
        "baa_start_date": baa_start_date or "",
        "baa_end_date": baa_end_date or "",
        "baa_territory": baa_territory or "",
        "baa_class": baa_class or "",
        "baa_authority_limit": baa_authority_limit or "",
        "baa_endorsements": baa_endorsements or "",
        "baa_text": baa_text or "",
    }


def format_date_value(value: object) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    return ""


def build_baa_form_from_extraction(text: str, filename: Optional[str] = None) -> Dict[str, str]:
    extracted = extract_fields_from_baa(text)
    form = empty_baa_form()
    form["baa_name"] = str(extracted.get("agreement_name") or filename or "Uploaded BAA")
    form["baa_start_date"] = format_date_value(extracted.get("start_date"))
    form["baa_end_date"] = format_date_value(extracted.get("end_date"))
    form["baa_territory"] = ", ".join(extracted.get("territory") or [])
    form["baa_class"] = ", ".join(extracted.get("class_of_business") or [])
    authority_limit = extracted.get("authority_limit")
    form["baa_authority_limit"] = str(int(authority_limit)) if authority_limit else ""
    form["baa_endorsements"] = ", ".join(extracted.get("required_endorsements") or [])
    form["baa_text"] = text
    return form


async def read_uploaded_document(file: Optional[UploadFile]) -> str:
    if not file or not file.filename:
        return ""
    content = await file.read()
    if not content:
        return ""
    filename = file.filename.lower()
    content_type = (file.content_type or "").lower()
    if filename.endswith(".pdf") or content_type == "application/pdf":
        return extract_text_from_pdf_bytes(content)
    return content.decode("utf-8", errors="ignore")


def parse_baa_inputs(
    name,
    start_date_str,
    end_date_str,
    territory_str,
    class_str,
    authority_limit_str,
    endorsements_str,
    baa_text,
) -> BAA:
    text = baa_text or ""
    name = name or "Uploaded BAA"
    if text and (
        not start_date_str
        or not end_date_str
        or not territory_str
        or not class_str
        or not authority_limit_str
        or not endorsements_str
    ):
        extracted = extract_fields_from_baa(text)
        if (not name or name == "Uploaded BAA") and extracted.get("agreement_name"):
            name = str(extracted["agreement_name"])
        if not start_date_str and extracted.get("start_date"):
            start_date_str = extracted["start_date"].strftime("%Y-%m-%d")
        if not end_date_str and extracted.get("end_date"):
            end_date_str = extracted["end_date"].strftime("%Y-%m-%d")
        if not territory_str and extracted.get("territory"):
            territory_str = ", ".join(extracted["territory"])
        if not class_str and extracted.get("class_of_business"):
            class_str = ", ".join(extracted["class_of_business"])
        if not authority_limit_str and extracted.get("authority_limit"):
            authority_limit_str = str(int(extracted["authority_limit"]))
        if not endorsements_str and extracted.get("required_endorsements"):
            endorsements_str = ", ".join(extracted["required_endorsements"])
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d") if start_date_str else datetime.now()
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d") if end_date_str else datetime.now()
    territory = [item.strip() for item in territory_str.split(",") if item.strip()] if territory_str else []
    class_of_business = [item.strip() for item in class_str.split(",") if item.strip()] if class_str else []
    try:
        authority_limit = float(authority_limit_str.replace(",", "")) if authority_limit_str else 0.0
    except Exception:
        authority_limit = 0.0
    endorsements = [item.strip() for item in endorsements_str.split(",") if item.strip()] if endorsements_str else []
    return BAA(
        name=name,
        start_date=start_date,
        end_date=end_date,
        territory=territory,
        class_of_business=class_of_business,
        authority_limit=authority_limit,
        required_endorsements=endorsements,
    )


def parse_policy_inputs(
    policy_number,
    bind_date_str,
    territory,
    class_of_business,
    sum_insured_str,
    endorsements_str,
    policy_text,
) -> Policy:
    policy_number = policy_number or "Policy"
    if policy_text and (not bind_date_str or not territory or not class_of_business or not sum_insured_str):
        extracted = extract_policy_fields(policy_text)
        if not bind_date_str and extracted.get("bind_date"):
            bind_date_str = extracted["bind_date"].strftime("%Y-%m-%d")
        if not territory and extracted.get("territory"):
            territory = extracted["territory"]
        if not class_of_business and extracted.get("class_of_business"):
            class_of_business = extracted["class_of_business"]
        if not sum_insured_str and extracted.get("sum_insured"):
            sum_insured_str = str(int(extracted["sum_insured"]))
        if not endorsements_str and extracted.get("endorsements"):
            endorsements_str = ", ".join(extracted["endorsements"])
    bind_date = datetime.strptime(bind_date_str, "%Y-%m-%d") if bind_date_str else datetime.now()
    try:
        sum_insured = float(sum_insured_str.replace(",", "")) if sum_insured_str else 0.0
    except Exception:
        sum_insured = 0.0
    endorsements = [item.strip() for item in endorsements_str.split(",") if item.strip()] if endorsements_str else []
    return Policy(
        policy_number=policy_number,
        bind_date=bind_date,
        territory=territory or "",
        class_of_business=class_of_business or "",
        sum_insured=sum_insured,
        endorsements=endorsements,
        text=policy_text,
    )


def build_baa_from_form_values(*values) -> BAA:
    return parse_baa_inputs(*values)


def render_mass_results(request: Request, baa: BAA, rows: List[Dict[str, str]], source_label: str, parse_warnings=None) -> HTMLResponse:
    validation = validate_bordereaux(baa, rows)
    metrics = validation["metrics"]
    fallback_summary = deterministic_portfolio_summary(metrics)
    executive_summary = generate_portfolio_summary(metrics, fallback_summary)
    summary_source = "Deterministic fallback" if executive_summary == fallback_summary else "AI-assisted summary"
    report_csv = generate_exception_report_csv(validation["rows"])
    dashboard_data = build_dashboard_data(validation["rows"], metrics)
    return templates.TemplateResponse(
        request,
        "mass_results.html",
        {
            "baa": baa,
            "rows": validation["rows"],
            "metrics": metrics,
            "executive_summary": executive_summary,
            "summary_source": summary_source,
            "dashboard_data": dashboard_data,
            "source_label": source_label,
            "parse_warnings": parse_warnings or [],
            "report_csv": report_csv,
            "bordereaux_json": rows_to_json(rows),
        },
    )


@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse(request, "index.html", index_context())


@app.get("/how-it-works", response_class=HTMLResponse)
async def how_it_works(request: Request):
    return templates.TemplateResponse(request, "how_it_works.html", {})


@app.post("/extract-baa", response_class=HTMLResponse)
async def extract_baa(request: Request, baa_file: UploadFile = File(None)) -> HTMLResponse:
    baa_form = empty_baa_form()
    try:
        baa_text = await read_uploaded_document(baa_file)
    except Exception as exc:
        return templates.TemplateResponse(
            request,
            "index.html",
            index_context(baa_form=baa_form, baa_extraction_error=f"Could not read that BAA file: {exc}"),
        )
    if not baa_text.strip():
        return templates.TemplateResponse(
            request,
            "index.html",
            index_context(
                baa_form=baa_form,
                baa_extraction_error="No text could be extracted. Please upload a text-based PDF or paste the BAA text manually.",
            ),
        )
    baa_form = build_baa_form_from_extraction(baa_text, baa_file.filename if baa_file else None)
    return templates.TemplateResponse(
        request,
        "index.html",
        index_context(
            baa_form=baa_form,
            baa_extraction_message="BAA rules extracted. Review and edit the fields below before generating the digital twin.",
        ),
    )


@app.post("/generate-bordereaux", response_class=HTMLResponse)
async def generate_bordereaux(
    request: Request,
    baa_name: Optional[str] = Form(None),
    baa_start_date: Optional[str] = Form(None),
    baa_end_date: Optional[str] = Form(None),
    baa_territory: Optional[str] = Form(None),
    baa_class: Optional[str] = Form(None),
    baa_authority_limit: Optional[str] = Form(None),
    baa_endorsements: Optional[str] = Form(None),
    baa_text: Optional[str] = Form(None),
    row_count: int = Form(DEFAULT_SYNTHETIC_ROWS),
) -> HTMLResponse:
    baa_form = form_from_baa_inputs(baa_name, baa_start_date, baa_end_date, baa_territory, baa_class, baa_authority_limit, baa_endorsements, baa_text)
    try:
        baa = build_baa_from_form_values(baa_name, baa_start_date, baa_end_date, baa_territory, baa_class, baa_authority_limit, baa_endorsements, baa_text)
    except Exception:
        return templates.TemplateResponse(request, "index.html", index_context(baa_form=baa_form, bordereaux_errors=["Please review the BAA rule fields before generating a synthetic portfolio."]))
    rows = generate_synthetic_bordereaux(baa, row_count)
    return render_mass_results(request, baa, rows, f"Synthetic portfolio ({len(rows)} policies)")


@app.post("/upload-bordereaux", response_class=HTMLResponse)
async def upload_bordereaux(
    request: Request,
    baa_name: Optional[str] = Form(None),
    baa_start_date: Optional[str] = Form(None),
    baa_end_date: Optional[str] = Form(None),
    baa_territory: Optional[str] = Form(None),
    baa_class: Optional[str] = Form(None),
    baa_authority_limit: Optional[str] = Form(None),
    baa_endorsements: Optional[str] = Form(None),
    baa_text: Optional[str] = Form(None),
    bordereaux_file: UploadFile = File(None),
) -> HTMLResponse:
    baa_form = form_from_baa_inputs(baa_name, baa_start_date, baa_end_date, baa_territory, baa_class, baa_authority_limit, baa_endorsements, baa_text)
    try:
        baa = build_baa_from_form_values(baa_name, baa_start_date, baa_end_date, baa_territory, baa_class, baa_authority_limit, baa_endorsements, baa_text)
    except Exception:
        return templates.TemplateResponse(request, "index.html", index_context(baa_form=baa_form, bordereaux_errors=["Please review the BAA rule fields before uploading a bordereaux."]))
    if not bordereaux_file or not bordereaux_file.filename:
        return templates.TemplateResponse(request, "index.html", index_context(baa_form=baa_form, bordereaux_errors=["Please choose a bordereaux CSV file to upload."]))
    parsed = parse_bordereaux_csv(await bordereaux_file.read())
    if parsed.errors:
        return templates.TemplateResponse(request, "index.html", index_context(baa_form=baa_form, bordereaux_errors=parsed.errors, bordereaux_warnings=parsed.warnings))
    return render_mass_results(request, baa, parsed.rows, f"Uploaded CSV: {bordereaux_file.filename}", parsed.warnings)


@app.post("/validate-bordereaux", response_class=HTMLResponse)
async def validate_existing_bordereaux(
    request: Request,
    baa_name: Optional[str] = Form(None),
    baa_start_date: Optional[str] = Form(None),
    baa_end_date: Optional[str] = Form(None),
    baa_territory: Optional[str] = Form(None),
    baa_class: Optional[str] = Form(None),
    baa_authority_limit: Optional[str] = Form(None),
    baa_endorsements: Optional[str] = Form(None),
    baa_text: Optional[str] = Form(None),
    bordereaux_json: str = Form(""),
) -> HTMLResponse:
    baa = build_baa_from_form_values(baa_name, baa_start_date, baa_end_date, baa_territory, baa_class, baa_authority_limit, baa_endorsements, baa_text)
    rows = rows_from_json(bordereaux_json)
    return render_mass_results(request, baa, rows, "Revalidated portfolio")


@app.post("/download-report")
async def download_report(report_csv: str = Form(...)) -> StreamingResponse:
    filename = f"policycheck_exception_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(io.StringIO(report_csv), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={filename}"})


@app.post("/process", response_class=HTMLResponse)
async def process(
    request: Request,
    baa_name: Optional[str] = Form(None),
    baa_start_date: Optional[str] = Form(None),
    baa_end_date: Optional[str] = Form(None),
    baa_territory: Optional[str] = Form(None),
    baa_class: Optional[str] = Form(None),
    baa_authority_limit: Optional[str] = Form(None),
    baa_endorsements: Optional[str] = Form(None),
    baa_text: Optional[str] = Form(None),
    baa_file: UploadFile = File(None),
    policy1_number: Optional[str] = Form(None),
    policy1_bind_date: Optional[str] = Form(None),
    policy1_territory: Optional[str] = Form(None),
    policy1_class: Optional[str] = Form(None),
    policy1_sum_insured: Optional[str] = Form(None),
    policy1_endorsements: Optional[str] = Form(None),
    policy1_file: UploadFile = File(None),
    policy2_number: Optional[str] = Form(None),
    policy2_bind_date: Optional[str] = Form(None),
    policy2_territory: Optional[str] = Form(None),
    policy2_class: Optional[str] = Form(None),
    policy2_sum_insured: Optional[str] = Form(None),
    policy2_endorsements: Optional[str] = Form(None),
    policy2_file: UploadFile = File(None),
    policy3_number: Optional[str] = Form(None),
    policy3_bind_date: Optional[str] = Form(None),
    policy3_territory: Optional[str] = Form(None),
    policy3_class: Optional[str] = Form(None),
    policy3_sum_insured: Optional[str] = Form(None),
    policy3_endorsements: Optional[str] = Form(None),
    policy3_file: UploadFile = File(None),
) -> HTMLResponse:
    try:
        uploaded_baa_text = await read_uploaded_document(baa_file)
    except Exception:
        uploaded_baa_text = ""
    combined_baa_text = "\n\n".join([part for part in [baa_text, uploaded_baa_text] if part])
    baa = parse_baa_inputs(baa_name, baa_start_date, baa_end_date, baa_territory, baa_class, baa_authority_limit, baa_endorsements, combined_baa_text)
    policies: List[Policy] = []
    p1_text = await read_uploaded_document(policy1_file)
    if any([policy1_number, policy1_bind_date, policy1_territory, policy1_class, policy1_sum_insured, policy1_endorsements, p1_text]):
        policies.append(parse_policy_inputs(policy1_number, policy1_bind_date, policy1_territory, policy1_class, policy1_sum_insured, policy1_endorsements, p1_text))
    p2_text = await read_uploaded_document(policy2_file)
    if any([policy2_number, policy2_bind_date, policy2_territory, policy2_class, policy2_sum_insured, policy2_endorsements, p2_text]):
        policies.append(parse_policy_inputs(policy2_number, policy2_bind_date, policy2_territory, policy2_class, policy2_sum_insured, policy2_endorsements, p2_text))
    p3_text = await read_uploaded_document(policy3_file)
    if any([policy3_number, policy3_bind_date, policy3_territory, policy3_class, policy3_sum_insured, policy3_endorsements, p3_text]):
        policies.append(parse_policy_inputs(policy3_number, policy3_bind_date, policy3_territory, policy3_class, policy3_sum_insured, policy3_endorsements, p3_text))
    bordereau = {p.policy_number: datetime.now() for p in policies}
    results = []
    for policy in policies:
        issues = check_policy_against_baa(policy, baa) + check_bordereau_delays(policy, bordereau)
        results.append({"policy": policy, "issues": issues})
    return templates.TemplateResponse(request, "results.html", {"baa": baa, "results": results})
