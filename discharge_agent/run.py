"""CLI for the discharge pipeline.

    python -m discharge_agent.run --note-id 1                # traced, redaction from .env
    python -m discharge_agent.run --note-id 1 --redaction on
    python -m discharge_agent.run --all --redaction on
    python -m discharge_agent.run --note-id 1 --trace off    # no Langfuse at all
"""

import argparse
import json
import os
import sys

from dotenv import load_dotenv

from discharge_agent import pipeline

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Run the discharge safety pipeline")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--note-id", type=int, help="noteid from the synthetic notes CSVs")
    group.add_argument("--all", action="store_true", help="run every note")
    parser.add_argument(
        "--redaction",
        choices=["on", "off"],
        default=os.getenv("REDACTION", "off").strip('"'),
        help="mask PHI in trace payloads before export (default: REDACTION from .env)",
    )
    parser.add_argument(
        "--trace",
        choices=["on", "off"],
        default="on",
        help="send traces to Langfuse (default on)",
    )
    parser.add_argument("--model", default=None, help="Ollama model (default: MODEL from .env)")
    parser.add_argument(
        "--notes-file",
        action="append",
        default=None,
        help="CSV of notes (repeatable; default: data/synthetic_notes*.csv)",
    )
    args = parser.parse_args()

    df = pipeline.load_notes(args.notes_file)
    if args.all:
        rows = df
    else:
        rows = df[df["noteid"] == args.note_id]
        if rows.empty:
            sys.exit(f"note-id {args.note_id} not found (have: {sorted(df['noteid'])})")

    results = []
    for _, row in rows.iterrows():
        note_id = int(row["noteid"])
        if args.trace == "on":
            from discharge_agent.tracing.instrumentation import traced_run_note

            out = traced_run_note(
                row["note_text"],
                note_id=note_id,
                model=args.model,
                redaction=(args.redaction == "on"),
            )
        else:
            out = pipeline.run_note(row["note_text"], note_id=note_id, model=args.model)
        results.append(out)
        print(f"--- note {note_id} ---")
        print(json.dumps(out.get("decision") or {"error": out.get("error"), "raw": out.get("decision_raw")}, indent=2))

    if args.trace == "on":
        from discharge_agent.tracing.instrumentation import get_langfuse

        get_langfuse(redaction=(args.redaction == "on")).flush()

    return results


if __name__ == "__main__":
    main()
