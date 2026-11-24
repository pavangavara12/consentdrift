import os
import sys
from pathlib import Path
from datetime import datetime, timezone

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

os.environ["DISABLE_SQLALCHEMY_CEXT"] = "1"

import json
from app.config import LLM_API_KEY
from app.engine.pipeline import analyze

CLASSES = ["LOW", "MEDIUM", "HIGH", "INSUFFICIENT_EVIDENCE"]

class DummyItem:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

def evaluate_mode(samples, force_rules_only=True):
    total = len(samples)
    correct = 0
    false_high_count = 0
    predictions = []

    # Initialize 4x4 confusion matrix: matrix[expected][predicted]
    matrix = {exp: {pred: 0 for pred in CLASSES} for exp in CLASSES}

    for s in samples:
        consent = DummyItem(
            original_purpose=s["original_purpose"],
            service_name=s.get("domain", "DemoService"),
            data_categories=[]
        )
        evidence = DummyItem(
            content=s["evidence_text"],
            evidence_type="email"
        )

        res = analyze(consent, evidence, force_rules_only=force_rules_only)
        predicted = res["risk"]
        expected = s["expected_risk"]

        if predicted not in CLASSES:
            predicted = "INSUFFICIENT_EVIDENCE"

        matrix[expected][predicted] += 1

        is_correct = (predicted == expected)
        if is_correct:
            correct += 1

        if predicted == "HIGH" and expected != "HIGH":
            false_high_count += 1

        predictions.append({
            "id": s["id"],
            "domain": s.get("domain"),
            "expected": expected,
            "predicted": predicted,
            "correct": is_correct,
            "signals": [sig["signal"] for sig in res.get("rule_signals", [])],
            "quotes": res.get("evidence_quotes", []),
            "explanation": res.get("explanation", "")
        })

    accuracy = correct / total if total > 0 else 0.0

    # Calculate per-class precision, recall, F1
    per_class = {}
    for c in CLASSES:
        tp = matrix[c][c]
        fp = sum(matrix[other][c] for other in CLASSES if other != c)
        fn = sum(matrix[c][other] for other in CLASSES if other != c)
        support = sum(matrix[c][col] for col in CLASSES)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        per_class[c] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": support
        }

    return {
        "total": total,
        "correct": correct,
        "accuracy": round(accuracy, 4),
        "false_high_count": false_high_count,
        "confusion_matrix": matrix,
        "per_class": per_class,
        "predictions": predictions
    }

def generate_markdown_report(rules_results, hybrid_results=None):
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "# ConsentDrift Evaluation & Benchmark Report",
        f"\n**Generated at:** {now_str}",
        f"**Benchmark Dataset:** 40 curated multi-domain scenarios (10 LOW, 10 MEDIUM, 12 HIGH, 8 INSUFFICIENT_EVIDENCE)",
        "\n---\n",
        "## Summary Metrics\n",
        "| Evaluation Mode | Total Samples | Accuracy | False HIGH Alarms |",
        "| :--- | :---: | :---: | :---: |",
        f"| **Rules-Only Mode** | {rules_results['total']} | **{rules_results['accuracy'] * 100:.1f}%** | **{rules_results['false_high_count']}** |",
    ]

    if hybrid_results:
        lines.append(f"| **Hybrid (LLM + Rules)** | {hybrid_results['total']} | **{hybrid_results['accuracy'] * 100:.1f}%** | **{hybrid_results['false_high_count']}** |")
    else:
        lines.append("| **Hybrid (LLM + Rules)** | — | *Skipped (No LLM key configured)* | — |")

    lines.extend([
        "\n> [!IMPORTANT]",
        "> False HIGH alarms (predicting HIGH when expected is not HIGH) are the most critical failure mode in privacy purpose drift auditing. Minimizing false alarms protects users against alert fatigue and unnecessary dispute escalations.\n",
        "\n## Rules-Only Mode: 4×4 Confusion Matrix\n",
        "Rows represent Expected Ground Truth; Columns represent ConsentDrift Pipeline Predictions.\n",
        "| Expected \\ Predicted | LOW | MEDIUM | HIGH | INSUFFICIENT_EVIDENCE |",
        "| :--- | :---: | :---: | :---: | :---: |"
    ])

    for exp in CLASSES:
        row = rules_results["confusion_matrix"][exp]
        lines.append(f"| **{exp}** | {row['LOW']} | {row['MEDIUM']} | {row['HIGH']} | {row['INSUFFICIENT_EVIDENCE']} |")

    lines.extend([
        "\n## Rules-Only Mode: Per-Class Performance\n",
        "| Class | Support | Precision | Recall | F1-Score |",
        "| :--- | :---: | :---: | :---: | :---: |"
    ])

    for c in CLASSES:
        m = rules_results["per_class"][c]
        lines.append(f"| **{c}** | {m['support']} | {m['precision']*100:.1f}% | {m['recall']*100:.1f}% | {m['f1']*100:.1f}% |")

    lines.extend([
        "\n## Sample-by-Sample Analysis Breakdown\n",
        "| ID | Domain | Expected | Predicted | Status | Detected Signals |",
        "| :-: | :--- | :---: | :---: | :---: | :--- |"
    ])

    for p in rules_results["predictions"]:
        status_icon = "PASS" if p["correct"] else "FAIL"
        sigs = ", ".join(p["signals"]) if p["signals"] else "none"
        lines.append(f"| {p['id']} | {p['domain']} | {p['expected']} | {p['predicted']} | {status_icon} | {sigs} |")

    lines.extend([
        "\n## Known Limitations & Boundaries",
        "1. **Potential Discrepancies Only:** Results highlight textual differences between baseline purposes and disclosure evidence; they do not constitute legal proof of misuse or statutory violation.",
        "2. **Ambiguous Phrasing:** Novel or highly euphemistic privacy policy language may fall back to MEDIUM risk or require manual clarification.",
        "3. **Blind to Internal Practice:** The engine evaluates submitted written text only and cannot inspect unstated server-side telemetry or internal data handling.",
        "4. **Not Legal Advice:** Clarification requests and risk indicators are designed for consumer empowerment and transparency, not formal litigation."
    ])

    return "\n".join(lines)

def run():
    dataset_path = Path(__file__).resolve().parent / "dataset.json"
    if not dataset_path.exists():
        print(f"Error: {dataset_path} not found.")
        sys.exit(1)

    with open(dataset_path, "r", encoding="utf-8") as f:
        samples = json.load(f)

    print(f"\nEvaluating ConsentDrift on {len(samples)} benchmark samples...")

    # 1. Run Rules-Only Evaluation
    rules_results = evaluate_mode(samples, force_rules_only=True)

    # 2. Run Hybrid Evaluation if LLM key configured
    hybrid_results = None
    if LLM_API_KEY:
        print("LLM API key detected. Running Hybrid mode evaluation...")
        try:
            hybrid_results = evaluate_mode(samples, force_rules_only=False)
        except Exception as e:
            print(f"Warning: Hybrid evaluation failed: {e}")
            hybrid_results = None
    else:
        print("No LLM_API_KEY configured. Skipping Hybrid mode evaluation.")

    # 3. Print Console Summary
    print("\n" + "=" * 65)
    print("                CONSENTDRIFT BENCHMARK RESULTS")
    print("=" * 65)
    print(f"Rules-Only Accuracy:   {rules_results['accuracy'] * 100:.1f}% ({rules_results['correct']}/{rules_results['total']})")
    print(f"False HIGH Alarms:     {rules_results['false_high_count']}")
    if hybrid_results:
        print(f"Hybrid Accuracy:       {hybrid_results['accuracy'] * 100:.1f}% ({hybrid_results['correct']}/{hybrid_results['total']})")
        print(f"Hybrid False HIGHs:    {hybrid_results['false_high_count']}")
    print("-" * 65)
    print(f"{'Class':<24} {'Support':<10} {'Precision':<12} {'Recall':<10} {'F1':<10}")
    print("-" * 65)
    for c in CLASSES:
        m = rules_results["per_class"][c]
        print(f"{c:<24} {m['support']:<10} {m['precision']*100:>8.1f}%  {m['recall']*100:>7.1f}%  {m['f1']*100:>7.1f}%")
    print("=" * 65 + "\n")

    # 4. Save JSON results for API & UI
    output_json = {
        "status": "completed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample_count": len(samples),
        "metrics": {
            "rules_only": {
                "total": rules_results["total"],
                "accuracy": rules_results["accuracy"],
                "false_high_count": rules_results["false_high_count"],
                "confusion_matrix": rules_results["confusion_matrix"],
                "per_class": rules_results["per_class"]
            }
        }
    }
    if hybrid_results:
        output_json["metrics"]["hybrid"] = {
            "total": hybrid_results["total"],
            "accuracy": hybrid_results["accuracy"],
            "false_high_count": hybrid_results["false_high_count"],
            "confusion_matrix": hybrid_results["confusion_matrix"],
            "per_class": hybrid_results["per_class"]
        }

    json_path = Path(__file__).resolve().parent / "results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output_json, f, indent=2)
    print(f"Saved evaluation JSON to: {json_path}")

    # 5. Save Markdown report
    md_content = generate_markdown_report(rules_results, hybrid_results)
    md_path = Path(__file__).resolve().parent / "results.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"Saved human-readable report to: {md_path}\n")

if __name__ == "__main__":
    run()
