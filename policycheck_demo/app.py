"""
FastAPI application for the PolicyCheck digital twin POC.

This module defines a small web application that allows users to
describe a Binding Authority Agreement (BAA) and up to three policies,
either by providing structured form fields or by uploading documents.
It then performs AI-assisted extraction of missing fields, validates
the policies against the agreement, and renders the results using
Jinja2 templates.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .ai_utils import extract_fields_from_baa, extract_policy_fields
from .checker import check_bordereau_delays, check_policy_against_baa
from .models import BAA, Policy
from .pdf_utils import extract_text_from_pdf_bytes


app = FastAPI()

# Mount static files (CSS)
app.mount(
    "/static",
    StaticFiles(directory=str(Path(__file__).parent / "static")),
    name="static",
)

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
    """Return the template context expected by the BAA form."""
    return {key: "" for key in BAA_FORM_KEYS}


def format_date_value(value: object) -> str:
    """Format extracted dates for HTML date inputs."""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    return ""


def build_baa_form_from_extraction(text: str, filename: Optional[str] = None) -> Dict[str, str]:
    """Build editable BAA form values from extracted PDF/plain-text content."""
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
    """Read a lightweight text-based upload.

    Supports text files and text-based PDFs. It intentionally does not perform
    OCR, image analysis, or model-based parsing so the demo remains stable on
    Render.
    """
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
    name: Optional[str],
    start_date_str: Optional[str],
    end_date_str: Optional[str],
    territory_str: Optional[str],
    class_str: Optional[str],
    authority_limit_str: Optional[str],
    endorsements_str: Optional[str],
    baa_text: Optional[str],
) -> BAA:
    """Assemble a BAA instance from reviewed form inputs.

    If any key fields are still missing but textual content is provided, the
    function invokes the lightweight extractor to attempt to fill them in.
    """
    text = baa_text or ""
    name = name or "Uploaded BAA"

    if text and (
        not name
        or not start_date_str
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
    territory = [t.strip() for t in territory_str.split(",") if t.strip()] if territory_str else []
    class_of_business = [c.strip() for c in class_str.split(",") if c.strip()] if class_str else []
    try:
        authority_limit = float(authority_limit_str.replace(",", "")) if authority_limit_str else 0.0
    except Exception:
        authority_limit = 0.0
    endorsements = [e.strip() for e in endorsements_str.split(",") if e.strip()] if endorsements_str else []

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
    policy_number: Optional[str],
    bind_date_str: Optional[str],
    territory: Optional[str],
    class_of_business: Optional[str],
    sum_insured_str: Optional[str],
    endorsements_str: Optional[str],
    policy_text: Optional[str],
) -> Policy:
    """Assemble a Policy instance from form inputs and optional text."""
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
    territory = territory or ""
    class_of_business = class_of_business or ""
    try:
        sum_insured = float(sum_insured_str.replace(",", "")) if sum_insured_str else 0.0
    except Exception:
        sum_insured = 0.0
    endorsements = [e.strip() for e in endorsements_str.split(",") if e.strip()] if endorsements_str else []

    return Policy(
        policy_number=policy_number,
        bind_date=bind_date,
        territory=territory,
        class_of_business=class_of_business,
        sum_insured=sum_insured,
        endorsements=endorsements,
        text=policy_text,
    )


@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    """Render the homepage."""
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "baa_form": empty_baa_form(),
            "baa_extraction_message": None,
            "baa_extraction_error": None,
        },
    )


@app.post("/extract-baa", response_class=HTMLResponse)
async def extract_baa(
    request: Request,
    baa_file: UploadFile = File(None),
) -> HTMLResponse:
    """Extract BAA rules from an uploaded text-based PDF before validation."""
    baa_form = empty_baa_form()

    try:
        baa_text = await read_uploaded_document(baa_file)
    except Exception as exc:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "baa_form": baa_form,
                "baa_extraction_message": None,
                "baa_extraction_error": f"Could not read that BAA file: {exc}",
            },
        )

    if not baa_text.strip():
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "baa_form": baa_form,
                "baa_extraction_message": None,
                "baa_extraction_error": "No text could be extracted. Please upload a text-based PDF or paste the BAA text manually.",
            },
        )

    baa_form = build_baa_form_from_extraction(baa_text, baa_file.filename if baa_file else None)

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "baa_form": baa_form,
            "baa_extraction_message": "BAA rules extracted. Review and edit the fields below before generating the digital twin.",
            "baa_extraction_error": None,
        },
    )


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
    # Policy 1
    policy1_number: Optional[str] = Form(None),
    policy1_bind_date: Optional[str] = Form(None),
    policy1_territory: Optional[str] = Form(None),
    policy1_class: Optional[str] = Form(None),
    policy1_sum_insured: Optional[str] = Form(None),
    policy1_endorsements: Optional[str] = Form(None),
    policy1_file: UploadFile = File(None),
    # Policy 2
    policy2_number: Optional[str] = Form(None),
    policy2_bind_date: Optional[str] = Form(None),
    policy2_territory: Optional[str] = Form(None),
    policy2_class: Optional[str] = Form(None),
    policy2_sum_insured: Optional[str] = Form(None),
    policy2_endorsements: Optional[str] = Form(None),
    policy2_file: UploadFile = File(None),
    # Policy 3
    policy3_number: Optional[str] = Form(None),
    policy3_bind_date: Optional[str] = Form(None),
    policy3_territory: Optional[str] = Form(None),
    policy3_class: Optional[str] = Form(None),
    policy3_sum_insured: Optional[str] = Form(None),
    policy3_endorsements: Optional[str] = Form(None),
    policy3_file: UploadFile = File(None),
) -> HTMLResponse:
    uploaded_baa_text = ""
    try:
        uploaded_baa_text = await read_uploaded_document(baa_file)
    except Exception:
        uploaded_baa_text = ""

    combined_baa_text = "\n\n".join([part for part in [baa_text, uploaded_baa_text] if part])

    baa = parse_baa_inputs(
        baa_name,
        baa_start_date,
        baa_end_date,
        baa_territory,
        baa_class,
        baa_authority_limit,
        baa_endorsements,
        combined_baa_text,
    )

    policies: List[Policy] = []

    p1_text = await read_uploaded_document(policy1_file)
    if any([policy1_number, policy1_bind_date, policy1_territory, policy1_class, policy1_sum_insured, policy1_endorsements, p1_text]):
        policies.append(
            parse_policy_inputs(
                policy1_number,
                policy1_bind_date,
                policy1_territory,
                policy1_class,
                policy1_sum_insured,
                policy1_endorsements,
                p1_text,
            )
        )

    p2_text = await read_uploaded_document(policy2_file)
    if any([policy2_number, policy2_bind_date, policy2_territory, policy2_class, policy2_sum_insured, policy2_endorsements, p2_text]):
        policies.append(
            parse_policy_inputs(
                policy2_number,
                policy2_bind_date,
                policy2_territory,
                policy2_class,
                policy2_sum_insured,
                policy2_endorsements,
                p2_text,
            )
        )

    p3_text = await read_uploaded_document(policy3_file)
    if any([policy3_number, policy3_bind_date, policy3_territory, policy3_class, policy3_sum_insured, policy3_endorsements, p3_text]):
        policies.append(
            parse_policy_inputs(
                policy3_number,
                policy3_bind_date,
                policy3_territory,
                policy3_class,
                policy3_sum_insured,
                policy3_endorsements,
                p3_text,
            )
        )

    bordereau = {p.policy_number: datetime.now() for p in policies}

    results = []
    for policy in policies:
        issues = check_policy_against_baa(policy, baa) + check_bordereau_delays(policy, bordereau)
        results.append({"policy": policy, "issues": issues})

    return templates.TemplateResponse(
        request,
        "results.html",
        {
            "baa": baa,
            "results": results,
        },
    )
