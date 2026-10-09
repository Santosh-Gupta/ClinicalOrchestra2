"""Compile typed requests from knowledge phases; keep gold and source metadata out of inputs."""

from __future__ import annotations

from collections import Counter
import random

from .evidence import check_evidence, digest, unique_index
from .schemas import AUDIT, BLIND, ContractError, validate


def visible_state(graph, cut_rank):
    ranks = {p["id"]: p["rank"] for p in graph["phases"]}
    visible = [f for f in graph["facts"] if f["known_phase"] is not None
               and ranks[f["known_phase"]] <= cut_rank]
    visible.sort(key=lambda f: (ranks[f["known_phase"]], f["id"]))
    # Do not serialize phase descriptions, thesis, source refs, or future facts.
    lines = []
    last_rank = None
    for fact in visible:
        rank = ranks[fact["known_phase"]]
        if rank != last_rank:
            lines.append(f"Information phase {rank} (facts within this phase are unordered):")
            last_rank = rank
        lines.append(f"- [{fact['status']}] {fact['claim']}")
    context = "\n".join(lines)
    return context, [f["id"] for f in visible]


def proposals(graph, source, constructor, *, max_items=6):
    ranks = {p["id"]: p["rank"] for p in graph["phases"]}
    facts = {f["id"]: f for f in graph["facts"]}
    groups = Counter((f["known_phase"], f["kind"], f["linked_action_id"]
                      if f["kind"] in {"result", "response"} else None) for f in facts.values())
    items, excluded = [], []
    for fact in sorted(facts.values(), key=lambda f: (ranks.get(f["known_phase"], 100000), f["id"])):
        if fact["kind"] == "context":
            continue
        reason = None
        phase = fact["known_phase"]
        rank = ranks.get(phase, 0)
        group = (phase, fact["kind"], fact["linked_action_id"] if fact["kind"] in {"result", "response"} else None)
        if phase is None or rank == 0:
            reason = "no_supported_earlier_information_state"
        elif groups[group] != 1:
            reason = "simultaneous_targets_require_bundle_or_narrower_endpoint"
        context, visible_ids = visible_state(graph, rank - 1)
        if not visible_ids:
            reason = reason or "empty_visible_state"
        link = fact["linked_action_id"]
        if fact["kind"] in {"result", "response"} and link not in visible_ids:
            reason = reason or "linked_action_not_known_before_cut"
        if fact["kind"] in {"response", "progression"} and fact["endpoint"] is None:
            reason = reason or "no_supported_follow_up_endpoint"
        if reason:
            excluded.append({"fact_id": fact["id"], "reason": reason})
            continue
        if len(items) >= max_items:
            excluded.append({"fact_id": fact["id"], "reason": "fixed_per_case_item_cap"})
            continue
        if fact["kind"] == "action":
            question = "Which action or action bundle was next documented after this information state? Predict the reported course."
        elif fact["kind"] == "diagnosis":
            question = "Which diagnostic assessment or revision did the team next document after this information state?"
        elif fact["kind"] == "result":
            question = f"For this already documented action: {facts[link]['claim']} What result was next reported?"
        elif fact["kind"] == "response":
            question = f"Following this documented treatment: {facts[link]['claim']} What change was reported at {fact['endpoint']}?"
        else:
            question = f"What change in the patient's condition was reported at {fact['endpoint']}?"
        item_id = digest([source["case_id"], constructor, fact["id"], rank - 1])[:24]
        items.append({"item_id": item_id, "target_fact_id": fact["id"],
                      "cut_rank": rank - 1, "visible_fact_ids": visible_ids,
                      "input": {"item_id": item_id, "event_type": fact["kind"],
                                "prediction_axis": "new_information" if fact["kind"] == "result" else
                                "clinical_development" if fact["kind"] in {"progression", "response"} else
                                "documented_action_or_assessment", "context": context, "question": question}})
    return items, excluded


def add_options(item, blind):
    validate(blind, BLIND)
    normalized = [" ".join(x.lower().split()) for x in blind["alternatives"]]
    if len(set(normalized)) != len(normalized):
        raise ContractError("duplicate blind alternatives")
    if blind["defects"]:
        return {**item, "blind": blind, "rejection": "blind_question_defect"}
    alternatives = list(blind["alternatives"])
    # Randomize the labels as well as positions; A must not encode the proposer's first choice.
    seed = {k: v for k, v in item["input"].items() if k != "item_id"}
    rng = random.Random(int(digest(seed), 16))
    rng.shuffle(alternatives)
    options = [{"id": chr(65 + i), "text": x} for i, x in enumerate(alternatives)]
    options.append({"id": "OTHER", "text": "Another documented event or finding not represented by the alternatives."})
    rng.shuffle(options)
    return {**item, "blind": blind, "input": {**item["input"], "options": options,
            "response_instructions": 'Return only JSON {"probabilities": {"candidate_id": probability, ...}}. '
                                     'Include every candidate ID exactly once. Probabilities must be finite, '
                                     'between zero and one, and sum to one. Express uncertainty through this distribution.'}}


def apply_audit(graph, source, items, audit, constructor):
    validate(audit, AUDIT)
    facts = {f["id"]: f for f in graph["facts"]}
    f_reviews = unique_index(audit["fact_reviews"], "fact_id", facts)
    p_reviews = unique_index(audit["phase_reviews"], "phase_id", [p["id"] for p in graph["phases"]])
    c_reviews = unique_index(audit["coverage_reviews"], "span_id", [s["id"] for s in source["spans"]])
    i_reviews = unique_index(audit["item_reviews"], "item_id", [i["item_id"] for i in items])
    for review in list(f_reviews.values()) + list(p_reviews.values()):
        check_evidence(review["evidence"], source, required=review["verdict"] == "supported")
    global_failure = bool(audit["hard_defects"] or audit["unresolved"] or
                          any(r["verdict"] != "supported" for r in list(p_reviews.values()) + list(c_reviews.values())))
    accepted, rejected = [], []
    for item in items:
        review = i_reviews[item["item_id"]]
        check_evidence(review["evidence"], source, required=review["verdict"] == "supported")
        if len(review["visible_fact_ids_checked"]) != len(set(review["visible_fact_ids_checked"])) or set(review["visible_fact_ids_checked"]) != set(item["visible_fact_ids"]):
            raise ContractError("auditor omitted or duplicated visible facts")
        options = {o["id"] for o in item["input"]["options"]}
        if review["answer_id"] is not None and review["answer_id"] not in options:
            raise ContractError("auditor supplied unknown answer option")
        required_facts = set(item["visible_fact_ids"]) | {item["target_fact_id"]}
        failure = global_failure or review["verdict"] != "supported" or bool(review["defects"]) or review["answer_id"] is None or any(f_reviews[f]["verdict"] != "supported" for f in required_facts)
        if failure:
            rejected.append({"item_id": item["item_id"], "reason": "source_audit_rejected",
                             "review": review, "global_failure": global_failure})
            continue
        target = facts[item["target_fact_id"]]
        accepted.append({"input": item["input"], "output": {
            "item_id": item["item_id"], "case_id": source["case_id"], "case_group": source["case_group"],
            "split": source["split"], "constructor": constructor, "answer_id": review["answer_id"],
            "source_reported_answer": target["claim"], "target_fact_id": target["id"],
            "event_type": target["kind"], "clinical_time": target["clinical_time"],
            "known_phase": target["known_phase"], "cut_rank": item["cut_rank"],
            "visible_fact_ids": item["visible_fact_ids"], "evidence": check_evidence(target["evidence"], source),
            "source_hash": source["source_hash"], "source": source["source"],
            "missing_variables": item["blind"]["missing_variables"],
            "label_method": "source_extraction_plus_model_audit", "scoring_method": "exact_candidate_id",
        }})
    return accepted, rejected
