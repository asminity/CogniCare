"""Synthetic Indian healthcare demo data for the Cognicare prototype."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CareEvent, CareJourney, Hospital, Patient, Policy, PolicyRule


DEMO_POLICY_NUMBER = "CSHP-DEL-26-004182"
DEMO_NETWORK = "CareSecure Cashless Network"


def _rule(rule_type: str, service_name: str, page: int, text: str, *, coverage: int = 0, copay: int = 0, authorization: bool = False, value: dict | None = None) -> PolicyRule:
    return PolicyRule(rule_type=rule_type, service_name=service_name, in_network=True, requires_authorization=authorization, coverage_percent=coverage, copay_cents=copay, notes=text, rule_value=value or {}, source_page=page, source_text=text, confidence=0.98)


def _policy() -> Policy:
    return Policy(provider_name="CareSecure Health Insurance", plan_name="CareSecure Comprehensive Plus", member_id=DEMO_POLICY_NUMBER, effective_date=date(2026, 1, 1), end_date=date(2026, 12, 31), network_name=DEMO_NETWORK, deductible_cents=2500000, out_of_pocket_max_cents=7500000, rules=[
        _rule("hospitalization", "inpatient hospitalization", 4, "Inpatient hospitalization is covered when medically necessary, subject to policy limits.", coverage=70),
        _rule("coverage", "oncology", 5, "Covered oncology treatment is reimbursed at 70% after the annual deductible.", coverage=70),
        _rule("room_limit", "hospital room", 6, "Eligible room category is single private room up to INR 8,000 per day.", value={"room_type": "single private room", "daily_limit_cents": 800000}),
        _rule("icu", "ICU", 7, "ICU is covered up to INR 15,000 per day when clinically required.", coverage=70, value={"daily_limit_cents": 1500000}),
        _rule("network", "hospital care", 8, "Cashless treatment is available only at hospitals in the CareSecure Cashless Network.", coverage=70),
        _rule("authorization", "inpatient oncology", 9, "Pre-authorization is required before planned inpatient oncology treatment.", coverage=70, authorization=True),
        _rule("emergency", "emergency admission", 10, "Emergency admission is covered at eligible hospitals; notify CareSecure within 24 hours.", coverage=70),
        _rule("waiting_period", "cancer treatment", 11, "Cancer treatment has a 90-day waiting period from the policy effective date.", value={"days": 90}),
        _rule("exclusion", "cosmetic surgery", 12, "Cosmetic surgery is excluded unless required for reconstruction after an accident.", value={"excluded": True}),
        _rule("procedure_restriction", "experimental therapy", 13, "Experimental or unproven therapies are not covered.", value={"excluded": True}),
        _rule("copay", "oncology", 14, "A 30% co-payment applies to oncology treatment for insured adults; no separate fixed copay is modelled.", coverage=70, value={"percent": 30}),
        _rule("deductible", "annual deductible", 15, "The annual deductible is INR 25,000 per policy year.", value={"amount_cents": 2500000}),
        _rule("sub_limit", "chemotherapy", 16, "Chemotherapy medicines are covered up to an annual sub-limit of INR 3,00,000.", coverage=70, value={"limit_cents": 30000000}),
        _rule("pre_post_hospitalization", "pre and post hospitalization", 17, "Eligible expenses are covered for 30 days before and 60 days after hospitalization.", coverage=70, value={"pre_days": 30, "post_days": 60}),
    ])


def _patients() -> tuple[Patient, Patient, Patient]:
    return (
        Patient(full_name="Ananya Mehra", date_of_birth=date(1981, 8, 19), diagnosis="Breast cancer, newly diagnosed", care_needs={"age": 45, "city": "Gurugram", "policy_number": DEMO_POLICY_NUMBER, "specialties": ["medical oncology", "surgical oncology"], "required_service": "oncology"}),
        Patient(full_name="Raghav Bhatia", date_of_birth=date(1968, 2, 7), diagnosis="Colorectal cancer under treatment", care_needs={"age": 58, "city": "Noida", "policy_number": DEMO_POLICY_NUMBER, "specialties": ["medical oncology", "gastrointestinal surgery"], "required_service": "chemotherapy"}),
        Patient(full_name="Farah Khan", date_of_birth=date(1994, 11, 3), diagnosis="Suspected lymphoma awaiting biopsy", care_needs={"age": 31, "city": "New Delhi", "policy_number": DEMO_POLICY_NUMBER, "specialties": ["hematology", "medical oncology"], "required_service": "diagnostic imaging"}),
    )


def _hospitals() -> list[Hospital]:
    return [
        Hospital(name="Aarohan Cancer Institute", city="Gurugram", state="Haryana", latitude=28.4595, longitude=77.0266, network_names=[DEMO_NETWORK], services=["oncology", "medical oncology", "surgical oncology", "chemotherapy", "radiology", "biopsy"], demo_costs_cents={"oncology": 95000000, "chemotherapy": 3200000, "radiology": 180000, "biopsy": 125000}, emergency_capable=True),
        Hospital(name="SwasthyaNova Medical Centre", city="New Delhi", state="Delhi", latitude=28.6139, longitude=77.2090, network_names=["Nova Preferred Network"], services=["oncology", "medical oncology", "surgical oncology", "chemotherapy", "radiology", "biopsy", "emergency"], demo_costs_cents={"oncology": 132000000, "chemotherapy": 4100000, "radiology": 240000, "biopsy": 160000}, emergency_capable=True),
        Hospital(name="Nirmal Care Hospital", city="Noida", state="Uttar Pradesh", latitude=28.5355, longitude=77.3910, network_names=[DEMO_NETWORK], services=["oncology", "medical oncology", "chemotherapy", "radiology", "biopsy"], demo_costs_cents={"oncology": 78000000, "chemotherapy": 2750000, "radiology": 145000, "biopsy": 95000}, emergency_capable=False),
        Hospital(name="JeevanSetu General Hospital", city="Faridabad", state="Haryana", latitude=28.4089, longitude=77.3178, network_names=[DEMO_NETWORK], services=["emergency", "general medicine", "diagnostic imaging", "general surgery"], demo_costs_cents={"emergency": 275000, "diagnostic imaging": 85000, "general surgery": 650000}, emergency_capable=True),
    ]


def _journeys(ananya: Patient, raghav: Patient, farah: Patient, non_network: Hospital) -> list[CareJourney]:
    primary = CareJourney(patient=ananya, title="Ananya breast cancer care pathway", condition="Breast cancer, newly diagnosed", status="active", started_on=date(2026, 2, 10), events=[
        CareEvent(event_type="consultation", title="Initial oncology consultation", occurred_on=date(2026, 2, 10), status="completed", details={"specialty": "medical oncology"}),
        CareEvent(event_type="test", title="Breast MRI and staging", occurred_on=date(2026, 2, 16), status="completed", details={"service": "radiology"}),
        CareEvent(event_type="specialist", title="Surgical oncology consultation", occurred_on=date(2026, 2, 23), status="completed", details={"specialty": "surgical oncology"}),
        CareEvent(event_type="procedure", title="Image-guided biopsy", occurred_on=date(2026, 3, 2), status="completed", details={"service": "biopsy"}),
        CareEvent(event_type="consultation", title="Medical oncology treatment consultation", occurred_on=date(2026, 3, 9), status="completed", details={"service": "oncology"}),
        CareEvent(event_type="procedure", title="Treatment planning at Aarohan", occurred_on=date(2026, 3, 16), status="completed", details={"service": "oncology", "hospital_id": 1}),
        CareEvent(event_type="hospital", title="Admission to non-network SwasthyaNova", occurred_on=date(2026, 4, 6), status="planned", details={"service": "inpatient oncology", "hospital_id": non_network.id, "hospital_network_compatible": False}),
        CareEvent(event_type="procedure", title="Inpatient oncology treatment", occurred_on=date(2026, 4, 7), status="planned", details={"service": "inpatient oncology", "hospital_id": non_network.id, "authorization_confirmed": False}),
        CareEvent(event_type="hospital", title="Requested deluxe room", occurred_on=date(2026, 4, 7), status="planned", details={"service": "hospital room", "room_type": "deluxe room", "hospital_id": non_network.id}),
        CareEvent(event_type="discharge", title="Expected discharge", occurred_on=date(2026, 4, 11), status="planned", details={"service": "inpatient hospitalization"}),
        CareEvent(event_type="follow_up", title="Post-treatment review", occurred_on=date(2026, 5, 20), status="planned", details={"service": "oncology"}),
    ])
    secondary = CareJourney(patient=raghav, title="Raghav chemotherapy monitoring", condition="Colorectal cancer under treatment", status="active", started_on=date(2026, 1, 20), events=[CareEvent(event_type="consultation", title="Gastrointestinal oncology review", occurred_on=date(2026, 1, 20), status="completed", details={"specialty": "medical oncology"}), CareEvent(event_type="procedure", title="Chemotherapy cycle planning", occurred_on=date(2026, 2, 3), status="planned", details={"service": "chemotherapy", "authorization_confirmed": True}), CareEvent(event_type="follow_up", title="Treatment response review", occurred_on=date(2026, 3, 5), status="planned", details={"service": "oncology"})])
    diagnostic = CareJourney(patient=farah, title="Farah lymphoma diagnostic pathway", condition="Suspected lymphoma awaiting biopsy", status="active", started_on=date(2026, 6, 4), events=[CareEvent(event_type="consultation", title="Hematology consultation", occurred_on=date(2026, 6, 4), status="completed", details={"specialty": "hematology"}), CareEvent(event_type="test", title="Diagnostic imaging", occurred_on=date(2026, 6, 12), status="planned", details={"service": "diagnostic imaging"}), CareEvent(event_type="follow_up", title="Biopsy results review", occurred_on=date(2026, 6, 25), status="planned", details={"service": "biopsy"})])
    return [primary, secondary, diagnostic]


def seed_demo_data(db: Session) -> None:
    if db.scalar(select(Patient.id).limit(1)) is not None:
        return
    ananya, raghav, farah = _patients()
    hospitals = _hospitals()
    db.add_all([ananya, raghav, farah, _policy(), *hospitals, *_journeys(ananya, raghav, farah, hospitals[1])])
    db.commit()
