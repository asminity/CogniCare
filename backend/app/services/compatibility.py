from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt
from typing import Any

from app.db.models import Hospital, Patient, Policy


@dataclass(frozen=True)
class CompatibilityWeights:
    network: int = 25
    specialty: int = 20
    service: int = 20
    policy: int = 20
    emergency: int = 10
    distance: int = 5


WEIGHTS = CompatibilityWeights()


def _normalize(value: str) -> str:
    return " ".join(value.lower().replace("-", " ").split())


def _distance_km(latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float) -> float:
    earth_radius_km = 6371.0
    lat_delta = radians(latitude_b - latitude_a)
    lon_delta = radians(longitude_b - longitude_a)
    haversine = sin(lat_delta / 2) ** 2 + cos(radians(latitude_a)) * cos(radians(latitude_b)) * sin(lon_delta / 2) ** 2
    return earth_radius_km * 2 * asin(sqrt(haversine))


def _matches(values: list[str], requested: str) -> bool:
    target = _normalize(requested)
    return any(target == _normalize(value) or target in _normalize(value) or _normalize(value) in target for value in values)


def calculate_compatibility(patient: Patient, policy: Policy, hospital: Hospital, care_requirement: dict[str, Any]) -> dict[str, Any]:
    weights = WEIGHTS
    specialty = str(care_requirement.get("specialty", "")).strip()
    service = str(care_requirement.get("service", "")).strip()
    emergency_required = bool(care_requirement.get("emergency", False))
    patient_latitude = care_requirement.get("latitude")
    patient_longitude = care_requirement.get("longitude")
    max_distance_km = float(care_requirement.get("max_distance_km", 50))
    matched: list[str] = []
    failed: list[str] = []
    warnings: list[str] = []

    network_match = _matches(hospital.network_names, policy.network_name)
    (matched if network_match else failed).append(f"Hospital is {'' if network_match else 'not '}in the {policy.network_name} network")

    specialty_match = not specialty or _matches(hospital.services, specialty)
    (matched if specialty_match else failed).append(f"Required specialty: {specialty or 'not specified'}")

    service_match = not service or _matches(hospital.services, service)
    (matched if service_match else failed).append(f"Required service: {service or 'not specified'}")

    relevant_rules = [rule for rule in policy.rules if not service or _matches([rule.service_name], service) or rule.rule_type in {"network", "emergency", "authorization"}]
    policy_match = network_match and bool(relevant_rules or not policy.rules)
    if not relevant_rules and policy.rules:
        warnings.append("No structured policy rule directly matched this care requirement.")
    if any(rule.requires_authorization for rule in relevant_rules):
        warnings.append("Prior authorization may be required before care begins.")
    (matched if policy_match else failed).append("Policy rules support this hospital and care requirement" if policy_match else "Policy rules do not establish coverage for this care requirement")

    emergency_match = not emergency_required or hospital.emergency_capable
    (matched if emergency_match else failed).append("Emergency capability meets the requirement" if emergency_match else "Hospital is not marked as emergency capable")

    distance_km: float | None = None
    if patient_latitude is not None and patient_longitude is not None:
        distance_km = _distance_km(float(patient_latitude), float(patient_longitude), hospital.latitude, hospital.longitude)
    distance_match = distance_km is None or distance_km <= max_distance_km
    if distance_km is None:
        warnings.append("Distance was not scored because the patient's location was not provided.")
    (matched if distance_match else failed).append(f"Distance is within {max_distance_km:g} km" if distance_match else f"Distance exceeds {max_distance_km:g} km")

    score = sum([
        weights.network if network_match else 0,
        weights.specialty if specialty_match else 0,
        weights.service if service_match else 0,
        weights.policy if policy_match else 0,
        weights.emergency if emergency_match else 0,
        weights.distance if distance_match else 0,
    ])
    breakdown = {
        "network_compatibility": {"score": weights.network if network_match else 0, "max": weights.network, "matched": network_match},
        "required_specialty": {"score": weights.specialty if specialty_match else 0, "max": weights.specialty, "matched": specialty_match},
        "required_service": {"score": weights.service if service_match else 0, "max": weights.service, "matched": service_match},
        "policy_compatibility": {"score": weights.policy if policy_match else 0, "max": weights.policy, "matched": policy_match},
        "emergency_capability": {"score": weights.emergency if emergency_match else 0, "max": weights.emergency, "matched": emergency_match},
        "distance": {"score": weights.distance if distance_match else 0, "max": weights.distance, "matched": distance_match, "distance_km": round(distance_km, 1) if distance_km is not None else None},
    }
    explanation = f"{hospital.name} scores {score}/100 because {len(matched)} of 6 compatibility conditions matched."
    return {"hospital_id": hospital.id, "hospital_name": hospital.name, "total_score": score, "score_breakdown": breakdown, "matched_conditions": matched, "failed_conditions": failed, "warnings": warnings, "explanation": explanation}