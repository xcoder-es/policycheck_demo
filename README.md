# PolicyCheck Demo

PolicyCheck is a lightweight product-grade demo for insurance operational intelligence. It turns a reviewed Binding Authority Agreement into an executable digital twin, then validates individual policies and bordereaux portfolios against the reviewed authority controls.

The demo is intentionally designed for a Render free-tier deployment: FastAPI, Jinja, static CSS, small file uploads, standard-library CSV processing and optional requests-based Hugging Face calls with deterministic fallbacks.

## Product narrative

Insurance operations teams often discover binder and bordereaux mistakes too late: after reporting, reconciliation, audit review or claims friction. PolicyCheck demonstrates a safer workflow:

1. Upload or define a Binding Authority Agreement.
2. Extract candidate rules from the document.
3. Keep a human review step before rules become executable.
4. Validate individual policies or a full bordereaux portfolio.
5. Surface breaches, warnings, exposure and audit-friendly explanations.
6. Download an exception report for operational follow-up.

## Current capabilities

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
- Responsive and accessibility-oriented dark UI

## Business architecture

The business flow is deliberately simple. PolicyCheck does not replace underwriting judgement. It gives operations teams a structured way to catch document and authority exceptions earlier.

```mermaid
flowchart LR
    A[Binding Authority Agreement] --> B[Human-reviewed BAA Digital Twin]
    B --> C[Policy Validation]
    B --> D[Bordereaux Mass Validation]
    C --> E[Policy Exceptions]
    D --> F[Portfolio Exception Intelligence]
    F --> G[Dashboard Metrics]
    F --> H[Audit-ready CSV Report]
    F --> I[Executive Summary]
```

## Operating model

```mermaid
flowchart TD
    U[Operations user] --> W[PolicyCheck Web Demo]
    W --> R[Reviewed BAA Rules]
    R --> V[Deterministic Validation Engine]
    P[Policy / Bordereaux Data] --> V
    V --> M[Metrics]
    V --> X[Exceptions]
    V --> C[CSV Report]
    V --> S[Summary Input]
    S --> AI{HF available?}
    AI -->|Yes| H[AI-assisted Summary]
    AI -->|No| F[Deterministic Fallback Summary]
```

## Solution architecture

The application is a modular monolith. FastAPI and Jinja are inbound adapters. Domain rules are framework-independent. AI and PDF/CSV integrations are outbound adapters behind lightweight ports.

```mermaid
flowchart TB
    Browser[Browser] --> FastAPI[FastAPI + Jinja Web Adapter]
    FastAPI --> UseCases[Application Use Cases]
    UseCases --> Domain[Domain Services and Pydantic Models]
    UseCases --> Ports[Ports / Protocols]
    Ports --> PDF[PDF Adapter: pypdf]
    Ports --> CSV[CSV Adapter: stdlib csv/io]
    Ports --> AI[AI Adapter: Hugging Face via requests]
    Ports --> Fallback[Fallback Adapters]
    Domain --> Results[Validation Results]
    Results --> FastAPI
    FastAPI --> Browser
```

## Hexagonal architecture boundaries

```mermaid
flowchart LR
    subgraph Inbound[Inbound adapter]
        Web[FastAPI routes]
        Forms[Form parsers and view models]
        Templates[Jinja templates]
    end

    subgraph Application[Application layer]
        Extract[Extract BAA Rules]
        Single[Validate Single Policy]
        Synthetic[Generate Synthetic Bordereaux]
        Mass[Validate Bordereaux]
        Report[Generate Exception Report]
        Summary[Generate Portfolio Summary]
    end

    subgraph Domain[Domain layer]
        Models[Pydantic domain models]
        Rules[Deterministic validation services]
    end

    subgraph Ports[Ports]
        PdfPort[PdfTextExtractor]
        AiRulesPort[AiRuleExtractor]
        AiSummaryPort[AiSummaryGenerator]
        CsvPort[BordereauxReader]
        ReportPort[ReportWriter]
    end

    subgraph Outbound[Outbound adapters]
        PyPdf[pypdf text extraction]
        Hf[Hugging Face requests adapter]
        Local[Deterministic fallback adapters]
        Csv[CSV reader/writer]
    end

    Web --> Application
    Forms --> Application
    Application --> Domain
    Application --> Ports
    Ports --> Outbound
    Templates <-- Web
```

## Application flow

```mermaid
sequenceDiagram
    participant User
    participant Web as FastAPI Web Adapter
    participant UseCase as Application Use Case
    participant Domain as Validation Domain
    participant Adapter as CSV/PDF/AI Adapter

    User->>Web: Submit BAA and portfolio data
    Web->>UseCase: Execute workflow with DTO/domain input
    UseCase->>Adapter: Read PDF, CSV or optional summary
    Adapter-->>UseCase: Extracted text, rows or fallback summary
    UseCase->>Domain: Validate records against BAA rules
    Domain-->>UseCase: Validation results and metrics
    UseCase-->>Web: Structured view model
    Web-->>User: Dashboard, exceptions and report download
```

## Domain model overview

```mermaid
classDiagram
    class BAARules {
        agreement_name
        start_date
        end_date
        territories
        classes_of_business
        authority_limit
        required_endorsements
    }

    class PolicyRecord {
        policy_number
        insured_name
        bind_date
        territory
        class_of_business
        sum_insured
        premium
        endorsements
        broker
        status
    }

    class ValidationIssue {
        issue_type
        severity
        message
    }

    class ValidationResult {
        policy_number
        status
        severity
        issue_count
        sum_insured
    }

    class PortfolioValidationSummary {
        total_policies
        compliant_count
        warning_count
        breach_count
        high_severity_count
        total_exposure
        exposure_outside_authority
        most_common_issue
        compliance_percentage
    }

    BAARules --> PolicyRecord : validates
    ValidationResult --> ValidationIssue : contains
    PortfolioValidationSummary --> ValidationResult : summarises
```

## Deterministic validation rules

AI never decides compliance. Compliance is owned by deterministic domain services.

Rules currently checked:

- Bind date must be inside the BAA start and end date.
- Territory must be one of the permitted territories.
- Class of business must be one of the permitted classes.
- Sum insured must not exceed the authority limit.
- Required endorsements must be present.
- Missing or malformed values produce warnings or breaches instead of stack traces.
- Multiple issues per policy are supported.

## AI usage policy

AI is used only for assistance:

- Extracting candidate BAA rules from text for human review.
- Generating a human-readable portfolio summary from deterministic metrics.

AI is not used to decide whether a policy is compliant. If Hugging Face is unavailable, slow, rate-limited or not configured, the app falls back to deterministic local logic.

```mermaid
flowchart TD
    Metrics[Deterministic metrics] --> Prompt[Summary prompt]
    Prompt --> HF{HF_TOKEN configured and API available?}
    HF -->|Yes| AISummary[AI-assisted executive summary]
    HF -->|No| LocalSummary[Deterministic fallback summary]
    AISummary --> UI[Results page]
    LocalSummary --> UI
```

## Repository structure

```text
policycheck_demo/
  app.py                         # FastAPI entrypoint and web adapter compatibility layer
  domain/                        # Pydantic models and deterministic domain services
  application/                   # Use cases and DTO contracts
  ports/                         # Protocol-based outbound interfaces
  adapters/                      # PDF, AI and CSV adapter implementations
  infrastructure/                # Config and lightweight composition root
  templates/                     # Jinja templates
  static/                        # CSS assets

tests/
  domain/
  application/
  adapters/
  web/
```

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn policycheck_demo.app:app --reload
```

Open `http://127.0.0.1:8000`.

## Quality checks

Development tools are intentionally installed outside production requirements.

```bash
pip install pytest ruff
ruff check .
ruff format --check policycheck_demo/domain policycheck_demo/application policycheck_demo/ports policycheck_demo/adapters policycheck_demo/infrastructure tests
pytest
```

## CI

GitHub Actions runs on pull requests and pushes to `main`.

```mermaid
flowchart LR
    PR[Pull request] --> Checkout[Checkout]
    Checkout --> Python[Setup Python 3.14.3]
    Python --> Install[Install runtime + dev tools]
    Install --> Ruff[Ruff lint]
    Ruff --> Format[Ruff format check]
    Format --> Tests[pytest]
```

## Render free-tier constraints

This demo is deliberately small and cheap to run.

- No database
- No authentication
- No queues
- No background workers
- No OCR
- No local ML model loading
- No pandas, torch, transformers, LangChain or LlamaIndex
- Standard-library CSV processing
- Optional network AI calls with fallback
- Small synthetic bordereaux datasets: 25, 50 or 100 rows
- Text-based PDF extraction only

## Deployment

The existing Render deployment remains supported. The app entrypoint is unchanged:

```bash
uvicorn policycheck_demo.app:app --host 0.0.0.0 --port $PORT
```

## Current limitations

- Scanned PDFs are not OCR'd.
- Excel upload is out of scope.
- There is no persistence between requests.
- There are no user accounts, tenant isolation or permissions.
- The demo focuses on product narrative and architecture shape, not full enterprise workflow management.

## Design principle

PolicyCheck is built around one core idea: AI can assist the operator, but deterministic rules and human-reviewed controls own compliance decisions.
