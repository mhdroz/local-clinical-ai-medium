# Redaction metrics (policy: none)

40 notes, score threshold 0.35. Matching: char overlap. `recall (typed)` requires a compatible entity type; `recall (masked at all)` counts any overlapping detection — wrong label but still masked.

| PHI category | ground truth | recall (typed) | recall (masked at all) |
|---|---|---|---|
| PATIENT_NAME | 76 | 0.842 | 0.895 |
| PROVIDER_NAME | 117 | 0.974 | 0.974 |
| DOB | 40 | 0.9 | 0.9 |
| DATE | 389 | 0.787 | 0.81 |
| PHONE | 46 | 1.0 | 1.0 |
| ADDRESS | 44 | 0.795 | 0.818 |
| MRN | 40 | 1.0 | 1.0 |

**False positives:** 376 total — {"DATE_TIME": 304, "LOCATION": 11, "PERSON": 60, "PHONE_NUMBER": 1}. Overall typed precision: 0.648. Every FP is listed in redaction_false_positives.md.
