from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Policy, PolicyRule
from app.db.session import get_db
from app.services.policy_extraction import PolicyExtractionError, extract_policy_rules

router = APIRouter(prefix="/api")


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/policies/extract", status_code=status.HTTP_201_CREATED)
async def extract_policy(
    document: UploadFile = File(...),
    provider_name: str = Form("Demo Insurance"),
    plan_name: str = Form("Extracted Policy"),
    db: Session = Depends(get_db),
) -> dict:
    if document.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(status_code=415, detail="Upload a PDF policy document.")
    pdf_bytes = await document.read()
    if not pdf_bytes:
        raise HTTPException(status_code=422, detail={"stage": "upload", "message": "The uploaded PDF is empty."})
    try:
        result = extract_policy_rules(pdf_bytes, get_settings())
    except PolicyExtractionError as exc:
        raise HTTPException(status_code=422, detail={"stage": exc.stage, "message": str(exc)}) from exc

    policy = Policy(
        provider_name=provider_name,
        plan_name=plan_name,
        member_id=f"EXTRACTED-{uuid4().hex[:12].upper()}",
        effective_date=__import__("datetime").date.today(),
        network_name="Extracted network",
        deductible_cents=0,
        out_of_pocket_max_cents=0,
    )
    policy.rules = [PolicyRule(
        rule_type=rule.rule_type,
        service_name=rule.service_name,
        in_network=rule.in_network,
        requires_authorization=rule.requires_authorization,
        coverage_percent=rule.coverage_percent,
        copay_cents=rule.copay_cents,
        notes=rule.notes,
        rule_value=rule.value,
        source_page=rule.source_page,
        source_text=rule.source_text,
        confidence=rule.confidence,
    ) for rule in result.rules]
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return {
        "policy_id": policy.id,
        "filename": document.filename,
        "pages": result.pages,
        "method": result.method,
        "warning": result.warning,
        "rules": [{
            "id": rule.id,
            "rule_type": rule.rule_type,
            "service_name": rule.service_name,
            "source_page": rule.source_page,
            "source_text": rule.source_text,
            "confidence": rule.confidence,
        } for rule in policy.rules],
    }