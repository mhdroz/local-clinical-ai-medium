"""Experiment A: redaction quality per PHI category, against exact ground truth.

    python -m experiments.run_redaction_eval
    python -m experiments.run_redaction_eval --policy v2   # after Phase 4C
    python -m experiments.run_redaction_eval --leak-check results/traces

Evaluation is ANALYZER-LEVEL: ground-truth spans are defined on the raw note
text, so we score what Presidio detects on that text. (Trace payloads contain
LLM-transformed text where char spans don't exist; the --leak-check pass covers
the end-to-end plumbing by grepping exported trace JSONs for every ground-truth
surface string.)

Matching rule (stated because it materially changes the numbers):
  - A ground-truth entity counts as DETECTED (typed) if any predicted span of a
    compatible entity type overlaps it by >= 1 char.
  - It counts as MASKED-AT-ALL if any predicted span of ANY type overlaps it —
    for privacy, an MRN flagged as PHONE_NUMBER is still masked; only the label
    is wrong. Both recalls are reported.
  - A predicted span is a FALSE POSITIVE if it overlaps no ground-truth entity
    compatible with its type. Every FP is logged with context.
"""

import argparse
import json
import os
from collections import defaultdict

import pandas as pd

from discharge_agent.redaction.masker import DEFAULT_ENTITIES, SCORE_THRESHOLD
from discharge_agent.redaction.recognizers import build_analyzer

# ground-truth category -> compatible Presidio entity types
COMPAT = {
    "PATIENT_NAME": {"PERSON"},
    "PROVIDER_NAME": {"PERSON"},
    "DOB": {"DATE_TIME"},
    "DATE": {"DATE_TIME"},
    "PHONE": {"PHONE_NUMBER"},
    "ADDRESS": {"LOCATION", "ADDRESS"},
    "MRN": {"MRN"},
}
CATEGORIES = list(COMPAT.keys())


def overlaps(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end


def evaluate_note(analyzer, note_text, gt_entities, policy=None):
    preds = analyzer.analyze(
        text=note_text,
        language="en",
        entities=DEFAULT_ENTITIES,
        score_threshold=SCORE_THRESHOLD,
    )
    if policy is not None:
        preds = policy.filter_results(note_text, preds)

    per_gt = []
    for gt in gt_entities:
        compatible = COMPAT[gt["entity_type"]]
        typed = any(
            p.entity_type in compatible and overlaps(p.start, p.end, gt["start"], gt["end"])
            for p in preds
        )
        any_mask = any(overlaps(p.start, p.end, gt["start"], gt["end"]) for p in preds)
        per_gt.append({**gt, "detected_typed": typed, "masked_at_all": any_mask})

    false_positives = []
    type_mismatches = 0
    typed_preds = 0
    for p in preds:
        hit_typed = any(
            p.entity_type in COMPAT[gt["entity_type"]]
            and overlaps(p.start, p.end, gt["start"], gt["end"])
            for gt in gt_entities
        )
        hit_any = any(overlaps(p.start, p.end, gt["start"], gt["end"]) for gt in gt_entities)
        if hit_typed:
            typed_preds += 1
            continue
        if hit_any:
            # masked real PHI under the wrong label ("02/28 0630" as
            # PHONE_NUMBER) — wrong taxonomy, right privacy outcome; counted
            # separately, not as a false positive
            type_mismatches += 1
            continue
        ctx_lo = max(0, p.start - 40)
        ctx_hi = min(len(note_text), p.end + 40)
        false_positives.append(
            {
                "entity_type": p.entity_type,
                "text": note_text[p.start : p.end],
                "score": round(p.score, 3),
                "context": note_text[ctx_lo:ctx_hi].replace("\n", " "),
            }
        )
    return per_gt, false_positives, type_mismatches, typed_preds


def load_notes_map(paths):
    notes = {}
    for p in paths:
        if os.path.exists(p):
            df = pd.read_csv(p)
            for _, row in df.iterrows():
                notes[str(int(row["noteid"]))] = row["note_text"]
    return notes


def leak_check(trace_dir, ground_truth):
    """Grep exported trace JSONs for ground-truth surface strings. Any hit in a
    redaction:on trace is a leak (plumbing failure, not analyzer failure)."""
    leaks = []
    for fname in sorted(os.listdir(trace_dir)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(trace_dir, fname)) as f:
            blob = f.read()
        note_id = fname.split("_")[1] if "_" in fname else None
        gt = ground_truth.get(note_id)
        if not gt:
            continue
        for e in gt["entities"]:
            # skip very short strings that can appear by chance
            if len(e["text"]) >= 4 and e["text"] in blob:
                leaks.append({"file": fname, "entity_type": e["entity_type"], "text": e["text"]})
    return leaks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ground-truth", default="data/phi_ground_truth.json")
    parser.add_argument(
        "--notes",
        action="append",
        default=None,
        help="note CSVs (default: original + extended)",
    )
    parser.add_argument("--policy", choices=["none", "v2"], default="none")
    parser.add_argument("--out-prefix", default="results/redaction_metrics")
    parser.add_argument("--fp-log", default="results/redaction_false_positives.md")
    parser.add_argument("--leak-check", default=None, help="dir of exported redacted traces")
    args = parser.parse_args()

    with open(args.ground_truth) as f:
        ground_truth = json.load(f)

    notes = load_notes_map(args.notes or ["data/synthetic_notes.csv", "data/synthetic_notes_extended.csv"])

    policy = None
    if args.policy == "v2":
        from discharge_agent.redaction.policy import clinical_policy_v2

        policy = clinical_policy_v2()

    if args.leak_check:
        leaks = leak_check(args.leak_check, ground_truth)
        print(f"leak check over {args.leak_check}: {len(leaks)} leaks")
        for leak in leaks:
            print(" LEAK:", leak)
        with open("results/leak_check.json", "w") as f:
            json.dump(leaks, f, indent=2)
        return

    # policy v2 pairs with the extended analyzer (structural recognizers)
    analyzer = build_analyzer(extended=(policy is not None))

    stats = {c: {"n": 0, "typed": 0, "any": 0} for c in CATEGORIES}
    fp_by_type = defaultdict(list)
    n_notes = 0
    n_mismatch = 0
    n_typed_preds = 0
    all_details = {}

    for note_id, gt in ground_truth.items():
        if note_id == "meta":
            continue
        if note_id not in notes:
            print(f"warning: note {note_id} has ground truth but no note text — skipped")
            continue
        n_notes += 1
        per_gt, fps, mismatches, typed_preds = evaluate_note(
            analyzer, notes[note_id], gt["entities"], policy
        )
        n_mismatch += mismatches
        n_typed_preds += typed_preds
        for g in per_gt:
            s = stats[g["entity_type"]]
            s["n"] += 1
            s["typed"] += g["detected_typed"]
            s["any"] += g["masked_at_all"]
        for fp in fps:
            fp_by_type[fp["entity_type"]].append({**fp, "note_id": note_id})
        all_details[note_id] = {"entities": per_gt, "false_positives": fps}

    n_fp = sum(len(v) for v in fp_by_type.values())

    summary = {
        "config": {
            "policy": args.policy,
            "score_threshold": SCORE_THRESHOLD,
            "notes_evaluated": n_notes,
            "matching": "char-overlap; typed = compatible entity type, any = any type",
        },
        "per_category": {},
        "overall": {},
    }
    for c in CATEGORIES:
        s = stats[c]
        summary["per_category"][c] = {
            "ground_truth_count": s["n"],
            "recall_typed": round(s["typed"] / s["n"], 3) if s["n"] else None,
            "recall_masked_at_all": round(s["any"] / s["n"], 3) if s["n"] else None,
        }
    fp_counts = {k: len(v) for k, v in fp_by_type.items()}
    summary["overall"] = {
        "false_positives_total": n_fp,
        "false_positives_by_predicted_type": fp_counts,
        "type_mismatched_masks": n_mismatch,
        "predictions_typed_correct": n_typed_preds,
        # precision over predictions: typed-correct / (typed-correct + true FPs);
        # type-mismatched masks are excluded from both sides (see module docstring)
        "precision_typed_overall": round(n_typed_preds / (n_typed_preds + n_fp), 3)
        if (n_typed_preds + n_fp)
        else None,
    }

    os.makedirs(os.path.dirname(args.out_prefix) or ".", exist_ok=True)
    suffix = "" if args.policy == "none" else f"_{args.policy}"
    with open(f"{args.out_prefix}{suffix}.json", "w") as f:
        json.dump({"summary": summary, "details": all_details}, f, indent=2)

    # markdown summary table
    lines = [
        f"# Redaction metrics (policy: {args.policy})",
        "",
        f"{n_notes} notes, score threshold {SCORE_THRESHOLD}. "
        "Matching: char overlap. `recall (typed)` requires a compatible entity type; "
        "`recall (masked at all)` counts any overlapping detection — wrong label but still masked.",
        "",
        "| PHI category | ground truth | recall (typed) | recall (masked at all) |",
        "|---|---|---|---|",
    ]
    for c in CATEGORIES:
        s = summary["per_category"][c]
        lines.append(
            f"| {c} | {s['ground_truth_count']} | {s['recall_typed']} | {s['recall_masked_at_all']} |"
        )
    lines += [
        "",
        f"**False positives:** {n_fp} total — {json.dumps(fp_counts)}. "
        f"Overall typed precision: {summary['overall']['precision_typed_overall']}. "
        "Every FP is listed in redaction_false_positives" + (suffix or "") + ".md.",
    ]
    with open(f"{args.out_prefix}{suffix}.md", "w") as f:
        f.write("\n".join(lines) + "\n")

    fp_path = args.fp_log.replace(".md", f"{suffix}.md")
    fp_lines = [f"# False positives (policy: {args.policy})", ""]
    for etype, fps in sorted(fp_by_type.items()):
        fp_lines.append(f"## predicted {etype} ({len(fps)})")
        fp_lines.append("")
        for fp in fps:
            fp_lines.append(
                f"- note {fp['note_id']} (score {fp['score']}): `{fp['text']}` — …{fp['context']}…"
            )
        fp_lines.append("")
    with open(fp_path, "w") as f:
        f.write("\n".join(fp_lines) + "\n")

    print(json.dumps(summary, indent=2))
    print(f"\nwrote {args.out_prefix}{suffix}.json / .md and {fp_path}")


if __name__ == "__main__":
    main()
