from datetime import date
from typing import Any

from app.db.models import CareEvent, CareJourney, Hospital, Policy, PolicyRule


def _text(*values: Any) -> str:
    return " ".join(str(value or "") for value in values).lower()


def _matches(rule: PolicyRule, event: CareEvent) -> bool:
    haystack = _text(event.event_type, event.title, event.details.get("service"), event.details.get("procedure"))
    target = _text(rule.service_name)
    return not target or target in haystack or haystack in target


def _shock(kind: str, severity: str, event: CareEvent, rule: PolicyRule | None, problem: str, action: str) -> dict[str, Any]:
    return {"kind": kind, "severity": severity, "event": event, "rule": rule, "problem": problem, "next_action": action}


def detect_policy_shocks(journey: CareJourney, policy: Policy, hospital: Hospital | None = None) -> list[dict[str, Any]]:
    shocks: list[dict[str, Any]] = []
    network_rule = next((rule for rule in policy.rules if rule.rule_type == "network"), None)
    if hospital and policy.network_name not in (hospital.network_names or []):
        event = next((item for item in journey.events if item.details.get("hospital_id") == hospital.id), journey.events[0] if journey.events else None)
        if event:
            shocks.append(_shock("network_incompatibility", "high", event, network_rule, f"{hospital.name} is outside the {policy.network_name} network.", "Confirm an in-network hospital or request an out-of-network exception."))

    for event in journey.events:
        event_text = _text(event.event_type, event.title, event.details.get("service"), event.details.get("procedure"))
        matched_rules = [rule for rule in policy.rules if _matches(rule, event)]
        for rule in matched_rules:
            rule_type = rule.rule_type.lower()
            if (rule_type in {"exclusion", "procedure_restriction"} and any(term in event_text for term in ("excluded", "exclusion", "not covered"))) or rule_type == "exclusion":
                shocks.append(_shock("procedure_excluded", "critical", event, rule, f"{rule.service_name} is excluded by the policy.", "Ask the insurer about an exception or identify a covered alternative."))
            elif rule_type in {"authorization", "preauthorization"} and rule.requires_authorization and not bool(event.details.get("authorization_confirmed", False)):
                shocks.append(_shock("authorization_required", "high", event, rule, f"Authorization is required for {rule.service_name}.", "Obtain prior authorization before scheduling or proceeding."))
            elif rule_type in {"waiting_period", "waiting"}:
                waiting_days = int((rule.rule_value or {}).get("days", 0))
                elapsed_days = (event.occurred_on - policy.effective_date).days
                if elapsed_days < waiting_days:
                    shocks.append(_shock("waiting_period", "high", event, rule, f"The {rule.service_name} waiting period has not ended.", "Delay non-urgent care or ask the insurer whether an exception applies."))
            elif rule_type in {"sub_limit", "coverage_limit", "limit"}:
                limit_cents = int((rule.rule_value or {}).get("limit_cents", 0))
                estimated_cost = int(event.details.get("estimated_cost_cents", 0))
                if limit_cents and estimated_cost > limit_cents:
                    shocks.append(_shock("coverage_limit", "medium", event, rule, f"Estimated cost exceeds the {rule.service_name} policy limit.", "Request a cost estimate and confirm coverage for the amount above the limit."))
            elif rule_type in {"room_limit", "room_restriction"} and event.details.get("room_type"):
                allowed_room = _text((rule.rule_value or {}).get("room_type"), rule.notes)
                if allowed_room and _text(event.details.get("room_type")) not in allowed_room:
                    shocks.append(_shock("room_restriction", "medium", event, rule, f"Requested room type is outside the policy room restriction.", "Select an eligible room or confirm the additional daily cost."))
        if event.details.get("hospital_network_compatible") is False:
            shocks.append(_shock("network_incompatibility", "high", event, network_rule, "The selected hospital is not compatible with the policy network.", "Choose an in-network hospital or request an exception."))
    return shocks