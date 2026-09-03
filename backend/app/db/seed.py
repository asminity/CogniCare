from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CareEvent, CareJourney, Hospital, Patient, Policy, PolicyRule


def seed_demo_data(db: Session) -> None:
    if db.scalar(select(Patient.id).limit(1)) is not None:
        return

    maya = Patient(full_name="Maya Thompson", date_of_birth=date(1987, 4, 12), diagnosis="Breast cancer", care_needs={"specialties": ["oncology", "radiology"], "transport": "weekday access"})
    robert = Patient(full_name="Robert Chen", date_of_birth=date(1959, 9, 27), diagnosis="Congestive heart failure", care_needs={"specialties": ["cardiology"], "mobility_support": True})
    gold = Policy(provider_name="Northstar Health Plan", plan_name="Choice Gold PPO", member_id="NSH-MAYA-1042", effective_date=date(2026, 1, 1), network_name="Northstar PPO", deductible_cents=150000, out_of_pocket_max_cents=550000, rules=[
        PolicyRule(rule_type="network", service_name="hospital care", coverage_percent=90, notes="In-network hospitals preferred."),
        PolicyRule(rule_type="authorization", service_name="inpatient oncology", coverage_percent=90, requires_authorization=True, notes="Preauthorization required within 48 hours."),
        PolicyRule(rule_type="specialty", service_name="radiation therapy", coverage_percent=80, copay_cents=5000),
    ])
    silver = Policy(provider_name="Civic Mutual", plan_name="Essential Silver HMO", member_id="CVM-ROBERT-7781", effective_date=date(2026, 1, 1), network_name="Civic HMO Network", deductible_cents=300000, out_of_pocket_max_cents=780000, rules=[
        PolicyRule(rule_type="network", service_name="hospital care", coverage_percent=100, notes="Primary-care referral required."),
        PolicyRule(rule_type="authorization", service_name="cardiac rehabilitation", coverage_percent=80, requires_authorization=True),
        PolicyRule(rule_type="emergency", service_name="emergency department", coverage_percent=100, notes="Emergency stabilization covered out of network."),
    ])
    hospitals = [
        Hospital(name="Metro Oncology Center", city="Boston", state="MA", latitude=42.3367, longitude=-71.0750, network_names=["Northstar PPO"], services=["oncology", "radiology", "infusion"], emergency_capable=True),
        Hospital(name="Riverside General Hospital", city="Boston", state="MA", latitude=42.3612, longitude=-71.0657, network_names=["Northstar PPO", "Civic HMO Network"], services=["emergency", "cardiology", "oncology"], emergency_capable=True),
        Hospital(name="Harbor Cardiac Institute", city="Cambridge", state="MA", latitude=42.3736, longitude=-71.1097, network_names=["Civic HMO Network"], services=["cardiology", "cardiac rehabilitation"]),
        Hospital(name="Eastside Community Hospital", city="Boston", state="MA", latitude=42.3208, longitude=-71.0583, network_names=["Northstar PPO"], services=["emergency", "general surgery"], emergency_capable=True),
    ]
    maya_journey = CareJourney(patient=maya, title="Maya oncology treatment", condition="Breast cancer", started_on=date(2026, 2, 3), events=[
        CareEvent(event_type="consultation", title="Oncology consultation", occurred_on=date(2026, 2, 3), status="completed"),
        CareEvent(event_type="imaging", title="MRI and staging", occurred_on=date(2026, 2, 12), status="planned"),
    ])
    robert_journey = CareJourney(patient=robert, title="Robert cardiac recovery", condition="Congestive heart failure", started_on=date(2026, 1, 18), events=[
        CareEvent(event_type="admission", title="Heart failure admission", occurred_on=date(2026, 1, 18), status="completed"),
        CareEvent(event_type="rehabilitation", title="Cardiac rehabilitation referral", occurred_on=date(2026, 2, 2), status="planned"),
    ])
    db.add_all([maya, robert, gold, silver, *hospitals, maya_journey, robert_journey])
    db.commit()