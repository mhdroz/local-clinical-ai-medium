# Agent tracing + PHI redaction: experiment summary

Companion results for blog post #5. Setup: the existing discharge agent
(gpt-oss:20b via Ollama, three tools) instrumented with self-hosted Langfuse
(Docker, localhost-only) and an in-process Presidio masking layer wired into
the Langfuse SDK's `mask` callback — unredacted PHI never leaves the agent
process; the local model always sees the full note, only telemetry is masked.

## What we measured

- **A. Redaction quality** — per-PHI-category recall/precision of the masking
  analyzer against exact ground-truth spans (`experiments/run_redaction_eval.py`),
  plus an end-to-end leak check grepping every ground-truth string against the
  exported redacted traces.
- **B. Debuggability** — five concrete debugging tasks attempted using only
  redacted traces (`results/debuggability_matrix.md`).
- **C. Fix iteration** — a redaction policy built from A+B's failures, then
  re-measured (`results/iteration_comparison.md`).

Current numbers are on the 10 original synthetic notes (182 ground-truth
entities). The 30 adversarial notes (eponym surnames, varied date/MRN formats)
are generated via `experiments/generation_prompt.md` + `ingest_skeletons.py`;
all experiments re-run unchanged once `data/synthetic_notes_extended.csv`
exists.

## Headline numbers (notes 1-10)

| PHI category | GT | recall base → v2 |
|---|---|---|
| Patient name | 22 | 0.955 → 0.955 |
| Provider name | 23 | 1.000 → 1.000 |
| DOB | 10 | 1.000 → 1.000 |
| Dates | 103 | **0.398 → 1.000** |
| Phone | 10 | 1.000 → 1.000 |
| Address | 14 | **0.357 → 0.357** |
| MRN (custom recognizer) | 10 | 1.000 → 1.000 |

False positives 139 → 41; typed precision 0.51 → 0.83. Trace-level leaks
73 → 2 (both remaining leaks are addresses).

Debuggability: 4/5 tasks PASS under naive placeholder masking; the one FAIL
(verifying date arithmetic in `followup_gap`) flips to PASS with per-trace
date-shift surrogates.

## The surprises (what the post is actually about)

1. **NER misses the easiest PHI in the note.** spaCy/Presidio caught every
   phone number and DOB but missed `Name: BROWN, DOROTHY MAE` — a full patient
   name in a fixed header — and half the lab dates (`03/15:`). Detection is
   *contextual and inconsistent*: the same `03/15` was masked in one sentence
   and leaked two lines later. The fix wasn't a better model but *structure*:
   two 10-line regex recognizers keyed to the note template took date recall
   from 0.40 to 1.00.
2. **Off-the-shelf Presidio over-redacts clinical text into noise.** 126 of
   139 baseline false positives were DATE_TIME hits on ages ("72-year-old"),
   durations ("x3 days"), med frequencies ("daily"), and clock times — none of
   which are Safe-Harbor identifiers. Clinical-sign eponyms (Kussmaul,
   Charcot) and drug names (Insulin lispro, Glipizide) were flagged as PERSON.
   An allowlist must be *context-anchored*, not term-based: "Parkinson's
   disease" stays readable while a patient named Parkinson is still masked —
   naive substring allowlisting would leak the patient.
3. **Structural masking preserves most debugging.** Masking argument *values*
   while keeping keys and shapes intact meant tool-use debugging (the post-#4
   methodology) survived redaction almost entirely — including diagnosing a
   deliberately reproduced tool-skip, because lab names/values aren't PHI.
4. **Dates are the genuine collision — and surrogates dissolve it.** The
   follow-up-gap tool is date arithmetic; placeholders make its traces
   unverifiable. Replacing detected dates with per-trace date-shifted
   surrogates (one random offset per trace, stored in the same registry that
   keeps `<PERSON_1>` consistent) preserves every interval while hiding every
   absolute date. FAIL → PASS.
5. **Every leak was a detection miss, not a plumbing failure.** The `mask`
   callback boundary held: nothing the analyzer detected reached the exporter
   unmasked. The weak link in "redact your traces" is not the wiring, it's the
   recognizer.
6. **Silent trace loss is real.** Midway through, another dev server bound
   `*:3000` (IPv6) and shadowed `localhost:3000`; the OTel exporter dropped
   whole traces without any error surfacing in the pipeline. Pin the host
   (`127.0.0.1`) and check trace counts — observability infrastructure fails
   silently too.

## Honest limitations

- Synthetic data, 10 notes evaluated so far (40 when the adversarial set
  lands); single redaction engine (Presidio + en_core_web_lg); single model
  (gpt-oss:20b); local-only single-user Langfuse.
- The MRN recognizer shares regex definitions with the data generator — MRN
  recall of 1.0 is best-case by construction. Real deployments discover their
  ID formats the hard way.
- Address detection was left broken deliberately (0.36 recall) — fixing it
  needs a dedicated address recognizer and is out of scope.
- Grading of Experiment B is human judgement on defined tasks, not automated
  scoring. LLM-as-judge over traces is the next post; the hooks are the
  exported trace JSONs in `results/traces*/` and the Langfuse datasets API.

## Reproduce

```bash
docker compose -f docker/langfuse/docker-compose.yml up -d
pip install -r requirements.txt && python -m spacy download en_core_web_lg
python -m experiments.run_all_notes --redaction off        # baseline traces
python -m experiments.run_all_notes --redaction on         # masked traces
python -m experiments.run_redaction_eval                   # Experiment A
python -m experiments.run_redaction_eval --policy v2       # Experiment C
python -m experiments.run_iteration_comparison
python -m experiments.fetch_traces --tag redaction:on --out results/traces
python -m experiments.run_debuggability --traces results/traces --task 1
python -m experiments.run_redaction_eval --leak-check results/traces
```
