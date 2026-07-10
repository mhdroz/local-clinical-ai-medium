# Redaction metrics (policy: v2)

10 notes, score threshold 0.35. Matching: char overlap. `recall (typed)` requires a compatible entity type; `recall (masked at all)` counts any overlapping detection — wrong label but still masked.

| PHI category | ground truth | recall (typed) | recall (masked at all) |
|---|---|---|---|
| PATIENT_NAME | 22 | 0.955 | 0.955 |
| PROVIDER_NAME | 23 | 1.0 | 1.0 |
| DOB | 10 | 1.0 | 1.0 |
| DATE | 103 | 1.0 | 1.0 |
| PHONE | 10 | 1.0 | 1.0 |
| ADDRESS | 14 | 0.357 | 0.429 |
| MRN | 10 | 1.0 | 1.0 |

**False positives:** 41 total — {"DATE_TIME": 39, "PHONE_NUMBER": 1, "PERSON": 1}. Overall typed precision: 0.835. Every FP is listed in redaction_false_positives_v2.md.
