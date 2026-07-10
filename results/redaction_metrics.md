# Redaction metrics (policy: none)

10 notes, score threshold 0.35. Matching: char overlap. `recall (typed)` requires a compatible entity type; `recall (masked at all)` counts any overlapping detection — wrong label but still masked.

| PHI category | ground truth | recall (typed) | recall (masked at all) |
|---|---|---|---|
| PATIENT_NAME | 15 | 1.0 | 1.0 |
| PROVIDER_NAME | 23 | 1.0 | 1.0 |
| DOB | 10 | 1.0 | 1.0 |
| DATE | 103 | 0.398 | 0.485 |
| PHONE | 10 | 1.0 | 1.0 |
| ADDRESS | 11 | 0.273 | 0.364 |
| MRN | 10 | 1.0 | 1.0 |

**False positives:** 159 total — {"DATE_TIME": 126, "PERSON": 17, "PHONE_NUMBER": 10, "LOCATION": 6}. Overall typed precision: 0.413. Every FP is listed in redaction_false_positives.md.
