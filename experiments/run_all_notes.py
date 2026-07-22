"""Batch-run the traced pipeline over the synthetic notes.

    python -m experiments.run_all_notes --redaction off            # baseline
    python -m experiments.run_all_notes --redaction on
    python -m experiments.run_all_notes --redaction on --ids 1 2 3

Each note becomes one Langfuse trace tagged redaction:on|off. Per-note results
(decision + timings) also land in results/runs/run_<redaction>_<ts>.jsonl so
experiments don't depend on the Langfuse API alone.
"""

import argparse
import datetime
import json
import os
import time

from discharge_agent import pipeline
from discharge_agent.tracing.instrumentation import get_langfuse, traced_run_note


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--redaction", choices=["on", "off"], required=True)
    parser.add_argument("--ids", type=int, nargs="*", default=None)
    parser.add_argument("--notes-file", action="append", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--out-dir", default="results/runs")
    args = parser.parse_args()

    redaction = args.redaction == "on"
    df = pipeline.load_notes(args.notes_file)
    if args.ids:
        df = df[df["noteid"].isin(args.ids)]
    print(f"running {len(df)} notes, redaction={args.redaction}")

    os.makedirs(args.out_dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(args.out_dir, f"run_{args.redaction}_{stamp}.jsonl")

    ok = 0
    with open(out_path, "w") as f:
        for _, row in df.iterrows():
            note_id = int(row["noteid"])
            t0 = time.perf_counter()
            try:
                out = traced_run_note(
                    row["note_text"],
                    note_id=note_id,
                    model=args.model,
                    redaction=redaction,
                )
            except Exception as e:
                out = {"note_id": note_id, "decision": None, "error": str(e)}
            out["wall_s"] = round(time.perf_counter() - t0, 2)
            out["redaction"] = args.redaction
            f.write(json.dumps(out) + "\n")
            f.flush()
            status = "ok" if out.get("decision") is not None else f"NO-DECISION ({out.get('error', 'unparsed')})"
            if out.get("decision") is not None:
                ok += 1
            print(f"note {note_id}: {status} [{out['wall_s']}s]")

    get_langfuse(redaction=redaction).flush()
    print(f"\n{ok}/{len(df)} notes produced a decision -> {out_path}")


if __name__ == "__main__":
    main()
