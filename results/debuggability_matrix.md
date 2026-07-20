# Experiment B: debugging with redacted traces only

Setup: all tasks attempted using ONLY the exported redacted traces
(`results/traces/` = redaction on, placeholder policy v1; `results/traces_v2/`
= policy v2 with date-shift surrogates) via `python -m experiments.run_debuggability`
and the Langfuse UI. No source notes were consulted. Model: gpt-oss:20b;
task specimens drawn from the original notes, leak counts from the full
40-note dataset. Grades: PASS / DEGRADED / FAIL.

| # | Task | v1 (placeholders) | v2 (policy + surrogates) |
|---|---|---|---|
| 1 | Tool called with plausible args? | **PASS** | **PASS** |
| 2 | Diagnose a tool skip (why?) | **PASS** | **PASS** |
| 3 | Trace a lab value note → extraction → tool | **PASS** (with a caveat) | **PASS** |
| 4 | Verify a followup_gap computation | **FAIL** | **PASS** |
| 5 | Reconstruct tokens + latency per stage | **PASS** | **PASS** |

## Task 1 — Did the agent call `flag_labs` on note 1, with plausible arguments? — PASS

The `execute_tool flag_labs` span is present with input shape
`{"labs": list[10] of {date: <DATE_14>, name: "WBC", value: "8.9"}}`. Structural
redaction (keys and shape preserved, values masked only when they are PHI) means
the *shape* of the call — 10 labs, each with name/value/date — is fully visible,
and since lab names and values are not PHI, even plausibility of the values can
be checked. Only the dates are placeholders, which doesn't affect this task.

## Task 2 — A note where a tool was skipped: can we tell WHY? — PASS

Specimen: note 6 re-run with the post-#4 "soft" v0 prompt
(`results/traces/note_6_v0_skip.json`). The redacted trace shows: (a) the
extraction output *contains* the abnormal labs — `Creatinine 1.8`, `BUN 45`
with masked dates — so the information was available; (b) generation 0 returns
**no** `flag_labs` tool call, and the final answer asserts "Abnormal kidney
function labs (Creatinine 1.8, BUN 45)" — the model did the abnormality
judgement itself instead of calling the tool. That is exactly the post-#4
distinction (info missing vs. model chose not to call), and it survives
redaction because lab names/values pass through unmasked.

## Task 3 — Trace WBC 12.5 from note → extraction → tool input → output — PASS (caveat under v1)

The value `12.5` is findable in every hop (raw-note payload inside the
extraction prompt, extraction JSON, `flag_labs` input). The handoff predicted
"partially broken if values are redacted" — but lab *values* are not PHI, so
the chain holds. Caveat under v1: correlating *which day's* WBC you are looking
at depends on placeholders; consistent indexing (`<DATE_14>` = same date
everywhere in the trace) lets you correlate two mentions of the same date, but
you cannot recover which calendar date it was. v1 also masked dates
*inconsistently* (one `03/15` became `<DATE_18>` in the model's reasoning while
another `03/15` two lines later survived) — see leak counts below.

## Task 4 — Verify `followup_gap` when the dates it needs are masked — FAIL → PASS

v1: input is `{"appts": [{"date": "<DATE_16>", ...}], "discharge_date": "<DATE_14>"}`,
output `{"days_to_earliest_followup": 7}`. There is no way to check the
arithmetic; if the tool mis-parsed a date you could not tell from the trace.
This is the designed collision between redaction and debuggability. **FAIL.**

v2 (date-shift surrogates, one random offset per trace): input becomes
`{"appts": [{"date": "2023-04-06", ...}], "discharge_date": "2023-03-30"}` →
7 days, matching the output exactly (note 6: 09/04 → 09/11 = 7, min over two
appts also checks out). Absolute dates are protected (shifted by an undisclosed
per-trace offset), intervals survive, the computation is verifiable. **PASS.**

## Task 5 — Reconstruct token cost and latency per stage — PASS

Usage and latency live in span metadata, which the masker never touches
(numbers pass through by design). For note 1: extraction 1,237→1,828 tokens /
43.9s, three agent-loop generations, tool latencies 0.01–0.78s, total
6,641 in / 2,825 out. Identical fidelity with redaction on or off.

## Bonus finding — anomaly diagnosis works on redacted traces

Note 8's redacted trace shows `flag_labs` called twice in successive
generations. The redacted payloads are sufficient to see the second call
carried a different (larger) labs list — the model split the labs across two
calls. Diagnosing this required only call shapes, not PHI.

## Leak reality check (plumbing vs. detection)

Boundary-aware grep of every ground-truth PHI string against the exported
redacted traces, full 40-note dataset:
- v1 (placeholders): **135 leaks** — 98 dates (bare `m/d` and month-name
  forms spaCy never detects), 13 provider names, 11 addresses, 9 patient
  names (incl. full all-caps header names with eponym surnames:
  `CROHN, DOROTHY`, `BELL, DAVID`, `HODGKIN, LISA`), 4 DOBs.
- v2 (policy + structural recognizers): **17 leaks** — zero dates,
  8 addresses/facility names (the category the fix iteration deliberately
  did not address), 8 provider names, 1 bare first name. Half the provider
  leaks were detected correctly in the raw note but leaked from
  LLM-transformed payloads (extraction JSON, model reasoning) — NER has to
  re-detect the same string in every payload shape; the rest are the
  `Firstname Eponym, NP` pattern with no "Dr." cue.

The masking *pipeline* (Langfuse `mask` callback → exporter) leaked nothing
that the analyzer detected; every leak is a detection miss, not a plumbing
failure. (The leak checker itself needed word-boundary matching — substring
grep matched "Apr 2" inside the shifted surrogate "Apr 23, 2023" and
reported phantom leaks.)
