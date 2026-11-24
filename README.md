# ConsentDrift

> **Evidence-backed personal privacy purpose drift detection.**  
> Compare what you *originally* consented to against *later* privacy disclosures (emails, policy snippets, app notifications) and flag potential purpose drift with verbatim verified quotes.

---

## Table of Contents
- [Overview](#overview)
- [Architecture & Pipeline](#architecture--pipeline)
- [Analysis Engine & Anti-Hallucination](#analysis-engine--anti-hallucination)
- [Modes: Rules-Only vs Hybrid](#modes-rules-only-vs-hybrid)
- [Quick Start](#quick-start)
  - [Prerequisites](#prerequisites)
  - [1. Backend Setup](#1-backend-setup)
  - [2. Frontend Setup](#2-frontend-setup)
  - [3. Loading Seed Scenarios](#3-loading-seed-scenarios)
  - [4. Chrome Extension Installation](#4-chrome-extension-installation)
- [Running Unit Tests](#running-unit-tests)
- [Running the Evaluation Benchmark](#running-the-evaluation-benchmark)
- [Project Structure](#project-structure)
- [Clarification Request Email Generator](#clarification-request-email-generator)
- [Limitations & Ethical Disclaimer](#limitations--ethical-disclaimer)

---

## Overview

When people sign up for online services (scholarships, job applications, e-commerce, edtech), they agree to specific terms (e.g., *"to evaluate your scholarship application"*). Months later, they receive emails or updated privacy disclosures stating that their data will now be shared with advertising partners, data brokers, or commercial recruiters.

**ConsentDrift** is a narrow vertical-slice privacy tool that lets individuals:
1. Store a **Baseline Consent** record (the original purpose and data categories).
2. Submit new **Evidence** (emails, policy snippets, in-app notifications).
3. Run a deterministic 5-stage **Analysis Pipeline** that flags potential purpose drift (`LOW`, `MEDIUM`, `HIGH`, `INSUFFICIENT_EVIDENCE`).
4. Inspect verbatim, highlighted quotes from the evidence that support the findings.
5. Generate a polite, non-accusatory **Clarification Request** email to send to the organization's privacy officer.

---

## Architecture & Pipeline

ConsentDrift uses a staged, multi-tier analysis pipeline where deterministic rules and strict substring validation always constrain any optional LLM extraction:

```
[Baseline Consent Record]  +  [New Evidence Text]
         │                              │
         ▼                              ▼
  ┌──────────────────────────────────────────────┐
  │  Stage 1: Deterministic Signal Detector      │  (rules.py)
  │  Regex matching for Marketing, Brokers,      │
  │  Sharing, Profiling, Analytics, Benign, etc. │
  └──────────────────────┬───────────────────────┘
                         │
         ┌───────────────┴──────────────┐
         │ Is LLM_API_KEY configured?   │
         │                              │
        YES                             NO (or on error)
         │                              │
         ▼                              ▼
  ┌───────────────────────────┐         │
  │ Stage 2: LLM Extraction   │         │
  │ JSON structured purpose   │         │
  │ comparison (temp = 0)     │         │
  └──────────────┬────────────┘         │
                 │                      │
                 ▼                      │
  ┌─────────────────────────────────────┴────────┐
  │  Stage 3: Verbatim Quote Validator           │  (validator.py)
  │  • Normalises case & whitespace              │
  │  • Verifies each quote is an exact substring │
  │  • Drops hallucinated quotes & logs warning  │
  │  • Falls back to matched sentence spans      │
  └──────────────────────┬───────────────────────┘
                         │
                         ▼
  ┌──────────────────────────────────────────────┐
  │  Stage 4: Deterministic Risk Classification  │  (risk.py)
  │  • INSUFFICIENT: <15 words or no signals     │
  │  • HIGH: Commercial/ad sharing not in base   │
  │    AND validated verbatim quote exists       │
  │  • Downgrade rule: HIGH without quote -> MED │
  │  • MEDIUM: Analytics, retention, vague terms │
  │  • LOW: Benign status or covered by baseline │
  └──────────────────────┬───────────────────────┘
                         │
                         ▼
  ┌──────────────────────────────────────────────┐
  │  Stage 5: Cautious Explanation & Labels      │  (risk.py)
  │  • Plain-language explanation ("potential")  │
  │  • Directly Stated vs AI Interpretation      │
  │  • Recommended next actions                  │
  └──────────────────────────────────────────────┘
```

---

## Analysis Engine & Anti-Hallucination

### 1. Deterministic Signal Detector (`rules.py`)
Case-insensitive regex patterns grouped into clear categories:
- **`HIGH_SIGNALS`**:
  - `SALE_OR_BROKER`: sell, sale of personal data, data broker, monetize data.
  - `THIRD_PARTY_SHARING`: sharing/disclosing data to advertising partners, affiliate networks, sponsors, commercial third parties.
  - `MARKETING`: promotional campaigns, newsletters, special partner deals, advertising communications.
  - `PROFILING`: behavioural profiling, personalised ads, targeted advertising, tracking interest profiles.
- **`MEDIUM_SIGNALS`**:
  - `VAGUE_PARTNER_SHARING`: ambiguous sharing with "trusted partners" or "selected partners" without clear advertising terms.
  - `ANALYTICS_RESEARCH`: product analytics, internal research, platform improvement.
  - `RETENTION_CHANGE`: indefinite retention, extended data holding periods.
  - `CONSENT_WITHDRAWAL_LIMIT`: opt-out restrictions, deemed or implied consent.
- **`BENIGN_STATUS`**: Application status updates, interview schedules, OTP tokens, password resets, verification receipts.
- **Data Categories**: Email, phone, physical address, location, resume/CV, financial information, ID numbers, academic records.

### 2. Anti-Hallucination Quote Validator (`validator.py`)
LLMs frequently hallucinate or paraphrase quotes. ConsentDrift guarantees quote fidelity:
1. Normalises whitespace (`\s+` -> `' '`) and case across both the candidate quote and evidence text.
2. Performs exact substring searches on the evidence text.
3. If an LLM quote is not found in the original evidence, it is immediately discarded and a warning is recorded (e.g., *"1 quote from LLM dropped: not found in evidence text"*).
4. Computes exact character start/end offsets (`[start, end]`) for UI highlighting.
5. In rules-only mode (or when no LLM quotes are valid), the validator extracts the full sentence containing the matched rule regex as the certified quote.

### 3. Risk Engine (`risk.py`)
- **`INSUFFICIENT_EVIDENCE`**: Evidence under 15 words, or no purpose-related signals and zero validated quotes.
- **`HIGH`**: A high-risk signal (`SALE_OR_BROKER`, `THIRD_PARTY_SHARING`, `MARKETING`, `PROFILING`) is present, is **not covered** by the original consent, and is supported by at least one validated verbatim quote.
- **`MEDIUM`**: Additional or vague purposes (`ANALYTICS_RESEARCH`, `VAGUE_PARTNER_SHARING`, `RETENTION_CHANGE`), OR a high signal is detected but lacks a verified quote, OR third-party sharing is marked "unclear".
- **`LOW`**: Only benign status signals exist, or the evidence is entirely consistent with the baseline consent.
- **Downgrade Rule**: If an LLM suggests HIGH findings but zero quotes survive validation, the risk is automatically downgraded to `MEDIUM` with an explicit warning.

---

## Modes: Rules-Only vs Hybrid

ConsentDrift runs out of the box in **rules-only** mode with **zero external API keys or network dependencies**.

| Feature | Rules-Only Mode (Default) | Hybrid Mode (LLM Enabled) |
|---|---|---|
| **API Key Required** | None (`LLM_API_KEY=""`) | OpenAI-compatible endpoint |
| **Signal Detection** | Deterministic regex | Deterministic regex |
| **Quote Extraction** | Sentence expansion of matched regex | Verbatim LLM quote extraction + validator |
| **Risk Classification** | Deterministic rules | Deterministic rules (constrained by validator) |
| **Fallback** | Always available | Auto-downgrades to rules-only if LLM fails |

### Enabling Hybrid Mode
In `backend/.env`:
```env
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-your-openai-api-key-here
LLM_MODEL=gpt-4o-mini
```
If `LLM_API_KEY` is left blank, or if an API call times out or fails JSON parsing after retry, the pipeline automatically proceeds in rules-only mode. Every analysis response displays its active mode: `"rules-only"` or `"hybrid"`.

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm
- Google Chrome (optional, for Chrome Extension)

---

### 1. Backend Setup

```bash
# Navigate to backend directory
cd backend

# Option A: Using the included Python 3.12 runtime
.\py312\python.exe -m uvicorn app.main:app --reload --port 8000

# Option B: Using standard Python venv
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
Backend runs at: **http://localhost:8000**  
API Documentation (Swagger): **http://localhost:8000/docs**

---

### 2. Frontend Setup

```bash
# Open a new terminal and navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```
Frontend runs at: **http://localhost:5173**

---

### 3. Loading Seed Scenarios

You can populate the database with realistic demo scenarios (Scholarship ad sharing, Job Portal interview notification, EdTech analytics disclosure) in two ways:

**Via Web UI:**  
Click the **"Load Demo"** button in the navigation bar or dashboard.

**Via CLI / API:**
```bash
# Direct python execution:
cd backend
.\py312\python.exe app/seed.py

# Or via curl:
curl -X POST http://localhost:8000/api/seed
```

---

### 4. Chrome Extension Installation

1. Open Google Chrome and navigate to `chrome://extensions/`.
2. Enable **"Developer mode"** via the toggle in the top-right corner.
3. Click **"Load unpacked"**.
4. Select the `extension/` folder from this repository:
   `c:\Users\pavan\Desktop\consentdrift\extension`
5. The ConsentDrift icon will appear in your Chrome toolbar.

**Extension Capabilities:**
- **Context Menu: Evidence Extraction**: Highlight any paragraph on a webpage, right-click, and select *"Send selection to ConsentDrift as evidence"*. The popup will prefill the text ready for analysis.
- **Context Menu: Baseline Capture**: Right-click anywhere on a privacy policy page and select *"Save this page as consent baseline"*. The text is extracted and stored directly in your ConsentDrift database.
- **Popup UI**: Submit evidence, select existing baseline consents, review risk badges and explanations inline, and open the full analysis directly in the web dashboard.

---

## Running Unit Tests

ConsentDrift includes a full pytest test suite covering quote validation, risk logic, regex signal detection, and pipeline orchestration.

```bash
cd backend
.\py312\python.exe -m pytest tests -v
```

**Expected output:**
```
tests/test_pipeline.py::test_pipeline_rules_only_high PASSED
tests/test_pipeline.py::test_pipeline_rules_only_low PASSED
tests/test_pipeline.py::test_pipeline_insufficient_evidence PASSED
tests/test_risk.py::test_insufficient_evidence_short_text PASSED
tests/test_risk.py::test_high_risk_marketing_not_covered PASSED
tests/test_risk.py::test_high_risk_covered_by_baseline PASSED
tests/test_risk.py::test_downgrade_rule_high_without_quotes PASSED
tests/test_risk.py::test_medium_risk_analytics PASSED
tests/test_risk.py::test_low_risk_benign_status PASSED
tests/test_rules.py::test_marketing_signals PASSED
tests/test_rules.py::test_third_party_sharing_signals PASSED
tests/test_rules.py::test_benign_status_signals PASSED
tests/test_rules.py::test_data_category_detection PASSED
tests/test_validator.py::test_validate_exact_quote PASSED
tests/test_validator.py::test_drop_hallucinated_quote PASSED
tests/test_validator.py::test_quote_spans_detection PASSED
tests/test_validator.py::test_rules_fallback_quotes PASSED

============================== 17 passed in 3.85s ==============================
```

---

## Running the Evaluation Benchmark

ConsentDrift includes an evaluation dataset with 40 diverse scenarios across scholarship portals, job platforms, edtech services, banking apps, and e-commerce stores:
- **10 LOW** (benign status updates, interview schedules, covered uses)
- **10 MEDIUM** (analytics, vague trusted partners, retention policy changes)
- **12 HIGH** (advertising partner sharing, data broker monetization, commercial marketing)
- **8 INSUFFICIENT_EVIDENCE** (receipts, short snippets under 15 words)

### Running Evaluation
```bash
# Run the evaluation script
.\backend\py312\python.exe eval/run_eval.py
```

### Benchmark Results (Rules-Only Mode)

```
Overall Accuracy: 100.0% (40/40)
False HIGH Alarms: 0

Confusion Matrix:
Predicted ->             LOW     MEDIUM       HIGH  INSUFFICIENT
Actual:
LOW                       10          0          0             0
MEDIUM                     0         10          0             0
HIGH                       0          0         12             0
INSUFFICIENT               0          0          0             8

Per-Class Performance:
Class             Precision    Recall    F1-Score    Support
------------------------------------------------------------
LOW                  100.0%    100.0%      100.0%         10
MEDIUM               100.0%    100.0%      100.0%         10
HIGH                 100.0%    100.0%      100.0%         12
INSUFFICIENT         100.0%    100.0%      100.0%          8
```

Results are saved to `eval/results.md` and `eval/results.json`, and can be inspected visually at `http://localhost:5173/evaluation`.

---

## Project Structure

```
consentdrift/
├── README.md                     # Documentation and quick start
├── backend/
│   ├── .env.example              # Environment variables template
│   ├── requirements.txt          # Python dependencies
│   ├── py312/                    # Local Python 3.12 embeddable runtime
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py               # FastAPI entrypoint, CORS configuration
│   │   ├── config.py             # Environment configuration
│   │   ├── db.py                 # SQLite engine and session factory
│   │   ├── models.py             # SQLAlchemy models (ConsentRecord, Evidence, Analysis)
│   │   ├── schemas.py            # Pydantic v2 validation models
│   │   ├── seed.py               # Demo scenario seeder
│   │   ├── engine/
│   │   │   ├── rules.py          # Stage 1: Deterministic regex signal detector
│   │   │   ├── llm.py            # Stage 2: OpenAI-compatible structured extractor
│   │   │   ├── validator.py      # Stage 3: Verbatim quote anti-hallucination validator
│   │   │   ├── risk.py           # Stage 4 & 5: Deterministic risk engine & explanations
│   │   │   ├── pipeline.py       # Orchestrator connecting stages 1 to 5
│   │   │   └── clarification.py  # Plain-text clarification request generator
│   │   └── routers/
│   │       ├── consents.py       # Consent records CRUD & JSON export
│   │       ├── evidence.py       # Evidence submission & analysis trigger
│   │       ├── analyses.py       # Analysis retrieval & clarification draft API
│   │       └── eval_api.py       # Evaluation benchmark results endpoint
│   └── tests/
│       ├── test_rules.py         # Signal detection tests
│       ├── test_validator.py     # Substring validation & span tests
│       ├── test_risk.py          # Risk rules and downgrade tests
│       └── test_pipeline.py      # End-to-end pipeline execution tests
├── frontend/                     # React 18 + TypeScript + Vite + Tailwind CSS
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── src/
│       ├── api.ts                # Typed API client
│       ├── types.ts              # TypeScript schemas
│       ├── components/           # Navbar, Footer, RiskBadge
│       └── pages/
│           ├── Dashboard.tsx     # Consents overview, metrics, demo loader
│           ├── NewConsent.tsx    # Baseline creation form
│           ├── ConsentDetail.tsx # Baseline inspection, evidence upload, history
│           ├── AnalysisDetail.tsx# 2-column view with highlighted quotes & clarification modal
│           └── Evaluation.tsx    # Confusion matrix & benchmark metrics view
├── extension/                    # Chrome Extension (Manifest V3)
│   ├── manifest.json
│   ├── background.js             # Service worker handling context menus & page capture
│   ├── popup.html                # Extension popup interface
│   ├── popup.js                  # Frontend bridge & evidence submitter
│   ├── popup.css                 # Clean popup styling
│   └── icons/                    # 16px, 48px, 128px PNG icons
└── eval/
    ├── dataset.json              # 40 labeled benchmark samples
    ├── run_eval.py               # Evaluation benchmark execution script
    ├── results.md                # Markdown evaluation report
    └── results.json              # Structured benchmark results served to UI
```

---

## Clarification Request Email Generator

When a purpose drift risk is identified, ConsentDrift allows users to generate an editable, polite clarification request directly from the analysis page. 

The template contains five specific inquiries:
1. For what specific purpose is the additional use mentioned?
2. Which of my personal data categories are involved?
3. Is my information shared with third parties? If so, which categories of recipients?
4. On what basis is this additional use carried out?
5. What choices do I have to opt out or withdraw consent?

Users can copy the text to their clipboard or download it as a `.txt` file ready to send to the data controller.

---

## Limitations & Ethical Disclaimer

> [!IMPORTANT]
> **Mandatory Disclaimer:**  
> Findings produced by ConsentDrift represent **potential discrepancies** between submitted texts. They are **not proof of misuse, a data breach, or a legal violation**.

ConsentDrift is intentionally designed with the following inherent limitations:

1. **Discrepancy vs. Legal Violation**:  
   Only a competent court, Data Protection Authority (DPA), or supervisory regulator can determine whether a data protection law (such as GDPR, CCPA, or DPDP) has been violated. Legitimate interests, statutory requirements, or separate consent channels may legally authorize specific data processing activities.
2. **Ambiguous and Broad Language**:  
   Commercial privacy policies frequently use vague terminology such as *"to improve our services"* or *"with selected trusted partners"*. These phrases may refer to routine functional cloud hosting, or alternatively to third-party ad retargeting. ConsentDrift conservatively classifies ambiguous terminology as `MEDIUM` risk to encourage human verification without sounding false alarms.
3. **No Visibility into Actual Backend Data Flows**:  
   ConsentDrift solely analyzes disclosed text. It does not inspect network packets, inspect database schemas, or audit backend microservices. An organization might state compliant terms while mishandling data internally, or conversely mention broad terms in boilerplate text that are never actively utilized.
4. **Not Legal Advice**:  
   ConsentDrift is an educational inquiry tool designed to empower individuals to ask informed questions about their personal data. It does not constitute legal counsel or formal legal opinions.
