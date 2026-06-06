"""
FastAPI application for the PolicyCheck digital twin POC.

This module defines a small web application that allows users to
describe a Binding Authority Agreement (BAA) and up to three
policies, either by providing structured form fields or by
uploading plain‑text documents.  It then performs AI‑assisted
extraction of missing fields, validates the policies against the
agreement, and renders the results using Jinja2 templates.

The application relies on FastAPI and Uvicorn rather than Flask, as
FastAPI is pre‑installed in the execution environment.  To run the
app locally, execute:

    uvicorn policycheck_demo.app:app --reload

The ``--reload`` flag reloads the server on code changes.  Navigate
to http://127.0.0.1:8000/ in your browser.
"""

import io
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import FastAPI, Form, UploadFile, File, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .models import BAA, Policy
from .ai_utils import extract_fields_from_baa, extract_policy_fields
from .checker import check_policy_against_baa, check_bordereau_delays


app = FastAPI()

# Mount static files (CSS)
app.mount(
    "/static", StaticFiles(directory=str(__import__('pathlib').Path(__file__).parent / "static")), name="static"
)

templates = Jinja2Templates(directory=str(__import__('pathlib').Path(__file__).parent / "templates"))


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
    """Assemble a BAA instance from form inputs.

    If any key fields are missing but textual content is provided, the
    function invokes the AI extractor to attempt to fill them in.
    """
    text = baa_text or ""
    name = name or "Uploaded BAA"
    # AI extraction
    if text and (not start_date_str or not end_date_str or not territory_str or not class_str or not authority_limit_str):
        extracted = extract_fields_from_baa(text)
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
    # Parse fields
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
    # AI extraction if needed
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
    # Parse
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
    return templates.TemplateResponse("index.html", {"request": request})


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
    # Create BAA
    baa = parse_baa_inputs(
        baa_name,
        baa_start_date,
        baa_end_date,
        baa_territory,
        baa_class,
        baa_authority_limit,
        baa_endorsements,
        baa_text,
    )
    # Create policies list
    policies: List[Policy] = []
    # helper to read uploaded file text
    async def read_file(file: UploadFile) -> str:
        if file and file.filename:
            content_bytes = await file.read()
            try:
                return content_bytes.decode("utf-8", errors="ignore")
            except Exception:
                return ""
        return ""
    # Policy 1
    p1_text = await read_file(policy1_file)
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
    # Policy 2
    p2_text = await read_file(policy2_file)
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
    # Policy 3
    p3_text = await read_file(policy3_file)
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
    # Simulate bordereau as reported today
    bordereau = {p.policy_number: datetime.now() for p in policies}
    # Check policies
    results = []
    for p in policies:
        issues = check_policy_against_baa(p, baa) + check_bordereau_delays(p, bordereau)
        results.append({"policy": p, "issues": issues})
    return templates.TemplateResponse(
        "results.html",
        {
            "request": request,
            "baa": baa,
            "results": results,
        },
    )