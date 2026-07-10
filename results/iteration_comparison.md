# Redaction fix iteration: baseline vs policy v2

Notes evaluated: 10 (baseline) / 10 (v2). Matching: char-overlap; typed = compatible entity type, any = any type.

Policy v2 = clinical-eponym allowlist + benign-date filters (ages, durations,
frequencies, clock times, pain/strength scores) + structural recognizers
(header names, bare m/d dates) + per-trace date-shift surrogates.

| PHI category | GT count | recall (typed) base → v2 | recall (masked at all) base → v2 |
|---|---|---|---|
| PATIENT_NAME | 22 | 0.955 → **0.955** | 0.955 → **0.955** |
| PROVIDER_NAME | 23 | 1.000 → **1.000** | 1.000 → **1.000** |
| DOB | 10 | 1.000 → **1.000** | 1.000 → **1.000** |
| DATE | 103 | 0.398 → **1.000** | 0.485 → **1.000** |
| PHONE | 10 | 1.000 → **1.000** | 1.000 → **1.000** |
| ADDRESS | 14 | 0.357 → **0.357** | 0.429 → **0.429** |
| MRN | 10 | 1.000 → **1.000** | 1.000 → **1.000** |

| overall | baseline | policy v2 |
|---|---|---|
| false positives | 139 | **41** |
| precision (typed) | 0.511 | **0.835** |
| type-mismatched masks | 12 | 12 |

Notes:
- The DATE recall jump comes almost entirely from the bare-`m/d` structural
  recognizer — spaCy's DATE_TIME simply does not see `03/15:`-style lab dates.
- ADDRESS recall is essentially unchanged: street addresses are a known
  Presidio/spaCy weak spot and would need a dedicated address recognizer
  (out of scope for this iteration; kept as an honest limitation).
- Date-shift surrogates do not change detection metrics; their effect shows
  in the debuggability matrix (interval arithmetic survives redaction).
- Residual date ambiguity: `9/10` (pain) vs `09/10` (Sept 10) cannot be
  resolved by pattern alone; the policy keeps unpadded pain scores visible.
