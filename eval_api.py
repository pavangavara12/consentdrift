import json
from pathlib import Path
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/eval", tags=["evaluation"])

@router.get("/results")
def get_eval_results():
    # Look for results.json in eval/ relative to backend or root
    candidates = [
        Path(__file__).resolve().parent.parent.parent.parent / "eval" / "results.json",
        Path(__file__).resolve().parent.parent.parent / "eval" / "results.json",
        Path("eval/results.json"),
    ]

    for p in candidates:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed reading eval results: {e}")

    # Default fallback if eval hasn't run yet
    return {
        "status": "pending",
        "message": "Evaluation has not been executed yet. Run 'python eval/run_eval.py' to generate benchmark results.",
        "metrics": {
            "rules_only": {
                "total": 0,
                "accuracy": 0.0,
                "confusion_matrix": {},
                "per_class": {},
                "false_high_count": 0
            }
        }
    }
