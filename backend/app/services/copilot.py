import json
from typing import Any

from app.core.config import Settings
from app.db.models import CareJourney, Hospital, Patient, Policy, Simulation
from app.services.compatibility import calculate_compatibility


def _contains(question: str, *terms: str) -> bool:
    question = question.lower()
    return any(term in question for term in terms)


def retrieve_cognicare_context(
    question: str,
    patient: Patient,
    policy: Policy,
    hospital: Hospital | None = None,
    journey: CareJourney | None = None,
    simulation: Simulation | None = None,
    care_requirement: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    terms = set(question.lower().replace("?", " ").split())
    selected_rules = [rule for rule in policy.rules if not terms or any(term in rule.service_name.lower() or term in rule.rule_type.lower() or term in (rule.source_text or "").lower() for term in terms if len(term) > 3)]
    if not selected_rules:
        selected_rules = list(policy.rules)
    evidence = [{"type": "policy_rule", "id": rule.id, "source_page": rule.source_page, "source_text": rule.source_text, "confidence": rule.confidence} for rule in selected_rules[:8]]
    context: dict[str, Any] = {
        "patient": {"id": patient.id, "name": patient.full_name, "diagnosis": patient.diagnosis, "care_needs": patient.care_needs},
        "policy": {"id": policy.id, "provider": policy.provider_name, "plan": policy.plan_name, "network": policy.network_name, "deductible_cents": policy.deductible_cents, "out_of_pocket_max_cents": policy.out_of_pocket_max_cents},
        "policy_rules": [{"id": rule.id, "type": rule.rule_type, "service": rule.service_name, "coverage_percent": rule.coverage_percent, "requires_authorization": rule.requires_authorization, "source_page": rule.source_page, "source_text": rule.source_text, "confidence": rule.confidence} for rule in selected_rules[:8]],
    }
    if hospital:
        context["hospital"] = {"id": hospital.id, "name": hospital.name, "city": hospital.city, "services": hospital.services, "networks": hospital.network_names, "emergency_capable": hospital.emergency_capable}
        if care_requirement:
            compatibility = calculate_compatibility(patient, policy, hospital, care_requirement)
            context["compatibility"] = compatibility
            evidence.append({"type": "compatibility", "hospital": hospital.name, "score": compatibility["total_score"], "breakdown": compatibility["score_breakdown"], "matched": compatibility["matched_conditions"], "failed": compatibility["failed_conditions"]})
    if journey:
        context["journey"] = {"id": journey.id, "title": journey.title, "condition": journey.condition, "events": [{"id": event.id, "type": event.event_type, "title": event.title, "date": str(event.occurred_on), "status": event.status, "details": event.details} for event in journey.events]}
        evidence.append({"type": "care_journey", "id": journey.id, "events": context["journey"]["events"]})
    if simulation:
        context["simulation"] = simulation.results
        evidence.append({"type": "simulation", "id": simulation.id, "results": simulation.results})
    return context, evidence


def _deterministic_answer(question: str, context: dict[str, Any]) -> str:
    compatibility = context.get("compatibility")
    if compatibility and _contains(question, "recommended", "incompatible", "score", "why"):
        return compatibility["explanation"] + " " + ("Matched conditions: " + "; ".join(compatibility["matched_conditions"]) if compatibility["matched_conditions"] else "No compatibility conditions matched.")
    if context.get("simulation") and _contains(question, "cost", "another hospital", "difference", "choose"):
        return "The comparison contains the available pathway estimates. Use the supplied simulation evidence for the cost values; values not present there are unavailable."
    if context.get("journey") and _contains(question, "journey", "shock", "caused"):
        return "The care journey contains " + str(len(context["journey"]["events"])) + " recorded events. Policy shock causes must be read from the linked policy rules and event details returned as evidence."
    if context.get("policy_rules"):
        rule = context["policy_rules"][0]
        return f"The most relevant available policy rule is: {rule['source_text']} (page {rule['source_page']}). I cannot infer conditions beyond the supplied policy data."
    return "I could not find supporting Cognicare data for that question."


def answer_with_cognicare_data(question: str, context: dict[str, Any], evidence: list[dict[str, Any]], settings: Settings) -> tuple[str, str]:
    if not settings.openai_api_key:
        return _deterministic_answer(question, context), "deterministic evidence response"
    try:
        from openai import OpenAI

        prompt = "Answer the caregiver's question using only the Cognicare context below. Never invent policy rules, costs, hospital capabilities, or compatibility scores. If a value is missing, say unavailable. Cite evidence IDs/pages in the answer where applicable. Return plain text only.\n\nQUESTION:\n" + question + "\n\nCONTEXT:\n" + json.dumps(context, default=str)
        response = OpenAI(api_key=settings.openai_api_key).chat.completions.create(model=settings.openai_model, temperature=0, messages=[{"role": "user", "content": prompt}])
        return response.choices[0].message.content or _deterministic_answer(question, context), "OpenAI grounded response"
    except Exception:
        return _deterministic_answer(question, context), "deterministic fallback after LLM failure"


def explain_recommendation(compatibility: dict[str, Any], hospital: Hospital) -> dict[str, Any]:
    breakdown = compatibility["score_breakdown"]
    evidence = [{"condition": key, "score": value["score"], "maximum": value["max"], "matched": value["matched"]} for key, value in breakdown.items()]
    return {"hospital": hospital.name, "explanation": compatibility["explanation"], "evidence": evidence, "matched_conditions": compatibility["matched_conditions"], "failed_conditions": compatibility["failed_conditions"], "warnings": compatibility["warnings"]}