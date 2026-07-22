"""Experiment C: before/after table for the redaction fix iteration.

    python -m experiments.run_iteration_comparison

Reads results/redaction_metrics.json (baseline: default Presidio + MRN
recognizer) and results/redaction_metrics_v2.json (policy v2: clinical
allowlist, benign-date filters, structural header/date recognizers, date-shift
surrogates) and writes results/iteration_comparison.md. Run both evals first:

    python -m experiments.run_redaction_eval
    python -m experiments.run_redaction_eval --policy v2
"""

import json

BASE = "results/redaction_metrics.json"
V2 = "results/redaction_metrics_v2.json"
OUT = "results/iteration_comparison.md"


def main():
    with open(BASE) as f:
        base = json.load(f)["summary"]
    with open(V2) as f:
        v2 = json.load(f)["summary"]

    def fmt(x):
        return "—" if x is None else f"{x:.3f}"

    lines = [
        "# Redaction fix iteration: baseline vs policy v2",
        "",
        f"Notes evaluated: {base['config']['notes_evaluated']} (baseline) / "
        f"{v2['config']['notes_evaluated']} (v2). Matching: {base['config']['matching']}.",
        "",
        "Policy v2 = clinical-eponym allowlist + benign-date filters (ages, durations,",
        "frequencies, clock times, pain/strength scores) + structural recognizers",
        "(header names, bare m/d dates) + per-trace date-shift surrogates.",
        "",
        "| PHI category | GT count | recall (typed) base → v2 | recall (masked at all) base → v2 |",
        "|---|---|---|---|",
    ]
    for cat, b in base["per_category"].items():
        n = v2["per_category"][cat]
        lines.append(
            f"| {cat} | {b['ground_truth_count']} "
            f"| {fmt(b['recall_typed'])} → **{fmt(n['recall_typed'])}** "
            f"| {fmt(b['recall_masked_at_all'])} → **{fmt(n['recall_masked_at_all'])}** |"
        )
    bo, no = base["overall"], v2["overall"]
    lines += [
        "",
        "| overall | baseline | policy v2 |",
        "|---|---|---|",
        f"| false positives | {bo['false_positives_total']} | **{no['false_positives_total']}** |",
        f"| precision (typed) | {fmt(bo['precision_typed_overall'])} | **{fmt(no['precision_typed_overall'])}** |",
        f"| type-mismatched masks | {bo.get('type_mismatched_masks', '—')} | {no.get('type_mismatched_masks', '—')} |",
        "",
        "Notes:",
        "- The DATE recall jump comes almost entirely from the bare-`m/d` structural",
        "  recognizer — spaCy's DATE_TIME simply does not see `03/15:`-style lab dates.",
        "- ADDRESS recall is essentially unchanged: street addresses are a known",
        "  Presidio/spaCy weak spot and would need a dedicated address recognizer",
        "  (out of scope for this iteration; kept as an honest limitation).",
        "- Date-shift surrogates do not change detection metrics; their effect shows",
        "  in the debuggability matrix (interval arithmetic survives redaction).",
        "- Residual date ambiguity: `9/10` (pain) vs `09/10` (Sept 10) cannot be",
        "  resolved by pattern alone; the policy keeps unpadded pain scores visible.",
    ]
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {OUT}")
    print("\n".join(lines[:20]))


if __name__ == "__main__":
    main()
