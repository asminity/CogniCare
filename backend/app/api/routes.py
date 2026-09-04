from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from datetime import date

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import CareEvent, CareJourney, Hospital, IngestionJob, Patient, PatientDocument, Policy, PolicyRule, PolicyShock, Simulation
from app.db.session import get_db
from app.services.compatibility import calculate_compatibility
from app.services.policy_shocks import detect_policy_shocks
from app.services.simulation import simulate_pathway
from app.services.copilot import answer_with_cognicare_data, explain_recommendation, retrieve_cognicare_context
from app.services.policy_extraction import PolicyExtractionError, extract_policy_rules
from app.services.ingestion import ensure_demo_patient, hash_upload, process_ingestion

router = APIRouter(prefix="/api")


class CareRequirement(BaseModel):
    specialty: str = ""
    service: str = ""
    emergency: bool = False
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    max_distance_km: float = Field(default=50, gt=0, le=500)


class CompatibilityRequest(BaseModel):
    patient_id: int
    policy_id: int
    hospital_id: int
    care_requirement: CareRequirement


class CareEventInput(BaseModel):
    event_type: str
    title: str
    occurred_on: date
    status: str = "planned"
    details: dict = Field(default_factory=dict)


class ShockScanRequest(BaseModel):
    policy_id: int
    hospital_id: int | None = None


class SimulationRequest(BaseModel):
    patient_id: int
    policy_id: int
    hospital_ids: list[int] = Field(min_length=2, max_length=6)
    journey_id: int | None = None
    care_requirement: CareRequirement


class EmergencyRequest(BaseModel):
    patient_id: int
    policy_id: int
    care_requirement: CareRequirement


class CopilotRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    patient_id: int
    policy_id: int
    hospital_id: int | None = None
    journey_id: int | None = None
    simulation_id: int | None = None
    care_requirement: CareRequirement | None = None


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


def _ingestion_payload(job: IngestionJob) -> dict:
    return {
        "id": job.id,
        "filename": job.filename,
        "status": job.status,
        "stage": job.stage,
        "progress": job.progress,
        "document_type": job.document_type,
        "patient": {"id": "CG-DEMO-001", "name": "Ananya Sharma", "city": "Nagpur"},
        "document_id": job.document_id,
        "extracted_fields": job.extracted_fields,
        "care_events_updated": job.care_events_updated,
        "error": job.error,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
    }


@router.post("/ingestion/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_ingestion(background_tasks: BackgroundTasks, document: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    if not document.filename:
        raise HTTPException(status_code=422, detail="Choose a file to import.")
    payload = await document.read()
    if not payload:
        raise HTTPException(status_code=422, detail="The selected file is empty.")
    if len(payload) > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Files must be 15 MB or smaller.")
    patient = ensure_demo_patient(db)
    content_hash = hash_upload(payload)
    existing = db.scalar(select(PatientDocument).where(PatientDocument.patient_id == patient.id, PatientDocument.content_hash == content_hash))
    job = IngestionJob(patient_id=patient.id, document_id=existing.id if existing else None, filename=document.filename, content_type=document.content_type or "application/octet-stream", content_hash=content_hash, status="QUEUED", stage="UPLOADING", progress=5, document_type="OTHER")
    db.add(job)
    db.commit()
    db.refresh(job)
    if existing:
        job.status = "COMPLETED"
        job.stage = "COMPLETED"
        job.progress = 100
        job.error = "Document already exists; existing record reused."
        db.commit()
    elif background_tasks is not None:
        background_tasks.add_task(process_ingestion, job.id, payload)
    return _ingestion_payload(job)


@router.get("/ingestion/{job_id}")
def get_ingestion_job(job_id: int, db: Session = Depends(get_db)) -> dict:
    job = db.get(IngestionJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Ingestion job was not found.")
    return _ingestion_payload(job)


@router.get("/ingestion")
def list_ingestion_jobs(db: Session = Depends(get_db)) -> dict:
    jobs = db.scalars(select(IngestionJob).order_by(IngestionJob.id.desc())).all()
    return {"jobs": [_ingestion_payload(job) for job in jobs]}


@router.get("/patients/{patient_id}")
def get_patient_record(patient_id: int, db: Session = Depends(get_db)) -> dict:
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient record was not found.")
    return {"id": patient.id, "patient_id": patient.care_needs.get("demo_patient_id"), "name": patient.full_name, "diagnosis": patient.diagnosis, "care_needs": patient.care_needs, "documents": len(patient.documents), "journeys": len(patient.journeys)}


@router.get("/patients/{patient_id}/documents")
def list_patient_documents(patient_id: int, db: Session = Depends(get_db)) -> dict:
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient record was not found.")
    return {"patient": {"id": "CG-DEMO-001", "name": patient.full_name}, "documents": [{"id": item.id, "filename": item.filename, "document_type": item.document_type, "status": item.status, "size_bytes": item.size_bytes, "uploaded_at": item.uploaded_at, "extraction_summary": item.extraction_summary} for item in sorted(patient.documents, key=lambda item: item.id, reverse=True)]}


def _load_inputs(request: CompatibilityRequest, db: Session) -> tuple[Patient, Policy, Hospital]:
    patient = db.get(Patient, request.patient_id)
    policy = db.get(Policy, request.policy_id)
    hospital = db.get(Hospital, request.hospital_id)
    if not patient or not policy or not hospital:
        raise HTTPException(status_code=404, detail="Patient, policy, or hospital was not found.")
    return patient, policy, hospital


@router.get("/compatibility/options")
def compatibility_options(db: Session = Depends(get_db)) -> dict:
    return {
        "patients": [{"id": item.id, "name": item.full_name, "diagnosis": item.diagnosis} for item in db.scalars(select(Patient).order_by(Patient.full_name))],
        "policies": [{"id": item.id, "name": f"{item.provider_name} - {item.plan_name}", "network_name": item.network_name} for item in db.scalars(select(Policy).order_by(Policy.plan_name))],
        "hospitals": [{"id": item.id, "name": item.name, "city": item.city, "services": item.services, "latitude": item.latitude, "longitude": item.longitude, "emergency_capable": item.emergency_capable} for item in db.scalars(select(Hospital).order_by(Hospital.name))],
    }


@router.post("/compatibility/score")
def compatibility_score(request: CompatibilityRequest, db: Session = Depends(get_db)) -> dict:
    patient, policy, hospital = _load_inputs(request, db)
    return calculate_compatibility(patient, policy, hospital, request.care_requirement.model_dump())


@router.post("/compatibility/rank")
def rank_hospitals(request: CompatibilityRequest, db: Session = Depends(get_db)) -> dict:
    patient, policy, _ = _load_inputs(request, db)
    results = [calculate_compatibility(patient, policy, hospital, request.care_requirement.model_dump()) for hospital in db.scalars(select(Hospital)).all()]
    results.sort(key=lambda item: (-item["total_score"], item["hospital_name"]))
    return {"results": results}


@router.post("/emergency/rank")
def rank_emergency_hospitals(request: EmergencyRequest, db: Session = Depends(get_db)) -> dict:
    patient = db.get(Patient, request.patient_id)
    policy = db.get(Policy, request.policy_id)
    if not patient or not policy:
        raise HTTPException(status_code=404, detail="Patient or policy was not found.")
    requirement = request.care_requirement.model_dump()
    requirement["emergency"] = False
    results = []
    for hospital in db.scalars(select(Hospital)).all():
        compatibility = calculate_compatibility(patient, policy, hospital, requirement)
        distance = compatibility["score_breakdown"]["distance"].get("distance_km")
        service_match = compatibility["score_breakdown"]["required_service"]["matched"] and compatibility["score_breakdown"]["required_specialty"]["matched"]
        results.append({
            "hospital_id": hospital.id,
            "hospital_name": hospital.name,
            "city": hospital.city,
            "latitude": hospital.latitude,
            "longitude": hospital.longitude,
            "emergency_capable": hospital.emergency_capable,
            "distance_km": distance,
            "service_match": service_match,
            "compatibility_score": compatibility["total_score"],
            "policy_compatibility": compatibility["score_breakdown"]["policy_compatibility"],
            "policy_note": "Policy compatibility is advisory in emergency mode; it does not block this hospital.",
            "score_breakdown": compatibility["score_breakdown"],
        })
    results.sort(key=lambda item: (-int(item["emergency_capable"]), item["distance_km"] is None, item["distance_km"] or float("inf"), -int(item["service_match"]), -item["policy_compatibility"]["score"], item["hospital_name"]))
    for rank, item in enumerate(results, start=1):
        item["emergency_rank"] = rank
    return {"results": results, "ordering": ["emergency_capability", "distance", "required_service_and_specialty", "policy_compatibility"]}


@router.post("/copilot/ask")
def copilot_ask(request: CopilotRequest, db: Session = Depends(get_db)) -> dict:
    patient = db.get(Patient, request.patient_id)
    policy = db.get(Policy, request.policy_id)
    hospital = db.get(Hospital, request.hospital_id) if request.hospital_id else None
    journey = db.get(CareJourney, request.journey_id) if request.journey_id else None
    simulation = db.get(Simulation, request.simulation_id) if request.simulation_id else None
    if not patient or not policy or (request.hospital_id and not hospital) or (request.journey_id and not journey) or (request.simulation_id and not simulation):
        raise HTTPException(status_code=404, detail="Requested Cognicare context was not found.")
    context, evidence = retrieve_cognicare_context(request.question, patient, policy, hospital, journey, simulation, request.care_requirement.model_dump() if request.care_requirement else None)
    answer, mode = answer_with_cognicare_data(request.question, context, evidence, get_settings())
    return {"answer": answer, "mode": mode, "evidence": evidence}


@router.post("/recommendations/explain")
def recommendation_explanation(request: CompatibilityRequest, db: Session = Depends(get_db)) -> dict:
    patient, policy, hospital = _load_inputs(request, db)
    compatibility = calculate_compatibility(patient, policy, hospital, request.care_requirement.model_dump())
    return explain_recommendation(compatibility, hospital)


def _event_payload(event: CareEvent) -> dict:
    return {"id": event.id, "event_type": event.event_type, "title": event.title, "occurred_on": event.occurred_on, "status": event.status, "details": event.details}


@router.get("/journeys/{journey_id}")
def get_journey(journey_id: int, db: Session = Depends(get_db)) -> dict:
    journey = db.get(CareJourney, journey_id)
    if not journey:
        raise HTTPException(status_code=404, detail="Care journey was not found.")
    return {"id": journey.id, "patient_id": journey.patient_id, "title": journey.title, "condition": journey.condition, "status": journey.status, "started_on": journey.started_on, "events": [_event_payload(event) for event in sorted(journey.events, key=lambda item: (item.occurred_on, item.id))]}


@router.get("/journeys")
def list_journeys(patient_id: int | None = None, db: Session = Depends(get_db)) -> dict:
    query = select(CareJourney).order_by(CareJourney.id)
    if patient_id is not None:
        query = query.where(CareJourney.patient_id == patient_id)
    journeys = db.scalars(query).all()
    return {"journeys": [{"id": journey.id, "patient_id": journey.patient_id, "title": journey.title, "condition": journey.condition} for journey in journeys]}


@router.post("/journeys/{journey_id}/events", status_code=status.HTTP_201_CREATED)
def add_care_event(journey_id: int, payload: CareEventInput, db: Session = Depends(get_db)) -> dict:
    journey = db.get(CareJourney, journey_id)
    if not journey:
        raise HTTPException(status_code=404, detail="Care journey was not found.")
    event = CareEvent(journey_id=journey_id, **payload.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return _event_payload(event)


@router.patch("/journeys/{journey_id}/events/{event_id}")
def update_care_event(journey_id: int, event_id: int, payload: CareEventInput, db: Session = Depends(get_db)) -> dict:
    event = db.get(CareEvent, event_id)
    if not event or event.journey_id != journey_id:
        raise HTTPException(status_code=404, detail="Care event was not found in this journey.")
    for key, value in payload.model_dump().items():
        setattr(event, key, value)
    db.commit()
    db.refresh(event)
    return _event_payload(event)


def _shock_payload(shock: PolicyShock) -> dict:
    return {"id": shock.id, "kind": shock.title, "problem": shock.explanation, "severity": shock.severity, "event_id": shock.event_id, "affected_event": {"id": shock.event.id, "type": shock.event.event_type, "title": shock.event.title} if shock.event else None, "policy_rule_id": shock.policy_rule_id, "policy_rule": shock.policy_rule.source_text if shock.policy_rule else None, "next_action": shock.next_action, "resolved": shock.resolved}


@router.post("/journeys/{journey_id}/shocks/detect")
def scan_policy_shocks(journey_id: int, request: ShockScanRequest, db: Session = Depends(get_db)) -> dict:
    journey = db.get(CareJourney, journey_id)
    policy = db.get(Policy, request.policy_id)
    hospital = db.get(Hospital, request.hospital_id) if request.hospital_id else None
    if not journey or not policy or (request.hospital_id and not hospital):
        raise HTTPException(status_code=404, detail="Journey, policy, or hospital was not found.")
    db.query(PolicyShock).filter(PolicyShock.journey_id == journey_id, PolicyShock.policy_id == policy.id, PolicyShock.resolved.is_(False)).delete(synchronize_session=False)
    detected = detect_policy_shocks(journey, policy, hospital)
    for item in detected:
        db.add(PolicyShock(patient_id=journey.patient_id, policy_id=policy.id, journey_id=journey.id, event_id=item["event"].id, policy_rule_id=item["rule"].id if item["rule"] else None, severity=item["severity"], title=item["kind"].replace("_", " ").title(), explanation=item["problem"], next_action=item["next_action"]))
    db.commit()
    shocks = db.scalars(select(PolicyShock).where(PolicyShock.journey_id == journey_id, PolicyShock.policy_id == policy.id).order_by(PolicyShock.id)).all()
    return {"journey_id": journey_id, "count": len(shocks), "shocks": [_shock_payload(shock) for shock in shocks]}


@router.get("/journeys/{journey_id}/shocks")
def get_policy_shocks(journey_id: int, db: Session = Depends(get_db)) -> dict:
    shocks = db.scalars(select(PolicyShock).where(PolicyShock.journey_id == journey_id).order_by(PolicyShock.id)).all()
    return {"journey_id": journey_id, "count": len(shocks), "shocks": [_shock_payload(shock) for shock in shocks]}


@router.post("/simulations/compare", status_code=status.HTTP_201_CREATED)
def compare_pathways(request: SimulationRequest, db: Session = Depends(get_db)) -> dict:
    patient = db.get(Patient, request.patient_id)
    policy = db.get(Policy, request.policy_id)
    hospitals = db.scalars(select(Hospital).where(Hospital.id.in_(request.hospital_ids))).all()
    journey = db.get(CareJourney, request.journey_id) if request.journey_id else None
    if not patient or not policy or len(hospitals) != len(set(request.hospital_ids)) or (request.journey_id and not journey):
        raise HTTPException(status_code=404, detail="Patient, policy, journey, or one of the hospitals was not found.")
    pathways = [simulate_pathway(patient, policy, hospital, request.care_requirement.model_dump(), journey) for hospital in sorted(hospitals, key=lambda item: item.id)]
    simulation = Simulation(patient_id=patient.id, policy_id=policy.id, journey_id=journey.id if journey else None, name="Hospital pathway comparison", status="complete", inputs=request.model_dump(), results={"pathways": pathways})
    db.add(simulation)
    db.commit()
    db.refresh(simulation)
    return {"simulation_id": simulation.id, "data_quality_note": "Costs are estimated only where seeded demo cost data exists. No financial values are invented.", "pathways": pathways}


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