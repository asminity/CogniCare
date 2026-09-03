from typing import Any

from app.db.models import CareJourney, Hospital, Patient, Policy
from app.services.compatibility import calculate_compatibility
from app.services.policy_shocks import detect_policy_shocks


def _money(cents: int | None) -> float | None:
    return round(cents / 100, 2) if cents is not None else None


def simulate_pathway(patient: Patient, policy: Policy, hospital: Hospital, care_requirement: dict[str, Any], journey: CareJourney | None = None) -> dict[str, Any]:
    compatibility = calculate_compatibility(patient, policy, hospital, care_requirement)
    service = str(care_requirement.get("service", "")).lower()
    demo_cost = next((cost for name, cost in hospital.demo_costs_cents.items() if name.lower() == service), None)
    if demo_cost is None:
        financial = {
            "total_cost": {"value": None, "status": "unavailable", "basis": "No seeded/demo cost exists for this hospital and service."},
            "insurance_coverage": {"value": None, "status": "unavailable", "basis": "Coverage amount requires a total billed cost."},
            "patient_payment": {"value": None, "status": "unavailable", "basis": "Patient payment requires a total billed cost and deductible balance."},
        }
    else:
        matching_rules = [rule for rule in policy.rules if service and service in rule.service_name.lower()]
        coverage_rule = next((rule for rule in matching_rules if rule.coverage_percent > 0), None)
        coverage_percent = coverage_rule.coverage_percent if coverage_rule else None
        if coverage_percent is None:
            financial = {
                "total_cost": {"value": _money(demo_cost), "status": "estimated", "basis": "Seeded demo hospital cost."},
                "insurance_coverage": {"value": None, "status": "unavailable", "basis": "No matching structured coverage percentage was found."},
                "patient_payment": {"value": None, "status": "unavailable", "basis": "Coverage percentage is unavailable."},
            }
        else:
            copay = coverage_rule.copay_cents if coverage_rule else 0
            covered = round(demo_cost * coverage_percent / 100)
            financial = {
                "total_cost": {"value": _money(demo_cost), "status": "estimated", "basis": "Seeded demo hospital cost."},
                "insurance_coverage": {"value": _money(covered), "status": "estimated", "basis": f"Known policy rule coverage percentage: {coverage_percent}%."},
                "patient_payment": {"value": _money(demo_cost - covered + copay), "status": "estimated", "basis": "Estimated after policy percentage and copay; accumulated deductible balance is unavailable."},
            }
    shocks = detect_policy_shocks(journey, policy, hospital) if journey else []
    policy_risks = compatibility["warnings"] + [item for item in compatibility["failed_conditions"] if "policy" in item.lower() or "network" in item.lower()]
    return {
        "hospital_id": hospital.id,
        "hospital": hospital.name,
        "compatibility_score": compatibility["total_score"],
        "policy_compatibility": compatibility["score_breakdown"]["policy_compatibility"],
        "financial": financial,
        "policy_risks": policy_risks,
        "possible_policy_shocks": [{"kind": item["kind"], "severity": item["severity"], "problem": item["problem"], "next_action": item["next_action"]} for item in shocks],
        "data_quality": {"known": ["compatibility score", "structured policy rules"], "estimated": [key for key, value in financial.items() if value["status"] == "estimated"], "unavailable": [key for key, value in financial.items() if value["status"] == "unavailable"]},
        "explanation": compatibility["explanation"],
    }