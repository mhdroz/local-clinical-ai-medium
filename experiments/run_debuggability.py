"""Experiment B helper: per-task views over exported (redacted) trace JSONs.

    python -m experiments.run_debuggability --traces results/traces --task 1 --note 1
    python -m experiments.run_debuggability --traces results/traces --task 5

Prints the evidence available for each debugging task; the PASS/DEGRADED/FAIL
grading is done by a human reading these views (results/debuggability_matrix.md).
This is intentionally NOT an auto-grader — LLM-as-judge on traces is the next post.

Tasks:
  1  Did the agent call flag_labs on note N, with plausible argument shapes?
  2  For a note where a tool was skipped: why? (prompt/completion around the gap)
  3  Trace a lab value note -> extraction -> tool input -> tool output.
  4  Verify a followup_gap computation (dates masked -> expect trouble).
  5  Reconstruct token usage + latency per pipeline stage.
"""

import argparse
import glob
import json
import os


def load_traces(trace_dir):
    traces = {}
    for path in sorted(glob.glob(os.path.join(trace_dir, "*.json"))):
        with open(path) as f:
            t = json.load(f)
        note = None
        for tag in t.get("tags") or []:
            if tag.startswith("note:"):
                note = tag.split(":", 1)[1]
        traces[note or os.path.basename(path)] = t
    return traces


def obs_of(trace, type_=None, name_prefix=None):
    out = []
    for o in trace.get("observations", []):
        if type_ and o.get("type") != type_:
            continue
        if name_prefix and not (o.get("name") or "").startswith(name_prefix):
            continue
        out.append(o)
    return out


def shape(x, depth=0):
    """Describe structure without dumping content."""
    if isinstance(x, dict):
        return {k: shape(v, depth + 1) for k, v in x.items()}
    if isinstance(x, list):
        return f"list[{len(x)}]" + (f" of {shape(x[0], depth + 1)}" if x else "")
    if isinstance(x, str):
        return f"str({len(x)})" if len(x) > 30 else x
    return x


def task1(trace, args):
    print("== tool calls in trace ==")
    for o in obs_of(trace, type_="TOOL"):
        print(f"\n{o['name']}")
        print("  input shape:", json.dumps(shape(o.get("input")), indent=2)[:800])
        print("  output:", json.dumps(o.get("output"))[:300])


def task2(trace, args):
    print("== generation-by-generation view (was a tool skipped?) ==")
    for i, o in enumerate(obs_of(trace, type_="GENERATION")):
        msg = o.get("output") or {}
        calls = msg.get("tool_calls") or []
        print(f"\n--- generation {i} ---")
        print("  tool_calls:", [c.get("function", {}).get("name") for c in calls] or "NONE")
        content = (msg.get("content") or "")[:400]
        if content:
            print("  content:", content)
    print("\ntools actually executed:", [o["name"] for o in obs_of(trace, type_="TOOL")])


def task3(trace, args):
    val = args.value
    print(f"== occurrences of {val!r} across payloads ==")
    for o in trace.get("observations", []):
        for field in ("input", "output"):
            blob = json.dumps(o.get(field) or "")
            if val in blob:
                i = blob.find(val)
                print(f"\n{o['name']} [{field}]: …{blob[max(0, i-120):i+120]}…")


def task4(trace, args):
    print("== followup_gap spans ==")
    for o in obs_of(trace, type_="TOOL", name_prefix="execute_tool followup_gap"):
        print("input: ", json.dumps(o.get("input"), indent=2))
        print("output:", json.dumps(o.get("output"), indent=2))
    print("\n(can you verify days_to_earliest_followup from these inputs?)")


def task5(trace, args):
    print("== cost/latency per stage ==")
    total_in = total_out = 0
    for o in trace.get("observations", []):
        usage = o.get("usage") or {}
        tin, tout = usage.get("input") or 0, usage.get("output") or 0
        total_in += tin
        total_out += tout
        lat = o.get("latency")
        print(f"{o['type']:<11} {o['name']:<30} in={tin:<6} out={tout:<6} latency={lat}")
    print(f"\nTOTAL tokens: in={total_in} out={total_out}")


TASKS = {1: task1, 2: task2, 3: task3, 4: task4, 5: task5}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--traces", default="results/traces")
    parser.add_argument("--task", type=int, required=True, choices=sorted(TASKS))
    parser.add_argument("--note", default=None, help="note id (default: all)")
    parser.add_argument("--value", default=None, help="task 3: value to trace (e.g. '12.5')")
    args = parser.parse_args()

    if args.task == 3 and not args.value:
        parser.error("--task 3 requires --value")

    traces = load_traces(args.traces)
    selected = {args.note: traces[args.note]} if args.note else traces
    for note_id, trace in selected.items():
        print(f"\n########## note {note_id} ##########")
        TASKS[args.task](trace, args)


if __name__ == "__main__":
    main()
