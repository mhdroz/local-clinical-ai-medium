"""Export traces from Langfuse to JSON files (Experiment B input + blog assets).

    python -m experiments.fetch_traces --tag redaction:on --out results/traces
    python -m experiments.fetch_traces --trace-id <id> --out results/baseline_trace_example.json

Fetching via the API (instead of screenshotting the UI) makes the
debuggability experiment reproducible and diffable: the redacted trace JSONs
are committed and can be re-fetched after the fix iteration for comparison.
"""

import argparse
import json
import os

from dotenv import load_dotenv
from langfuse import Langfuse

load_dotenv()


def get_client() -> Langfuse:
    return Langfuse(
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        host=os.getenv("LANGFUSE_HOST", "http://localhost:3000"),
    )


def trace_to_dict(full_trace) -> dict:
    """Full trace incl. observations, ordered by start time."""
    d = full_trace.dict()
    d["observations"] = sorted(
        d.get("observations", []),
        key=lambda o: str(o.get("start_time") or o.get("startTime") or ""),
    )
    return d


def fetch_by_tag(lf: Langfuse, tag: str, limit: int = 100) -> list:
    traces, page = [], 1
    while True:
        batch = lf.api.trace.list(tags=[tag], limit=50, page=page)
        traces.extend(batch.data)
        if len(batch.data) < 50 or len(traces) >= limit:
            break
        page += 1
    return traces[:limit]


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--tag", help="fetch all traces with this tag (e.g. redaction:on)")
    group.add_argument("--trace-id", help="fetch a single trace")
    parser.add_argument("--out", required=True, help="output dir (--tag) or file (--trace-id)")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    lf = get_client()

    if args.trace_id:
        full = lf.api.trace.get(args.trace_id)
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w") as f:
            json.dump(trace_to_dict(full), f, indent=2, default=str)
        print(f"wrote {args.out}")
        return

    os.makedirs(args.out, exist_ok=True)
    traces = fetch_by_tag(lf, args.tag, args.limit)
    print(f"{len(traces)} traces tagged {args.tag}")
    for t in traces:
        full = lf.api.trace.get(t.id)
        note_tag = next((x for x in (t.tags or []) if x.startswith("note:")), None)
        note_id = note_tag.split(":", 1)[1] if note_tag else t.id[:8]
        path = os.path.join(args.out, f"note_{note_id}_{t.id[:8]}.json")
        with open(path, "w") as f:
            json.dump(trace_to_dict(full), f, indent=2, default=str)
        print(f"  {path}")


if __name__ == "__main__":
    main()
