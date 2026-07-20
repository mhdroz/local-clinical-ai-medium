# Redaction metrics (policy: v2)

40 notes, score threshold 0.35. Matching: char overlap. `recall (typed)` requires a compatible entity type; `recall (masked at all)` counts any overlapping detection — wrong label but still masked.

| PHI category | ground truth | recall (typed) | recall (masked at all) |
|---|---|---|---|
| PATIENT_NAME | 76 | 0.987 | 0.987 |
| PROVIDER_NAME | 117 | 0.974 | 0.974 |
| DOB | 40 | 1.0 | 1.0 |
| DATE | 389 | 1.0 | 1.0 |
| PHONE | 46 | 1.0 | 1.0 |
| ADDRESS | 44 | 0.795 | 0.818 |
| MRN | 40 | 1.0 | 1.0 |

**False positives:** 104 total — {"LOCATION": 4, "DATE_TIME": 88, "PERSON": 11, "PHONE_NUMBER": 1}. Overall typed precision: 0.884. Every FP is listed in redaction_false_positives_v2.md.
