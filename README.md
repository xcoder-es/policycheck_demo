# PolicyCheck Demo

PolicyCheck is a lightweight FastAPI and Jinja proof of concept for insurance operational intelligence.

The demo lets a user define or upload a Binding Authority Agreement, review extracted rules, validate individual policies, generate or upload a bordereaux, run portfolio-level validation, inspect exceptions and download an audit-style exception report.

## What the app does

- Manual BAA rule entry
- Text-based BAA PDF upload
- AI-assisted BAA rule extraction with human review
- Single policy validation
- Synthetic bordereaux generation
- Bordereaux CSV upload with tolerant column mapping
- Mass validation against reviewed BAA controls
- Validation dashboard and exception table
- Downloadable exception report CSV
- Optional AI-assisted executive summary with deterministic fallback

## Local run

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn policycheck_demo.app:app --reload
```

Open `http://127.0.0.1:8000`.

## Tests and quality

Development tools are intentionally not included in production requirements.

```bash
pip install pytest ruff
ruff check .
ruff format --check .
pytest
```

## Architecture overview

The codebase is organised as a pragmatic modular monolith using hexagonal architecture principles.

### Domain layer

`policycheck_demo/domain` contains Pydantic models and deterministic validation services. This layer owns the compliance language: BAA rules, policy records, validation issues, compliance status, severity and portfolio summaries.

### Application layer

`policycheck_demo/application/use_cases` orchestrates domain services and ports. Use cases do not know about FastAPI, Jinja templates, UploadFile, Request or HTML responses.

### Ports

`policycheck_demo/ports` defines small Protocol interfaces for outbound dependencies such as PDF text extraction, AI rule extraction, AI summaries, bordereaux reading and report writing.

### Adapters

`policycheck_demo/adapters` implements the current external behaviours using lightweight technology:

- `pypdf` for text-based PDF extraction
- standard library `csv` and `io` for bordereaux and exception reports
- requests-based Hugging Face integration for optional summaries
- deterministic fallback extractors and summaries

### Infrastructure/container

`policycheck_demo/infrastructure/container.py` is the composition root. It wires concrete adapters to application use cases without a third-party dependency injection framework.

### Web adapter

FastAPI and Jinja remain the inbound web adapter. Route handlers parse form/upload data, call use cases or compatibility services, and pass view models into templates.

## Deterministic validation

AI assists extraction and summarisation only. It does not decide compliance outcomes.

The deterministic validation rules are:

- bind date must be within the BAA period
- territory must be in the allowed territories
- class of business must be in the allowed classes
- sum insured must not exceed the authority limit
- required endorsements must be present
- malformed or missing values produce warnings or breaches instead of uncaught exceptions

## Render free-tier constraints

This POC is designed to stay deployable on Render free tier.

- No database
- No authentication
- No queues
- No background workers
- No OCR
- No local model loading
- No pandas, torch, transformers, LangChain or LlamaIndex
- CSV processing uses the Python standard library
- Hugging Face calls are optional and fail-safe
- Synthetic bordereaux generation defaults to 50 rows and is capped at small demo sizes

## Current limitations

- Scanned PDFs are not OCR'd
- Excel upload is out of scope
- No persistence between requests
- No user accounts or permissions
- No enterprise workflow management
- The demo is intentionally focused on a lightweight product narrative rather than a full production platform
