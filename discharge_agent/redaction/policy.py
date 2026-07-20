"""Redaction policy v2 — the Phase 4C fix iteration.

Built from Experiment A's false-positive log and Experiment B's failures:

1. Clinical allowlist: eponym disease terms ("Parkinson's disease", "Cushing
   syndrome"), clinical-sign eponyms ("Kussmaul", "Charcot"), drug names, and
   clinical abbreviations that Presidio's NER flags as PERSON/LOCATION.
   IMPORTANT: allowlisting is term-based, not surname-based — "Parkinson's
   disease" stays, a patient named Parkinson is still masked.

2. Benign-pattern filters for DATE_TIME noise: ages ("72-year-old"), durations
   ("x3 days", ">24h"), frequencies ("daily", "BID"), and clock times — these
   aren't Safe-Harbor PHI, and masking them wrecks clinical readability.

3. Date surrogates instead of placeholders: every parseable DATE_TIME hit is
   shifted by a per-trace random offset (stored in the masker's trace scope, so
   one trace = one offset). Intervals between dates survive, so follow-up-gap
   logic remains debuggable, while absolute dates stay protected. Unparseable
   relative phrases fall back to placeholders.
"""

import re
from dataclasses import dataclass, field
from datetime import timedelta

from dateutil import parser as dtparser

# ---------------------------------------------------------------- allowlist

# Terms that are clinical vocabulary, not identifiers. Seeded from
# experiments/phi_values.EPONYM_CLINICAL_TERMS + Experiment A's FP log.
CLINICAL_ALLOWLIST = {
    # eponymous diseases/procedures (also in the adversarial generator)
    "parkinson's disease", "parkinsonian gait", "cushing syndrome",
    "cushingoid features", "addison's disease", "addisonian crisis",
    "hodgkin lymphoma", "non-hodgkin lymphoma", "graves' disease",
    "crohn's disease", "wilson's disease", "huntington's disease",
    "barrett's esophagus", "paget's disease", "whipple procedure",
    "bell's palsy", "sweet syndrome",
    # clinical-sign eponyms flagged as PERSON on the original notes
    "kussmaul", "charcot", "charcot's triad", "babinski", "homans",
    # drug names flagged as PERSON
    "insulin lispro", "insulin glargine", "glipizide", "lispro", "glargine",
    # clinical abbreviations flagged as PERSON/LOCATION
    "mm", "ed", "snf", "aki", "us", "pt", "ot", "cholelithiasis", "neurology",
}

# DATE_TIME detections matching these are noise, not dates
BENIGN_DATE_PATTERNS = [
    re.compile(r"^\d{1,3}[- ]?year[- ]?old\b", re.I),  # ages
    re.compile(r"^(?:x\s?)?\d+\s?(?:days?|weeks?|months?|years?|hours?|h)\b", re.I),
    re.compile(r"^>?\s?\d+\s?h\.?$", re.I),
    re.compile(r"^(?:daily|nightly|weekly|monthly|q\d|bid|tid|qid|qhs|prn)\b", re.I),
    re.compile(r"^\d{1,2}:\d{2}\s?(?:AM|PM)?$", re.I),  # clock times
    re.compile(r"^(?:day|days|week|weeks|month|months|year|years)$", re.I),
    re.compile(r"^age \d+", re.I),
    re.compile(r"^\d{4}$"),  # bare years ("quit 2020") — not Safe-Harbor PHI
    # pain scores ("8/10") / strength grades ("4/5") the m/d recognizer can't
    # distinguish from dates. No leading zero: clinicians write pain as 9/10,
    # dates in these notes as 09/10 — "9/10" on Sept 10 remains inherently
    # ambiguous and is discussed in the writeup.
    re.compile(r"^[1-9]?\d/5$|^(?:[1-9]|10)/10$"),
]

_HAS_MONTH_DAY = re.compile(
    r"\d{1,2}[/-]\d{1,2}|"                       # 03/15, 3-15
    r"\d{4}-\d{2}-\d{2}|"                        # ISO
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}",  # March 14
    re.I,
)


def _term_at_word_boundary(window: str, term: str) -> bool:
    if not window.startswith(term):
        return False
    rest = window[len(term) :]
    return not rest or not rest[0].isalnum()


def _match_term_raw(text_from_start: str, term: str):
    """Match an allowlisted term at the start of the raw detection window,
    case-insensitively, tolerating whitespace runs. Returns the match end
    offset in raw chars, or None."""
    pattern = re.escape(term).replace(r"\ ", r"\s+") + r"(?![A-Za-z0-9])"
    m = re.match(pattern, text_from_start, re.IGNORECASE)
    return m.end() if m else None


@dataclass
class RedactionPolicy:
    allowlist: set = field(default_factory=lambda: set(CLINICAL_ALLOWLIST))
    benign_date_patterns: list = field(default_factory=lambda: list(BENIGN_DATE_PATTERNS))
    date_surrogates: bool = True

    # -- hook 1: drop analyzer results that shouldn't be masked at all -------
    def filter_results(self, text, results):
        kept = []
        for r in results:
            span = text[r.start : r.end].strip()
            key = " ".join(span.lower().split())
            if key in self.allowlist:
                continue
            # Boundary drift: NER often flags just "Parkinson" inside
            # "Parkinson's disease" (keep the disease term readable) — or
            # merges a specialty into a name ("Neurology Margaret Bell").
            # Anchor allowlist terms at the detection start, at a word
            # boundary ("ed" may not swallow "EDward Wilson"):
            #   - term covers the whole detection -> drop it entirely
            #   - term covers a prefix -> TRIM it off and keep masking the
            #     rest, so "Neurology Margaret Bell" still masks the name.
            window = text[r.start : r.end + 24]
            for term in self.allowlist:
                end = _match_term_raw(window, term)
                if end is None:
                    continue
                if end >= (r.end - r.start):
                    r = None  # allowlisted term covers the detection
                    break
                trimmed_start = r.start + end
                while trimmed_start < r.end and not text[trimmed_start].isalnum():
                    trimmed_start += 1
                if trimmed_start < r.end:
                    r = type(r)(
                        entity_type=r.entity_type,
                        start=trimmed_start,
                        end=r.end,
                        score=r.score,
                    )
                break
            if r is None:
                continue
            span = text[r.start : r.end].strip()
            if r.entity_type == "DATE_TIME" and any(
                p.match(span) for p in self.benign_date_patterns
            ):
                # "...in 2 weeks" / "within one month": a duration used as an
                # appointment time. Keep it masked when the preceding words
                # say so; bare durations ("x3 days of abx") stay visible.
                if not re.search(r"(?:\bin|\bwithin)\s+$", text[: r.start], re.IGNORECASE):
                    continue
            kept.append(r)
        return kept

    # -- hook 2: replace with a surrogate instead of a placeholder -----------
    def surrogate_for(self, matched_text, result):
        """Date-shift surrogate for DATE_TIME hits; None -> placeholder."""
        if not self.date_surrogates or result.entity_type != "DATE_TIME":
            return None
        span = matched_text.strip()
        # only shift things that actually carry a month+day (a real date);
        # relative phrases ("in 2 weeks") keep the placeholder path
        if not _HAS_MONTH_DAY.search(span):
            return None
        try:
            d = dtparser.parse(span, fuzzy=False, default=dtparser.parse("2024-06-15"))
        except (ValueError, OverflowError):
            return None
        shifted = d - timedelta(days=self._trace_offset())
        # keep roughly the original rendering style
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", span):
            return shifted.strftime("%Y-%m-%d")
        if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", span):
            return shifted.strftime("%m/%d/%Y")
        if re.fullmatch(r"\d{1,2}/\d{1,2}", span):
            return shifted.strftime("%m/%d")
        return shifted.strftime("%b %d, %Y")

    def _trace_offset(self) -> int:
        """Per-trace day offset, stable within a trace scope (stored in the
        masker's contextvar registry), 90-450 days."""
        from discharge_agent.redaction import masker as m

        reg = m._registry.get()
        if reg is None:
            return 237  # fixed fallback outside a trace scope — still shifted
        if "date_offset" not in reg:
            # derive deterministically from registry identity so runs differ
            # but one trace is internally consistent
            reg["date_offset"] = 90 + (id(reg) % 361)
        return reg["date_offset"]


def clinical_policy_v2() -> RedactionPolicy:
    return RedactionPolicy()
