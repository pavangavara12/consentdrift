from fastapi import APIRouter, Request, HTTPException, status
from app.schemas import PlaygroundRequest
from app.auth import check_playground_rate_limit
from app.engine.pipeline import analyze_playground

router = APIRouter(prefix="/api/playground", tags=["playground"])

@router.post("/analyze")
def run_playground_analysis(req: PlaygroundRequest, request: Request):
    """
    Public analysis endpoint for interactive landing page simulator.
    No authentication required. Rate-limited to 20 requests per minute per IP.
    Stores no data in the database.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    check_playground_rate_limit(client_ip)

    original = req.original_purpose.strip()
    evidence = req.evidence_text.strip()

    if not original or not evidence:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both original purpose and evidence statement are required."
        )

    result = analyze_playground(original, evidence)
    return result
