# Redaction fix iteration: baseline vs policy v2

Notes evaluated: 40 (baseline) / 40 (v2). Matching: char-overlap; typed = compatible entity type, any = any type.

Policy v2 = clinical-eponym allowlist + benign-date filters (ages, durations,
frequencies, clock times, pain/strength scores) + structural recognizers
(header names, bare m/d dates) + per-trace date-shift surrogates.

| PHI category | GT count | recall (typed) base → v2 | recall (masked at all) base → v2 |
|---|---|---|---|
| PATIENT_NAME | 76 | 0.842 → **0.987** | 0.895 → **0.987** |
| PROVIDER_NAME | 117 | 0.974 → **0.974** | 0.974 → **0.974** |
| DOB | 40 | 0.900 → **1.000** | 0.900 → **1.000** |
| DATE | 389 | 0.787 → **1.000** | 0.810 → **1.000** |
| PHONE | 46 | 1.000 → **1.000** | 1.000 → **1.000** |
| ADDRESS | 44 | 0.795 → **0.795** | 0.818 → **0.818** |
| MRN | 40 | 1.000 → **1.000** | 1.000 → **1.000** |

| overall | baseline | policy v2 |
|---|---|---|
| false positives | 376 | **104** |
| precision (typed) | 0.648 | **0.884** |
| type-mismatched masks | 56 | 56 |

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
