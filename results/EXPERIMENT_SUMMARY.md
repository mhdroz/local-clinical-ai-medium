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

Dataset: 40 notes — the 10 originals plus 30 adversarial notes (eponym
surnames colliding with clinical vocabulary, varied date/MRN/phone formats,
relative appointment dates) generated as placeholder skeletons in the Claude
interface (`experiments/generation_prompt.md`) and materialized by
`experiments/ingest_skeletons.py`, which injects PHI values programmatically —
ground truth (752 entities) is exact by construction, never hand-annotated
after the fact.

## Headline numbers (40 notes, 752 ground-truth entities)

| PHI category | GT | recall base → v2 |
|---|---|---|
| Patient name | 76 | **0.842 → 0.987** |
| Provider name | 117 | 0.974 → 0.974 |
| DOB | 40 | 0.900 → 1.000 |
| Dates | 389 | **0.787 → 1.000** |
| Phone | 46 | 1.000 → 1.000 |
| Address | 44 | **0.795 → 0.795** |
| MRN (custom recognizer) | 40 | 1.000 → 1.000 |

False positives 376 → 104; typed precision 0.648 → 0.884. End-to-end trace
leaks (boundary-aware grep of every ground-truth string against the exported
redacted traces, 40 traces per policy):
- **v1 (placeholders): 135 leaks** — 98 dates, 13 providers, 11 addresses,
  9 patient names, 4 DOBs. The leaked patient names are overwhelmingly the
  planted eponym surnames in all-caps headers (`CROHN, DOROTHY`,
  `BELL, DAVID`, `HODGKIN, LISA`) — spaCy misses these at a far higher rate
  than plain surnames.
- **v2 (policy + structural recognizers): 17 leaks** — zero dates,
  8 addresses (the deliberately unfixed category), 8 provider names, 1 bare
  first name. Half the provider leaks were *detected correctly in the raw
  note* but leaked from LLM-transformed payloads (extraction JSON, reasoning
  text) where the different context defeats NER — masking must re-detect in
  every payload shape, not once per note. The rest are the
  `Firstname Eponym, NP` pattern (no "Dr." cue), which spaCy misses even in
  the note itself.

Debuggability: 4/5 tasks PASS under naive placeholder masking; the one FAIL
(verifying date arithmetic in `followup_gap`) flips to PASS with per-trace
date-shift surrogates.

## The surprises (what the post is actually about)

1. **NER misses the easiest PHI in the note.** spaCy/Presidio caught every
   phone number and DOB but missed `Name: BROWN, DOROTHY MAE` — a full patient
   name in a fixed header — and a fifth of all dates (`03/15:` lab lines,
   `Jun 11` month-name forms). Detection is *contextual and inconsistent*:
   the same `03/15` was masked in one sentence and leaked two lines later,
   and names caught in the note still leaked from the extraction JSON where
   the surrounding context differs. The fix wasn't a better model but
   *structure*: a handful of regex recognizers keyed to the note template
   took date recall from 0.79 to 1.00 and patient names from 0.84 to 0.99.
2. **Eponym surnames are a measurably harder class.** With 30 adversarial
   notes planting patients and providers named Parkinson, Cushing, Crohn,
   Bell..., baseline patient-name recall dropped from 0.95 (original notes)
   to 0.84, and the baseline produced 60 PERSON false positives on clinical
   vocabulary. The allowlist that fixes the false positives must be
   **context-anchored with word boundaries** — three bugs we actually hit:
   the abbreviation `ed` (emergency department) swallowed "EDward Wilson";
   spaCy merged "Neurology Margaret Bell" into one span that a naive
   allowlist dropped entirely (leaking the name); and "Barrett's
   *surveillance*" / "Crohn's *flare*" show exact-phrase allowlists don't
   generalize — the long tail (Forrest IIa, drug-allergy lines) never ends.
3. **Off-the-shelf Presidio over-redacts clinical text into noise.** 304 of
   376 baseline false positives were DATE_TIME hits on ages ("72-year-old"),
   durations ("x3 days"), med frequencies ("daily"), and clock times — none of
   which are Safe-Harbor identifiers. Clinical-sign eponyms (Kussmaul,
   Charcot) and drug names (Insulin lispro, Glipizide) were flagged as PERSON.
   And the categories overlap: "in 2 weeks" is an appointment timing (mask it)
   while "x3 days of antibiotics" is a clinical duration (keep it) — the
   policy disambiguates on the preceding words, and "9/10" (pain score) vs
   "09/10" (September 10) remains genuinely undecidable by pattern.
4. **Structural masking preserves most debugging.** Masking argument *values*
   while keeping keys and shapes intact meant tool-use debugging (the post-#4
   methodology) survived redaction almost entirely — including diagnosing a
   deliberately reproduced tool-skip, because lab names/values aren't PHI.
5. **Dates are the genuine collision — and surrogates dissolve it.** The
   follow-up-gap tool is date arithmetic; placeholders make its traces
   unverifiable. Replacing detected dates with per-trace date-shifted
   surrogates (one random offset per trace, stored in the same registry that
   keeps `<PERSON_1>` consistent) preserves every interval while hiding every
   absolute date. FAIL → PASS. (Meta-lesson: the leak *checker* itself needed
   word-boundary matching — "Apr 2" matched inside the shifted surrogate
   "Apr 23, 2023" and reported phantom leaks.)
6. **Every leak was a detection miss, not a plumbing failure.** The `mask`
   callback boundary held: nothing the analyzer detected reached the exporter
   unmasked. The weak link in "redact your traces" is not the wiring, it's the
   recognizer — and detection must succeed independently in every payload
   shape (raw note, extraction JSON, model reasoning), because NER that
   catches a name in prose can miss the same name inside JSON.
7. **Silent trace loss is real.** Midway through, another dev server bound
   `*:3000` (IPv6) and shadowed `localhost:3000`; the OTel exporter dropped
   whole traces without any error surfacing in the pipeline. Pin the host
   (`127.0.0.1`) and check trace counts — observability infrastructure fails
   silently too. Separately, gpt-oss:20b under sustained sequential load
   intermittently returned 500s from Ollama (~8/40 notes per batch; all
   succeeded on retry) — batch runners need retries, and the traces make the
   failure point obvious.

## Honest limitations

- Synthetic data, 40 notes, 752 ground-truth entities; single redaction
  engine (Presidio + en_core_web_lg); single model (gpt-oss:20b); local-only
  single-user Langfuse.
- The MRN recognizer shares regex definitions with the data generator — MRN
  recall of 1.0 is best-case by construction. Real deployments discover their
  ID formats the hard way. The header-name recognizer similarly exploits the
  note template; unstructured narrative notes would not benefit.
- Address detection was left broken deliberately (0.80 recall at 40 notes,
  all 8 remaining v2 leaks of this type) — fixing it needs a dedicated
  address recognizer and is out of scope.
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
