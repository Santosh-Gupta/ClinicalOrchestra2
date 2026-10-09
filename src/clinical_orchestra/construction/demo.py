"""Synthetic transport fixtures. These responses test plumbing, never model or clinical quality."""

from copy import deepcopy
import json


def demo_record():
    return {"case_id": "synthetic-dual-timeline", "case_group": "synthetic-patient-1",
            "split": "synthetic", "source": {"title": "Invented software test fixture", "synthetic": True},
            "case_text": "On admission, the patient had fever.\n\n"
                         "On day 1, a serum assay was ordered.\n\n"
                         "On day 2, the assay was reported negative to the team.\n\n"
                         "After reading the assay result on day 2, the team started supportive treatment.\n\n"
                         "On day 5, the team documented improvement after supportive treatment.\n\n"
                         "On day 4, family disclosed that symptoms had begun two days before admission."}


def demo_graph():
    paragraphs = demo_record()["case_text"].split("\n\n")
    def ref(index):
        return [{"span_id": f"p{index:04d}", "quote": paragraphs[index]}]
    phases = [{"id": f"k{rank}", "rank": rank, "evidence": ref(index)}
              for rank, index in enumerate([0, 1, 2, 3, 5, 4])]
    claims = ["The patient had fever on admission.", "On day 1, a serum assay was ordered.",
              "On day 2, the serum assay was reported negative.", "After reading the result on day 2, supportive treatment was started.",
              "On day 5, the patient improved after supportive treatment.", "On day 4, family reported symptoms began two days before admission."]
    kinds = ["context", "action", "result", "action", "response", "context"]
    phase_ids = ["k0", "k1", "k2", "k3", "k5", "k4"]
    facts = []
    for i in range(6):
        facts.append({"id": f"f{i}", "patient_id": "patient", "kind": kinds[i], "claim": claims[i],
                      "evidence": ref(i), "clinical_time": {"description": ["admission", "day 1", "day 2", "day 2", "day 5", "two days before admission"][i], "evidence": ref(i)},
                      "clinical_after": [f"f{i-1}"] if 1 <= i <= 4 else ["f5"] if i == 0 else [],
                      "known_phase": phase_ids[i], "known_evidence": ref(i),
                      "status": "ordered" if i == 1 else "performed" if i == 3 else "observed",
                      "linked_action_id": "f1" if i == 2 else "f3" if i == 4 else None,
                      "endpoint": "day 5" if i == 4 else None,
                      "endpoint_evidence": ref(i) if i == 4 else []})
    return {"phases": phases, "facts": facts,
            "coverage": [{"span_id": f"p{i:04d}", "fact_ids": [f"f{i}"],
                          "disposition": "represented", "reason": "Synthetic patient event represented."} for i in range(6)],
            "thesis": [], "unresolved": []}


def demo_responder(model, stage, payload):
    if stage == "extract":
        result = demo_graph()
    elif stage == "blind":
        kind = payload["event_type"]
        if kind == "result":
            alternatives = ["The assay was negative.", "The assay was positive.", "The assay was indeterminate."]
        elif kind == "response":
            alternatives = ["The patient improved.", "The patient remained unchanged.", "The patient worsened."]
        elif "negative" in payload["context"]:
            alternatives = ["Supportive treatment was started.", "A repeat assay was ordered.", "The patient was discharged."]
        else:
            alternatives = ["A serum assay was ordered.", "Chest imaging was ordered.", "Observation without new orders continued."]
        result = {"defects": [], "missing_variables": [], "alternatives": alternatives}
    else:
        graph = payload["primary"]
        result = {"fact_reviews": [{"fact_id": f["id"], "verdict": "supported", "evidence": f["evidence"], "reason": "Scripted synthetic fixture."} for f in graph["facts"]],
                  "phase_reviews": [{"phase_id": p["id"], "verdict": "supported", "evidence": p["evidence"], "reason": "Scripted synthetic fixture."} for p in graph["phases"]],
                  "coverage_reviews": [{"span_id": s["id"], "verdict": "supported", "reason": "Scripted synthetic fixture."} for s in payload["spans"]],
                  "item_reviews": [], "hard_defects": [], "unresolved": []}
        facts = {f["id"]: f for f in graph["facts"]}
        targets = {"f1": "A serum assay was ordered.", "f2": "The assay was negative.",
                   "f3": "Supportive treatment was started.", "f4": "The patient improved."}
        for item in payload["items"]:
            answer = next((o["id"] for o in item["input"]["options"] if o["text"] == targets.get(item["target_fact_id"])), "OTHER")
            result["item_reviews"].append({"item_id": item["item_id"], "verdict": "supported", "answer_id": answer,
                                         "evidence": facts[item["target_fact_id"]]["evidence"],
                                         "visible_fact_ids_checked": item["visible_fact_ids"], "defects": [],
                                         "reason": "Scripted synthetic fixture; no clinical/model validity claim."})
    return {"model": model.spec.model_id, "content": json.dumps(deepcopy(result)),
            "raw": {"synthetic": True, "usage": {}}, "latency_ms": 0}
