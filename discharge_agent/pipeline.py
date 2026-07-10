"""End-to-end discharge pipeline: raw note -> extraction JSON -> agent decision.

This is the same flow as discharge_agent_example.ipynb, extracted into an
importable module so it can be run from the CLI (see discharge_agent/run.py)
and instrumented for tracing (see discharge_agent/tracing/instrumentation.py).
All LLM and tool logic is reused from the existing modules — nothing is
reimplemented here.
"""

import json
import os

import pandas as pd
from dotenv import load_dotenv

from discharge_agent.extractions.extraction import extract_clinical_information
from discharge_agent.llm.prompts import get_messages
from discharge_agent.llm.tool_specs import TOOLS
from discharge_agent.pipelines.discharge_checker import chat, check_discharge_safety
from discharge_agent.tools.followup import followup_gap
from discharge_agent.tools.labs import flag_labs
from discharge_agent.tools.umls_client import normalize_terms_to_cui

load_dotenv()

MODEL = os.getenv("MODEL", "gpt-oss:20b")

DEFAULT_NOTE_PATHS = [
    "data/synthetic_notes.csv",
    "data/synthetic_notes_extended.csv",
]


def run_tool(name: str, args: dict) -> dict:
    """Plain tool dispatch, mirroring the default branch in
    check_discharge_safety. Extracted so tracing can wrap it via the
    existing tool_runner hook."""
    try:
        if name == "flag_labs":
            return flag_labs(**args)
        elif name == "followup_gap":
            return followup_gap(**args)
        elif name == "umls_normalize":
            return normalize_terms_to_cui(**args)
        return {"error": f"unknown tool {name}"}
    except Exception as e:
        return {"error": str(e)}


def load_notes(paths=None) -> pd.DataFrame:
    """Load synthetic notes (noteid, note_type, note_text, main_diagnosis).
    Missing files are skipped so the pipeline works before the extended
    dataset exists."""
    frames = []
    for p in paths or DEFAULT_NOTE_PATHS:
        if os.path.exists(p):
            frames.append(pd.read_csv(p))
    if not frames:
        raise FileNotFoundError(f"no note files found in {paths or DEFAULT_NOTE_PATHS}")
    return pd.concat(frames, ignore_index=True)


def run_note(
    note_text: str,
    note_id=None,
    model: str = None,
    chat_fn=None,
    tool_runner=None,
    max_retries: int = 3,
) -> dict:
    """Run one note end-to-end.

    chat_fn: (payload) -> full Ollama response dict; defaults to the plain
             discharge_checker.chat. Tracing injects a wrapped version.
    tool_runner: (name, args) -> result dict; defaults to run_tool.
    """
    model = model or MODEL

    # 1. Extraction, with the same JSON-validity retry loop the notebook used
    result_json = None
    last_error = None
    for _ in range(max_retries):
        raw = extract_clinical_information(note_text, chat_fn=chat_fn, model=model)
        try:
            result_json = json.loads(raw)
            break
        except Exception as e:
            last_error = str(e)
    if result_json is None:
        return {
            "note_id": note_id,
            "extraction": None,
            "decision_raw": None,
            "decision": None,
            "error": f"extraction produced invalid JSON after {max_retries} tries: {last_error}",
        }

    # 2. Agent loop over the extracted JSON
    messages = get_messages(result_json)
    final = check_discharge_safety(
        messages=messages,
        chat=chat_fn or chat,
        MODEL=model,
        TOOLS=TOOLS,
        tool_runner=tool_runner or run_tool,
    )

    decision = None
    try:
        decision = json.loads(final)
    except Exception:
        pass

    return {
        "note_id": note_id,
        "extraction": result_json,
        "decision_raw": final,
        "decision": decision,
    }
