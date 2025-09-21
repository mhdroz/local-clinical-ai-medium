# examples/evaluate_tool_use.py
import json, time, statistics
from typing import Dict, Any, List
import requests

from discharge_agent.tools.labs import flag_labs
from discharge_agent.tools.followup import followup_gap
from discharge_agent.tools.umls_client import normalize_terms_to_cui
from discharge_agent.llm.tool_specs import TOOLS
from discharge_agent.pipelines.discharge_checker import check_discharge_safety, chat
from dotenv import load_dotenv
import os

load_dotenv()

API = os.getenv("LLM_API")
MODEL = os.getenv("MODEL")


# Heuristics: simple rules to determine when a tool SHOULD be used
def should_use_flag_labs(rj: Dict[str, Any]) -> bool:
    labs = rj.get("abnormal_labs") or rj.get("most_recent_labs") or []
    return len(labs) > 0


def should_use_followup_gap(rj: Dict[str, Any]) -> bool:
    return bool(rj.get("follow_up_appointments"))


def should_use_umls(rj: Dict[str, Any]) -> bool:
    dx = rj.get("primary_discharge_diagnosis") or ""
    return bool(dx.strip())


# Tool runner with logging
class ToolLogger:
    def __init__(self):
        self.events: List[Dict[str, Any]] = []

    def runner(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        start = time.perf_counter()
        ok = True
        error = None
        try:
            if name == "flag_labs":
                out = flag_labs(**args)
            elif name == "followup_gap":
                out = followup_gap(**args)
            elif name == "umls_normalize":
                out = normalize_terms_to_cui(**args)
            else:
                ok = False
                out = {"error": f"unknown tool {name}"}
        except Exception as e:
            ok = False
            out, error = {"error": str(e)}, str(e)
        dur_ms = (time.perf_counter() - start) * 1000.0
        self.events.append(
            {
                "tool": name,
                "args_keys": sorted(list(args.keys())),
                "ok": ok,
                "latency_ms": dur_ms,
                "error": error,
            }
        )
        return out


# Build messages for a case
def build_messages(system_text: str, user_text: str) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": system_text},
        {"role": "user", "content": user_text},
    ]


# Summarize tool usage across cases
def summarize(all_case_logs: List[Dict[str, Any]]):
    tools = ["flag_labs", "followup_gap", "umls_normalize"]
    totals = {t: {"should": 0, "used": 0, "ok": 0, "lat": []} for t in tools}

    for log in all_case_logs:
        should = log["should"]
        used = {e["tool"] for e in log["events"]}
        for t in tools:
            if should[t]:
                totals[t]["should"] += 1
            if t in used:
                totals[t]["used"] += 1
                # count ok and latency for events of t
                for e in log["events"]:
                    if e["tool"] == t:
                        if e["ok"]:
                            totals[t]["ok"] += 1
                            totals[t]["lat"].append(e["latency_ms"])

    # Print table
    print("\n=== Tool Use Evaluation ===")
    print(
        f"{'Tool':<16}{'Should':>8}{'Used':>8}{'Use%':>8}{'OK':>8}{'OK%':>8}{'p50 ms':>10}{'p95 ms':>10}"
    )
    for t in tools:
        sh = totals[t]["should"]
        us = totals[t]["used"]
        ok = totals[t]["ok"]
        p50 = statistics.median(totals[t]["lat"]) if totals[t]["lat"] else 0.0
        p95 = (
            sorted(totals[t]["lat"])[max(0, int(0.95 * len(totals[t]["lat"])) - 1)]
            if totals[t]["lat"]
            else 0.0
        )
        use_pct = (100.0 * us / sh) if sh else 0.0
        ok_pct = (100.0 * ok / us) if us else 0.0
        print(
            f"{t:<16}{sh:>8}{us:>8}{use_pct:>7.0f}%{ok:>8}{ok_pct:>7.0f}%{p50:>10.1f}{p95:>10.1f}"
        )


# Main tool evaluation pipeline
def run_tool_eval(eval_path: str):

    # Load cases
    cases = []
    with open(eval_path, "r") as f:
        for line in f:
            cases.append(json.loads(line))

    all_logs = []
    for i, case in enumerate(cases, 1):
        system = case["system"]
        user = case["user"]
        result_json = case["result_json"]
        messages = build_messages(system, user)

        # Heuristic expectations
        should = {
            "flag_labs": should_use_flag_labs(result_json),
            "followup_gap": should_use_followup_gap(result_json),
            "umls_normalize": should_use_umls(result_json),
        }

        # Log tool calls
        tlog = ToolLogger()
        results = []
        try:
            result = check_discharge_safety(
                messages=messages,
                chat=chat,
                MODEL=MODEL,
                TOOLS=TOOLS,
                tool_runner=tlog.runner,
            )
            results.append(result)
        except NotImplementedError:
            print("Replace chat() stub with your real API call.")
            return

        all_logs.append({"events": tlog.events, "should": should})

    # summarize tool use and print stats
    summarize(all_logs)
    return results
