"""Rotate constructor roles on fixed cases; export only audited input/answer pairs."""

from collections import Counter

from .compiler import add_options, apply_audit, proposals
from .evidence import check_graph, digest
from .schemas import ContractError


def roles_for(models, index):
    constructor = models[index]
    others = [m for m in models[index+1:] + models[:index] if m.provider != constructor.provider]
    if not others:
        raise ValueError("construction needs at least two distinct provider families")
    witness = others[0]
    auditor = next((m for m in others[1:] if m.provider != witness.provider), witness)
    return constructor, witness, auditor


def run_comparison(sources, models, session, *, max_items=6, compare=True):
    ledger = session.ledger
    metrics = []
    for source in sources:
        ledger.append("sources", source)
    # Case-by-case ordering preserves reusable source prefixes; calls remain stateless.
    counts = {m.key: Counter(cases=0, accepted_items=0, rejected_items=0, rejected_cases=0,
                              candidate_items=0, mechanically_valid_extractions=0) for m in models}
    for source in sources:
        for index in range(len(models) if compare else 1):
            constructor, witness, auditor = roles_for(models, index)
            count = counts[constructor.key]
            count["cases"] += 1
            identifiers = {"case_id": source["case_id"], "case_group": source["case_group"],
                           "constructor": constructor.key, "witness": witness.key, "auditor": auditor.key}
            pending_ids = set()
            try:
                # Both extractors receive exactly the same source and no previous response.
                payload = {"spans": source["spans"]}
                primary = check_graph(session.call(constructor, "extract", payload), source)
                count["mechanically_valid_extractions"] += 1
                second = check_graph(session.call(witness, "extract", payload), source)
                ledger.append("timelines", {**identifiers, "source_hash": source["source_hash"],
                                             "primary": primary, "witness_graph": second,
                                             "status": "candidate_pending_audit"})
                candidates, exclusions = proposals(primary, source, constructor.key, max_items=max_items)
                count["candidate_items"] += len(candidates)
                pending_ids = {item["item_id"] for item in candidates}
                for exclusion in exclusions:
                    count["excluded_targets"] += 1
                    count[f"excluded_{exclusion['reason']}"] += 1
                    ledger.append("excluded_targets", {**identifiers, **exclusion})
                prepared = []
                for item in candidates:
                    # This allowlisted payload has no gold, source, thesis or later cutoff.
                    try:
                        blind = session.call(witness, "blind", item["input"])
                        enriched = add_options(item, blind)
                    except ContractError as exc:
                        count["rejected_items"] += 1
                        pending_ids.remove(item["item_id"])
                        ledger.append("rejected", {**identifiers, "item_id": item["item_id"],
                                                   "reason": "blind_contract_error", "detail": str(exc)})
                        continue
                    if "rejection" in enriched:
                        count["rejected_items"] += 1
                        pending_ids.remove(item["item_id"])
                        ledger.append("rejected", {**identifiers, **enriched})
                    else:
                        prepared.append(enriched)
                audit_payload = {"spans": source["spans"], "primary": primary, "independent_extraction": second,
                                 "items": [{k: v for k, v in i.items() if k != "blind"} for i in prepared]}
                audit = session.call(auditor, "audit", audit_payload)
                accepted, rejected = apply_audit(primary, source, prepared, audit, constructor.key)
                ledger.append("audits", {**identifiers, "audit": audit, "audit_hash": digest(audit)})
                for entry in accepted:
                    entry["output"]["witness"] = witness.key
                    entry["output"]["auditor"] = auditor.key
                    ledger.append("inputs", entry["input"])
                    ledger.append("outputs", entry["output"])
                for entry in rejected:
                    ledger.append("rejected", {**identifiers, **entry})
                count["accepted_items"] += len(accepted)
                count["rejected_items"] += len(rejected)
                pending_ids.clear()
                count["residual_labels"] += sum(e["output"]["answer_id"] == "OTHER" for e in accepted)
                for entry in accepted:
                    count[f"accepted_{entry['output']['event_type']}"] += 1
                if not accepted:
                    count["rejected_cases"] += 1
                ledger.append("case_results", {**identifiers, "accepted": len(accepted), "rejected": len(candidates) - len(accepted),
                                               "audit_rejected": len(rejected),
                                               "candidate_count": len(candidates), "excluded_target_count": len(exclusions)})
            except ContractError as exc:
                count["rejected_cases"] += 1
                count["rejected_items"] += len(pending_ids)
                for item_id in sorted(pending_ids):
                    ledger.append("rejected", {**identifiers, "item_id": item_id,
                                               "reason": "case_contract_error", "detail": str(exc)})
                ledger.append("rejected", {**identifiers, "reason": "construction_contract_error", "detail": str(exc)})
            # Transport failures and DeferredRequest deliberately escape: incomplete != rejected case.
    for model in models[:len(models) if compare else 1]:
        metrics.append({"constructor": model.key, **dict(counts[model.key])})
    ledger.write_json("construction_metrics.json", {"metrics": metrics,
                     "interpretation": "Pipeline coverage and model-assisted acceptance, not clinical accuracy.",
                     "comparison_limit": "Reviewer roles rotate; constructor differences are not isolated causal effects.",
                     "case_clusters": len({s['case_group'] for s in sources})})
    return metrics
