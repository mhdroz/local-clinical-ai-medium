"""Langfuse instrumentation for the discharge pipeline.

Everything here is a wrapper around the pipeline's existing injection points
(the `chat_fn` and `tool_runner` parameters) — check_discharge_safety and the
tools are not modified.

Span layout per note:

    invoke_agent note_<id>            (root, as_type="agent")
      ollama.chat                     (as_type="generation", extraction call)
      ollama.chat                     (agent-loop calls, one per LLM round)
      execute_tool flag_labs          (as_type="tool")
      execute_tool followup_gap
      ...

When redaction is on, the Langfuse client is constructed with a `mask`
callback (redaction.masker.TraceMasker) — payloads are masked in-process,
before they are handed to the SDK's exporter. The Ollama model itself always
sees the raw note; only the telemetry is masked.
"""

import os

from dotenv import load_dotenv
from langfuse import Langfuse, propagate_attributes

from discharge_agent import pipeline
from discharge_agent.pipelines.discharge_checker import chat

load_dotenv()

_clients = {}


def get_langfuse(redaction: bool = False) -> Langfuse:
    """One client per redaction mode. The mask callback is the redaction
    boundary: with redaction on, unmasked PHI never reaches the exporter."""
    key = "on" if redaction else "off"
    if key not in _clients:
        mask = None
        if redaction:
            # Lazy import: loads spaCy/Presidio only when actually redacting.
            from discharge_agent.redaction.masker import get_masker

            mask = get_masker().mask
        _clients[key] = Langfuse(
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
            host=os.getenv("LANGFUSE_HOST", "http://localhost:3000"),
            mask=mask,
        )
    return _clients[key]


def traced_chat(langfuse: Langfuse, base_chat=chat):
    """Wrap the raw Ollama chat function in a generation observation.

    Ollama's /api/chat response carries token counts as prompt_eval_count /
    eval_count; prompt_eval_count can be absent on full KV-cache hits, so
    missing counts are simply omitted rather than reported as 0.
    """

    def _chat(payload):
        with langfuse.start_as_current_observation(
            name="ollama.chat",
            as_type="generation",
            model=payload.get("model"),
            input=payload.get("messages"),
            metadata={"has_tools": "tools" in payload},
        ) as gen:
            resp = base_chat(payload)
            usage = {}
            if resp.get("prompt_eval_count") is not None:
                usage["input"] = resp["prompt_eval_count"]
            if resp.get("eval_count") is not None:
                usage["output"] = resp["eval_count"]
            gen.update(
                output=resp.get("message"),
                usage_details=usage or None,
                metadata={
                    "total_duration_ms": resp.get("total_duration", 0) / 1e6,
                    "eval_duration_ms": resp.get("eval_duration", 0) / 1e6,
                },
            )
            return resp

    return _chat


def traced_tool_runner(langfuse: Langfuse, inner=pipeline.run_tool):
    """Wrap tool dispatch in a tool observation (name: execute_tool <tool>)."""

    def _runner(name, args):
        with langfuse.start_as_current_observation(
            name=f"execute_tool {name}",
            as_type="tool",
            input=args,
        ) as span:
            result = inner(name, args)
            is_error = isinstance(result, dict) and "error" in result
            span.update(
                output=result,
                level="ERROR" if is_error else None,
                status_message=result.get("error") if is_error else None,
            )
            return result

    return _runner


def traced_run_note(note_text, note_id=None, model=None, redaction=False, **kwargs):
    """Run pipeline.run_note under a root `invoke_agent` span.

    With redaction on, brackets the run with the masker's per-trace scope so
    placeholder indices (<PERSON_1>, <DATE_2>, ...) are consistent within a
    trace and reset between traces.
    """
    langfuse = get_langfuse(redaction=redaction)
    model = model or pipeline.MODEL

    scope_token = None
    if redaction:
        from discharge_agent.redaction.masker import begin_trace_scope

        scope_token = begin_trace_scope()

    try:
        with langfuse.start_as_current_observation(
            name="invoke_agent", as_type="agent", input={"note_id": note_id}
        ) as root, propagate_attributes(
            trace_name=f"invoke_agent note_{note_id}",
            metadata={
                "note_id": str(note_id),
                "model": model,
                "pipeline_version": os.getenv("PIPELINE_VERSION", "0.2.0"),
                "redaction": "on" if redaction else "off",
            },
            tags=[f"redaction:{'on' if redaction else 'off'}", f"note:{note_id}"],
            version=os.getenv("PIPELINE_VERSION", "0.2.0"),
        ):
            out = pipeline.run_note(
                note_text,
                note_id=note_id,
                model=model,
                chat_fn=traced_chat(langfuse),
                tool_runner=traced_tool_runner(langfuse),
                **kwargs,
            )
            root.update(output=out.get("decision") or out.get("error"))
            return out
    finally:
        if scope_token is not None:
            from discharge_agent.redaction.masker import end_trace_scope

            end_trace_scope(scope_token)
