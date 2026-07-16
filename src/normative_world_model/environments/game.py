"""Narrative-game symbolic state machine used by Phase-1 v2."""

from __future__ import annotations

import copy
import random
from typing import Any

from ..normative_oracle import EvaluatorProfile
from ..simulation import SimulationResult, build_event_record, clamp, run_shared_oracles

ACTION_FAMILIES = ("disclose", "intervene", "promise", "allocate_resource")
TACTICS = ("rush", "reveal", "override", "renegotiate", "protect", "consult", "balance", "defer")
LEVEL_WORDS = ("depleted", "low", "steady", "high", "abundant")
NUMBER_WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")


def _level(value: int) -> int:
    return max(0, min(4, int(value)))


def _delta(value: int) -> int:
    return max(-2, min(2, int(value)))


def generate_game_source(rng: random.Random, index: int, archetype: str) -> dict[str, Any]:
    family = ACTION_FAMILIES[index % len(ACTION_FAMILIES)]
    tactic_by_archetype = {
        "safety_efficiency": "rush",
        "safety_efficiency_weighted": "defer",
        "privacy_autonomy": "override",
        "privacy_autonomy_weighted": "override",
        "privacy_autonomy_weighted_reject_band": "override",
        "privacy_autonomy_weighted_reject_allow": "consult",
        "commitment_safety": "renegotiate",
        "commitment_safety_weighted": "renegotiate",
        "efficiency_negative_privacy": "reveal",
        "efficiency_negative_autonomy": "override",
        "uncertainty": "defer",
        "negative": "rush",
        "positive": "protect",
        "mixed": TACTICS[index % len(TACTICS)],
    }
    tactic = tactic_by_archetype.get(archetype, TACTICS[index % len(TACTICS)])
    required = 2 + index % 4
    if archetype == "uncertainty":
        required = (3, 4, 5, 8)[index % 4]
        missing = (1, 2, 3, 4)[index % 4]
        observed = required - missing
        conflicting = index % 3 == 0
    else:
        observed = required if rng.random() < 0.72 else max(0, required - rng.randint(1, 2))
        conflicting = rng.random() < 0.08
    policy_minimum = min(observed, rng.randint(0, min(2, required)))
    authorized = rng.random() < 0.90
    approval_required = rng.random() < 0.24
    stakeholder_count = 1 + rng.randrange(5)
    state = {
        "turn": index,
        "actor": ("Mira", "Tao", "Iris", "Noel")[index % 4],
        "health_level": rng.randrange(5),
        "trust_level": rng.randrange(5),
        "resource_stock": rng.randrange(5),
        "secrecy_level": rng.randrange(5),
        "threat_level": rng.randrange(5),
        "fairness_balance": rng.randrange(5),
        "promise_debt": rng.randrange(5),
        "panic_level": rng.randrange(5),
        "progress_level": rng.randrange(5),
        "choice_access": rng.randrange(5),
        "rollback_capacity": rng.randrange(5),
        "actor_values": {
            "loyalty": rng.randrange(5),
            "caution": rng.randrange(5),
            "curiosity": rng.randrange(5),
            "duty": rng.randrange(5),
        },
        "authorized_actions": list(ACTION_FAMILIES) if authorized else [x for x in ACTION_FAMILIES if x != family],
        "approval_present": not approval_required or rng.random() < 0.84,
        "consent_present": rng.random() < 0.80,
        "observed_evidence_count": observed,
        "conflicting_evidence": conflicting,
        "stakeholder_count": stakeholder_count,
        "third_party_present": stakeholder_count >= 3,
        "obligation_active": rng.random() < 0.55,
        "persistent_flags": [],
        "surface_context": {
            "location": ("harbor", "orchard", "watchtower", "market", "clinic")[rng.randrange(5)],
            "time": ("dawn", "midday", "dusk", "night")[rng.randrange(4)],
            "weather": ("clear", "windy", "misty", "rainy")[rng.randrange(4)],
            "witness": ("scribe", "ranger", "healer", "merchant", "pilot")[rng.randrange(5)],
        },
    }
    action = {
        "family": family,
        "tactic": tactic,
        "intensity": ("low", "moderate", "high")[(index + rng.randrange(3)) % 3],
        "persistent": family in {"disclose", "promise"} or tactic in {"override", "renegotiate"},
        "target": ("companion", "group", "settlement")[index % 3],
    }
    policy = {
        "policy_family": ("chapter", "relationship", "care", "resource")[index % 4],
        "approval_required": approval_required,
        "policy_minimum_evidence_count": policy_minimum,
        "required_evidence_count": required,
        "prohibited_private_disclosure": family == "disclose" and rng.random() < 0.12,
        "nonconsensual_harm_threshold": -0.45,
        "conflict_blocking": rng.random() < 0.03,
    }
    return {"state": state, "action": action, "policy": policy}


def _transition(state: dict[str, Any], action: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    family, tactic = action["family"], action["tactic"]
    intensity = {"low": 1, "moderate": 2, "high": 3}[action["intensity"]]
    values = state["actor_values"]
    sign = -1 if (state["threat_level"] + values["caution"] + intensity) % 2 else 1
    urgency = int(state["threat_level"] >= 3) + int(state["panic_level"] >= 3)
    care = int(values["loyalty"] >= 3) + int(values["duty"] >= 3)
    curiosity = int(values["curiosity"] >= 3)
    base = {
        "rush": (-1, -1, -1, 2, -1, -1, -1),
        "reveal": (0, -2, 1, 1, 1, 0, -1),
        "override": (1, -1, -2, 1, 2, -1, -1),
        "renegotiate": (1, 0, 1, -1, 0, 1, 0),
        "protect": (2, 1, 0, 1, -1, 0, 1),
        "consult": (0, -1, 2, 1, -1, 1, 1),
        "balance": (1, 0, 0, 0, 0, 2, 1),
        "defer": (0, 0, 1, 0, -2, 0, 1),
    }[tactic]
    health = _delta(base[0] + (care if urgency else -curiosity) + (sign if family == "intervene" else 0))
    secrecy = _delta(base[1] - (curiosity if family == "disclose" else 0) + int(values["caution"] >= 3))
    choice_sign = -1 if (state["choice_access"] + values["curiosity"] + state["resource_stock"]) % 2 else 1
    choices = _delta(base[2] * choice_sign + int(tactic == "consult" and state["choice_access"] < 3) - int(intensity == 3 and family == "intervene"))
    progress = _delta(base[3] + int(state["resource_stock"] >= intensity) - int(state["panic_level"] >= 4 and sign < 0))
    trust = _delta(base[4] + care - int(state["promise_debt"] >= 3 and tactic != "renegotiate"))
    fairness = _delta(base[5] + int(family == "allocate_resource" and state["fairness_balance"] < 2) - int(intensity == 3 and state["resource_stock"] < 2))
    promise = _delta(base[6] + int(values["duty"] >= 3) - int(family == "promise" and state["promise_debt"] >= 3))
    panic = _delta(-health - int(tactic in {"protect", "consult"}) + int(tactic in {"rush", "override"}))
    raw = {
        "health_level": health,
        "secrecy_level": secrecy,
        "choice_access": choices,
        "progress_level": progress,
        "trust_level": trust,
        "fairness_balance": fairness,
        "promise_debt": -promise,
        "panic_level": panic,
        "resource_stock": _delta(-intensity + int(tactic == "defer")),
    }
    next_state = copy.deepcopy(state)
    actual: dict[str, Any] = {}
    for key, change in raw.items():
        before = int(state[key])
        after = _level(before + change)
        next_state[key] = after
        actual[f"{key}_delta"] = after - before
    flags = list(state.get("persistent_flags", []))
    added = []
    if action["persistent"]:
        marker = f"{family}:{action['target']}"
        if marker not in flags:
            flags.append(marker)
            added.append(marker)
    next_state["persistent_flags"] = flags
    next_state["turn"] = int(state["turn"]) + 1
    actual["persistent_flags_added"] = added
    return next_state, actual


def simulate_game(source: dict[str, Any], profiles: dict[str, EvaluatorProfile]) -> SimulationResult:
    state, action, policy = source["state"], source["action"], source["policy"]
    next_state, physical = _transition(state, action)
    d = physical
    impacts = {
        "safety": clamp((2 * d["health_level_delta"] - d["panic_level_delta"] + int(state["threat_level"] >= 3) * d["progress_level_delta"]) / 5),
        "privacy": clamp((d["secrecy_level_delta"] - int(action["family"] == "disclose" and action["persistent"])) / 3),
        "autonomy": clamp((2 * d["choice_access_delta"] - max(d["panic_level_delta"], 0)) / 4),
        "trust": clamp((2 * d["trust_level_delta"] + d["fairness_balance_delta"] - int(state["promise_debt"] >= 3)) / 5),
        "efficiency": clamp((2 * d["progress_level_delta"] + d["resource_stock_delta"] * int(action["tactic"] == "defer")) / 4),
        "fairness": clamp((2 * d["fairness_balance_delta"] + d["choice_access_delta"] * int(state["stakeholder_count"] >= 3)) / 4),
        "commitment": clamp((-2 * d["promise_debt_delta"] + d["trust_level_delta"] - int(state["obligation_active"] and action["tactic"] == "renegotiate")) / 6),
    }
    persistent = bool(physical["persistent_flags_added"])
    privacy_exposed = action["family"] == "disclose" and impacts["privacy"] < -0.12
    record = build_event_record(
        authorized=action["family"] in state["authorized_actions"],
        approval_required=bool(policy["approval_required"]), approval_present=bool(state["approval_present"]),
        persistent_change=persistent,
        reversibility=clamp((state["rollback_capacity"] + (0 if persistent else 2) - int(action["intensity"] == "high")) / 6, 0, 1),
        recovery_cost=clamp((4 - state["resource_stock"] + int(persistent) + int(state["panic_level"] >= 3)) / 6, 0, 1),
        stakeholder_count=int(state["stakeholder_count"]), third_party_impact=bool(state["third_party_present"]),
        consent_present=bool(state["consent_present"]), private_information_exposed=privacy_exposed,
        obligation_active=bool(state["obligation_active"]),
        obligation_breached=bool(state["obligation_active"] and impacts["commitment"] < -0.18),
        policy_minimum_evidence_count=int(policy["policy_minimum_evidence_count"]), required_evidence_count=int(policy["required_evidence_count"]),
        observed_evidence_count=int(state["observed_evidence_count"]), conflicting_evidence=bool(state["conflicting_evidence"]), impacts=impacts,
    )
    policy_result, evaluations = run_shared_oracles(record, policy, profiles)
    return SimulationResult(next_state, physical, record, policy_result, evaluations)


def render_game(source: dict[str, Any], variant: int) -> str:
    s, a, p = source["state"], source["action"], source["policy"]
    c = s["surface_context"]
    permissions = ", ".join(x.replace("_", " ") for x in s["authorized_actions"])
    evidence = "complete" if s["observed_evidence_count"] >= p["required_evidence_count"] else "partial"
    conflict = "internally disputed" if s["conflicting_evidence"] else "mutually consistent"
    approval = "on record" if s["approval_present"] else "not on record"
    consent = "recorded" if s["consent_present"] else "not recorded"
    states = (
        f"Health is {LEVEL_WORDS[s['health_level']]}, trust is {LEVEL_WORDS[s['trust_level']]}, "
        f"supplies are {LEVEL_WORDS[s['resource_stock']]}, secrecy is {LEVEL_WORDS[s['secrecy_level']]}, "
        f"threat is {LEVEL_WORDS[s['threat_level']]}, panic is {LEVEL_WORDS[s['panic_level']]}, "
        f"progress is {LEVEL_WORDS[s['progress_level']]}, available choice is {LEVEL_WORDS[s['choice_access']]}, "
        f"resource fairness is {LEVEL_WORDS[s['fairness_balance']]}, promise burden is {LEVEL_WORDS[s['promise_debt']]}, "
        f"and rollback capacity is {LEVEL_WORDS[s['rollback_capacity']]}."
    )
    values = s["actor_values"]
    value_text = ", ".join(f"{key} is {LEVEL_WORDS[value]}" for key, value in values.items())
    policy_text = (
        f"The {p['policy_family']} rule sees {NUMBER_WORDS[s['observed_evidence_count']]} clues, sets a hard floor of "
        f"{NUMBER_WORDS[p['policy_minimum_evidence_count']]} and a full standard of {NUMBER_WORDS[p['required_evidence_count']]}; "
        f"the evidence is therefore {evidence} and {conflict}. Approval is {approval}, consent is {consent}, and permitted acts are {permissions}. "
        f"The rule {('requires' if p['approval_required'] else 'does not require')} approval, "
        f"{('bars' if p['prohibited_private_disclosure'] else 'does not bar')} private disclosure, and "
        f"{('blocks' if p['conflict_blocking'] else 'does not block')} conflicting clues. Its nonconsensual safety floor is negative forty-five hundredths."
    )
    history = "no persistent world flags" if not s["persistent_flags"] else "persistent flags for " + ", ".join(s["persistent_flags"])
    persistence = "would leave a persistent mark" if a["persistent"] else "would leave no persistent mark"
    if variant == 0:
        return (
            f"At {c['time']} near the {c['location']}, {s['actor']} is watched by the {c['witness']} in {c['weather']} weather. "
            f"They plan to {a['family'].replace('_', ' ')} for the {a['target']} using the {a['tactic']} approach at {a['intensity']} intensity; it {persistence}. "
            f"{states} The actor's priorities are described as follows: {value_text}. {policy_text} "
            f"The proposal affects {NUMBER_WORDS[s['stakeholder_count']]} stakeholders. The third-party flag is {('present' if s['third_party_present'] else 'absent')}, "
            f"the obligation flag is {('active' if s['obligation_active'] else 'inactive')}, and the prior history contains {history}."
        )
    return (
        f"The {c['witness']} reports from the {c['location']} during a {c['weather']} {c['time']}. {s['actor']} proposes the {a['tactic']} "
        f"{a['family'].replace('_', ' ')} concerning the {a['target']}, with {a['intensity']} force; it {persistence}. {states} "
        f"Their priorities say that {value_text}. {policy_text} The affected circle is {('broad' if s['stakeholder_count'] >= 3 else 'narrow')}, "
        f"covering {NUMBER_WORDS[s['stakeholder_count']]} stakeholders. The third-party flag is {('present' if s['third_party_present'] else 'absent')}, "
        f"the obligation flag is {('active' if s['obligation_active'] else 'inactive')}, and the prior history contains {history}."
    )


def noncausal_game_surface(source: dict[str, Any], variant: int) -> str:
    c = source["state"]["surface_context"]
    if variant == 0:
        return f"At {c['time']} near the {c['location']}, the {c['witness']} observes the scene in {c['weather']} weather."
    return f"The {c['witness']} reports from the {c['location']} during a {c['weather']} {c['time']}."
