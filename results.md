# ConsentDrift Evaluation & Benchmark Report

**Generated at:** 2026-11-24 14:17:46 UTC
**Benchmark Dataset:** 40 curated multi-domain scenarios (10 LOW, 10 MEDIUM, 12 HIGH, 8 INSUFFICIENT_EVIDENCE)

---

## Summary Metrics

| Evaluation Mode | Total Samples | Accuracy | False HIGH Alarms |
| :--- | :---: | :---: | :---: |
| **Rules-Only Mode** | 40 | **100.0%** | **0** |
| **Hybrid (LLM + Rules)** | — | *Skipped (No LLM key configured)* | — |

> [!IMPORTANT]
> False HIGH alarms (predicting HIGH when expected is not HIGH) are the most critical failure mode in privacy purpose drift auditing. Minimizing false alarms protects users against alert fatigue and unnecessary dispute escalations.


## Rules-Only Mode: 4×4 Confusion Matrix

Rows represent Expected Ground Truth; Columns represent ConsentDrift Pipeline Predictions.

| Expected \ Predicted | LOW | MEDIUM | HIGH | INSUFFICIENT_EVIDENCE |
| :--- | :---: | :---: | :---: | :---: |
| **LOW** | 10 | 0 | 0 | 0 |
| **MEDIUM** | 0 | 10 | 0 | 0 |
| **HIGH** | 0 | 0 | 12 | 0 |
| **INSUFFICIENT_EVIDENCE** | 0 | 0 | 0 | 8 |

## Rules-Only Mode: Per-Class Performance

| Class | Support | Precision | Recall | F1-Score |
| :--- | :---: | :---: | :---: | :---: |
| **LOW** | 10 | 100.0% | 100.0% | 100.0% |
| **MEDIUM** | 10 | 100.0% | 100.0% | 100.0% |
| **HIGH** | 12 | 100.0% | 100.0% | 100.0% |
| **INSUFFICIENT_EVIDENCE** | 8 | 100.0% | 100.0% | 100.0% |

## Sample-by-Sample Analysis Breakdown

| ID | Domain | Expected | Predicted | Status | Detected Signals |
| :-: | :--- | :---: | :---: | :---: | :--- |
| 1 | scholarships | LOW | LOW | PASS | BENIGN_STATUS, BENIGN_STATUS, BENIGN_STATUS, BENIGN_STATUS, BENIGN_STATUS, BENIGN_STATUS |
| 2 | job_portals | LOW | LOW | PASS | BENIGN_STATUS |
| 3 | job_portals | LOW | LOW | PASS | BENIGN_STATUS, BENIGN_STATUS, BENIGN_STATUS, BENIGN_STATUS |
| 4 | banking | LOW | LOW | PASS | BENIGN_STATUS, BENIGN_STATUS |
| 5 | e_commerce | LOW | LOW | PASS | BENIGN_STATUS |
| 6 | government | LOW | LOW | PASS | BENIGN_STATUS, BENIGN_STATUS, BENIGN_STATUS |
| 7 | edtech | LOW | LOW | PASS | BENIGN_STATUS, BENIGN_STATUS |
| 8 | e_commerce | LOW | LOW | PASS | MARKETING, MARKETING |
| 9 | banking | LOW | LOW | PASS | BENIGN_STATUS |
| 10 | edtech | LOW | LOW | PASS | BENIGN_STATUS |
| 11 | edtech | MEDIUM | MEDIUM | PASS | VAGUE_PARTNER_SHARING, VAGUE_PARTNER_SHARING, ANALYTICS_RESEARCH, ANALYTICS_RESEARCH |
| 12 | job_portals | MEDIUM | MEDIUM | PASS | VAGUE_PARTNER_SHARING, VAGUE_PARTNER_SHARING, ANALYTICS_RESEARCH, ANALYTICS_RESEARCH |
| 13 | e_commerce | MEDIUM | MEDIUM | PASS | RETENTION_CHANGE, RETENTION_CHANGE |
| 14 | scholarships | MEDIUM | MEDIUM | PASS | MARKETING, MARKETING, OPT_IN_OPTIONAL, OPT_IN_OPTIONAL |
| 15 | banking | MEDIUM | MEDIUM | PASS | ANALYTICS_RESEARCH, ANALYTICS_RESEARCH |
| 16 | government | MEDIUM | MEDIUM | PASS | VAGUE_PARTNER_SHARING, VAGUE_PARTNER_SHARING, ANALYTICS_RESEARCH, ANALYTICS_RESEARCH |
| 17 | job_portals | MEDIUM | MEDIUM | PASS | VAGUE_PARTNER_SHARING, VAGUE_PARTNER_SHARING |
| 18 | e_commerce | MEDIUM | MEDIUM | PASS | MARKETING, MARKETING, OPT_IN_OPTIONAL, OPT_IN_OPTIONAL |
| 19 | edtech | MEDIUM | MEDIUM | PASS | ANALYTICS_RESEARCH, ANALYTICS_RESEARCH, ANALYTICS_RESEARCH |
| 20 | banking | MEDIUM | MEDIUM | PASS | RETENTION_CHANGE, RETENTION_CHANGE |
| 21 | scholarships | HIGH | HIGH | PASS | THIRD_PARTY_SHARING, THIRD_PARTY_SHARING, MARKETING, MARKETING, MARKETING |
| 22 | job_portals | HIGH | HIGH | PASS | MARKETING |
| 23 | e_commerce | HIGH | HIGH | PASS | SALE_OR_BROKER, SALE_OR_BROKER, SALE_OR_BROKER, MARKETING |
| 24 | edtech | HIGH | HIGH | PASS | MARKETING, PROFILING, PROFILING, PROFILING |
| 25 | banking | HIGH | HIGH | PASS | THIRD_PARTY_SHARING, MARKETING, MARKETING |
| 26 | government | HIGH | HIGH | PASS | SALE_OR_BROKER, THIRD_PARTY_SHARING, MARKETING, MARKETING |
| 27 | job_portals | HIGH | HIGH | PASS | THIRD_PARTY_SHARING, THIRD_PARTY_SHARING, VAGUE_PARTNER_SHARING, MARKETING, MARKETING |
| 28 | e_commerce | HIGH | HIGH | PASS | PROFILING, PROFILING |
| 29 | scholarships | HIGH | HIGH | PASS | THIRD_PARTY_SHARING, THIRD_PARTY_SHARING, MARKETING, MARKETING, MARKETING |
| 30 | edtech | HIGH | HIGH | PASS | SALE_OR_BROKER, THIRD_PARTY_SHARING, MARKETING |
| 31 | banking | HIGH | HIGH | PASS | VAGUE_PARTNER_SHARING, MARKETING, MARKETING, MARKETING |
| 32 | job_portals | HIGH | HIGH | PASS | PROFILING, PROFILING, PROFILING, PROFILING |
| 33 | edtech | INSUFFICIENT_EVIDENCE | INSUFFICIENT_EVIDENCE | PASS | none |
| 34 | banking | INSUFFICIENT_EVIDENCE | INSUFFICIENT_EVIDENCE | PASS | none |
| 35 | e_commerce | INSUFFICIENT_EVIDENCE | INSUFFICIENT_EVIDENCE | PASS | none |
| 36 | job_portals | INSUFFICIENT_EVIDENCE | INSUFFICIENT_EVIDENCE | PASS | none |
| 37 | scholarships | INSUFFICIENT_EVIDENCE | INSUFFICIENT_EVIDENCE | PASS | none |
| 38 | government | INSUFFICIENT_EVIDENCE | INSUFFICIENT_EVIDENCE | PASS | none |
| 39 | banking | INSUFFICIENT_EVIDENCE | INSUFFICIENT_EVIDENCE | PASS | none |
| 40 | edtech | INSUFFICIENT_EVIDENCE | INSUFFICIENT_EVIDENCE | PASS | none |

## Known Limitations & Boundaries
1. **Potential Discrepancies Only:** Results highlight textual differences between baseline purposes and disclosure evidence; they do not constitute legal proof of misuse or statutory violation.
2. **Ambiguous Phrasing:** Novel or highly euphemistic privacy policy language may fall back to MEDIUM risk or require manual clarification.
3. **Blind to Internal Practice:** The engine evaluates submitted written text only and cannot inspect unstated server-side telemetry or internal data handling.
4. **Not Legal Advice:** Clarification requests and risk indicators are designed for consumer empowerment and transparency, not formal litigation.