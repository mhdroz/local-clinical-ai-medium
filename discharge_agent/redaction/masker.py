"""In-process PHI masking for Langfuse trace payloads.

Wired in as the Langfuse client's `mask` callback, so every span input/output/
metadata passes through here BEFORE it reaches the SDK exporter — unmasked PHI
never leaves the agent process. (Verified against langfuse 4.13.2: the mask is
applied synchronously in span.update()/creation on the caller's thread, not on
the background flush thread — which is what makes the contextvar trace scope
below work.)

Placeholders are typed and indexed: <PERSON_1>, <DATE_2>, <MRN_1>. The index
registry lives in a contextvars.ContextVar that the tracing layer resets per
note (begin_trace_scope/end_trace_scope), so:
  - the same surface string always maps to the same placeholder within a trace
    ("<PERSON_1> was discharged... <PERSON_1> should follow up"), and
  - counters restart for each new trace.

Structural redaction: dict KEYS are preserved verbatim, only values are masked.
A tool-call span keeps its argument shape ({"discharge_date": "<DATE_3>"}) so
you can still see WHAT call the agent made, just not the identifying values.

Fail-closed: if mask() is ever invoked outside a trace scope, a throwaway
registry is used — redaction still happens, only cross-span index consistency
is lost.
"""

import threading
from collections import defaultdict
from contextvars import ContextVar

from discharge_agent.redaction.recognizers import DEFAULT_ENTITIES, build_analyzer

# Presidio entity -> placeholder label
PLACEHOLDER_LABELS = {
    "PERSON": "PERSON",
    "DATE_TIME": "DATE",
    "PHONE_NUMBER": "PHONE",
    "LOCATION": "LOCATION",
    "EMAIL_ADDRESS": "EMAIL",
    "US_SSN": "SSN",
    "MRN": "MRN",
}

SCORE_THRESHOLD = 0.35

_registry: ContextVar = ContextVar("phi_placeholder_registry", default=None)


def _new_registry():
    return {"map": {}, "counters": defaultdict(int)}


def begin_trace_scope():
    """Start a fresh placeholder registry for one trace. Returns a token for
    end_trace_scope. Called by tracing.instrumentation.traced_run_note."""
    return _registry.set(_new_registry())


def end_trace_scope(token):
    _registry.reset(token)


class TraceMasker:
    def __init__(self, analyzer=None, policy=None):
        self._analyzer = analyzer
        self._policy = policy
        self._analyzer_lock = threading.Lock()

    @property
    def analyzer(self):
        if self._analyzer is None:
            with self._analyzer_lock:
                if self._analyzer is None:
                    self._analyzer = build_analyzer()
        return self._analyzer

    # -- Langfuse calls this: mask(data=...) --------------------------------
    def mask(self, *, data):
        return self._mask_value(data)

    def _mask_value(self, obj):
        if isinstance(obj, str):
            return self._mask_text(obj)
        if isinstance(obj, dict):
            # keys preserved: structural redaction
            return {k: self._mask_value(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            masked = [self._mask_value(v) for v in obj]
            return type(obj)(masked) if isinstance(obj, tuple) else masked
        # numbers / bools / None pass through — token counts, latencies and
        # flags are exactly what must survive for debugging
        return obj

    def _mask_text(self, text: str) -> str:
        if not text:
            return text
        results = self.analyzer.analyze(
            text=text,
            language="en",
            entities=DEFAULT_ENTITIES,
            score_threshold=SCORE_THRESHOLD,
        )
        if self._policy is not None:
            results = self._policy.filter_results(text, results)

        # resolve overlaps: highest score wins, then longest span
        accepted = []
        for r in sorted(results, key=lambda r: (-r.score, -(r.end - r.start))):
            if all(r.end <= a.start or r.start >= a.end for a in accepted):
                accepted.append(r)

        # replace right-to-left so offsets stay valid
        out = text
        for r in sorted(accepted, key=lambda r: r.start, reverse=True):
            replacement = self._replacement_for(out[r.start : r.end], r)
            out = out[: r.start] + replacement + out[r.end :]
        return out

    def _replacement_for(self, matched_text: str, result) -> str:
        if self._policy is not None:
            surrogate = self._policy.surrogate_for(matched_text, result)
            if surrogate is not None:
                return surrogate
        label = PLACEHOLDER_LABELS.get(result.entity_type, result.entity_type)
        return self._placeholder(label, matched_text)

    def _placeholder(self, label: str, matched_text: str) -> str:
        reg = _registry.get()
        if reg is None:  # outside a trace scope: fail closed, still redact
            reg = _new_registry()
        key = (label, " ".join(matched_text.upper().split()))
        if key not in reg["map"]:
            reg["counters"][label] += 1
            reg["map"][key] = f"<{label}_{reg['counters'][label]}>"
        return reg["map"][key]


_default_masker = None
_masker_lock = threading.Lock()


def get_masker(policy=None) -> TraceMasker:
    """Shared TraceMasker (the spaCy model is ~600MB — load it once).
    Passing a policy returns a NEW masker wired to that policy but reusing
    the shared analyzer."""
    global _default_masker
    with _masker_lock:
        if _default_masker is None:
            _default_masker = TraceMasker()
        if policy is not None:
            return TraceMasker(analyzer=_default_masker.analyzer, policy=policy)
        return _default_masker
