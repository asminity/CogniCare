from __future__ import annotations

import hashlib
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CareEvent, CareJourney, IngestionJob, Patient, PatientDocument

DEMO_PATIENT_KEY = "CG-DEMO-001"
DEMO_PATIENT_NAME = "Ananya Sharma"


def ensure_demo_patient(db: Session) -> Patient:
    patient = db.scalar(select(Patient).where(Patient.care_needs["demo_patient_id"].as_string() == DEMO_PATIENT_KEY))
    if patient:
        return patient
    patient = db.scalar(select(Patient).order_by(Patient.id))
    if not patient:
        patient = Patient(full_name=DEMO_PATIENT_NAME, date_of_birth=date(1974, 1, 1), diagnosis="Synthetic oncology demo record", care_needs={})
        db.add(patient)
        db.flush()
    needs = dict(patient.care_needs or {})
    needs.setdefault("demo_patient_id", DEMO_PATIENT_KEY)
    needs.setdefault("gender", "Female")
    needs.setdefault("city", "Nagpur")
    needs.setdefault("age", 52)
    patient.full_name = DEMO_PATIENT_NAME
    patient.care_needs = needs
    db.commit()
    db.refresh(patient)
    return patient


def classify_document(filename: str, content_type: str) -> str:
    name = filename.lower()
    if any(word in name for word in ("insurance", "policy", "benefit", "coverage")):
        return "INSURANCE_POLICY"
    if any(word in name for word in ("discharge", "admission", "hospital")):
        return "DISCHARGE_SUMMARY" if "discharge" in name else "HOSPITAL_DOCUMENT"
    if any(word in name for word in ("prescription", "rx", "medication")):
        return "PRESCRIPTION"
    if any(word in name for word in ("lab", "blood", "test", "pathology")):
        return "LAB_REPORT"
    if any(word in name for word in ("care", "plan", "treatment")):
        return "CARE_PLAN"
    if any(word in name for word in ("report", "oncology", "clinical", "medical")):
        return "MEDICAL_REPORT"
    if content_type.startswith(("image/", "text/", "application/")):
        return "OTHER"
    return "OTHER"


def _update_stage(db: Session, job: IngestionJob, stage: str, progress: int) -> None:
    job.stage = stage
    job.progress = progress
    job.status = "PROCESSING"
    db.commit()
    time.sleep(0.18)


def process_ingestion(job_id: int, payload: bytes) -> None:
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        job = db.get(IngestionJob, job_id)
        if not job:
            return
        try:
            _update_stage(db, job, "VALIDATING", 15)
            _update_stage(db, job, "CLASSIFYING", 30)
            job.document_type = classify_document(job.filename, job.content_type)
            db.commit()
            _update_stage(db, job, "EXTRACTING", 48)
            _update_stage(db, job, "MATCHING_PATIENT", 66)
            patient = db.get(Patient, job.patient_id) or ensure_demo_patient(db)
            existing = db.scalar(select(PatientDocument).where(PatientDocument.patient_id == patient.id, PatientDocument.content_hash == job.content_hash))
            if existing:
                job.document_id = existing.id
                job.stage = "COMPLETED"
                job.status = "COMPLETED"
                job.progress = 100
                job.error = "Document already exists; existing record reused."
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
                return
            _update_stage(db, job, "UPDATING_RECORD", 82)
            summary: dict[str, Any] = {"patient_name": DEMO_PATIENT_NAME, "patient_id": DEMO_PATIENT_KEY, "synthetic": True, "extraction_mode": "controlled demo classification"}
            document = PatientDocument(patient_id=patient.id, filename=job.filename, content_type=job.content_type, content_hash=job.content_hash, size_bytes=len(payload), document_type=job.document_type, extraction_summary=summary)
            db.add(document)
            needs = dict(patient.care_needs or {})
            needs.setdefault("demo_patient_id", DEMO_PATIENT_KEY)
            needs.setdefault("gender", "Female")
            needs.setdefault("city", "Nagpur")
            needs.setdefault("age", 52)
            needs["last_ingested_document_type"] = job.document_type
            patient.care_needs = needs
            journey = db.scalar(select(CareJourney).where(CareJourney.patient_id == patient.id).order_by(CareJourney.id))
            if journey:
                db.add(CareEvent(journey_id=journey.id, event_type="document", title=f"Imported {job.document_type.replace('_', ' ').title()}", occurred_on=date.today(), status="completed", details={"document_id": document.id, "synthetic": True}))
                job.care_events_updated = 1
            job.extracted_fields = 5
            db.flush()
            job.document_id = document.id
            job.stage = "COMPLETED"
            job.status = "COMPLETED"
            job.progress = 100
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
        except Exception as exc:
            db.rollback()
            job = db.get(IngestionJob, job_id)
            if job:
                job.status = "FAILED"
                job.stage = "FAILED"
                job.error = "The document was stored, but structured extraction was unavailable."
                db.commit()


def hash_upload(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def extension_for(filename: str) -> str:
    return Path(filename).suffix.lower().lstrip(".") or "unknown"
