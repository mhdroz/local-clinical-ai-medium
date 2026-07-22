# Skeleton generation prompt (paste into Claude)

**How to use:** paste everything below the line into a fresh Claude conversation.
Claude will produce 10 skeletons per response — reply "continue" twice to get all 30.
Save every JSON line (concatenated, in order) into `data/skeletons/skeletons.jsonl`,
then run:

```bash
python -m experiments.ingest_skeletons
```

The skeletons contain **no PHI at all** — only `{{PLACEHOLDER}}` tokens. The ingest
script injects synthetic PHI values programmatically and records exact ground-truth
spans, so nothing needs to be hand-annotated.

---

I'm building a test dataset of **synthetic hospital discharge summary skeletons** for a
PHI-redaction benchmark. Generate **30 skeletons**, output **10 per response** (I'll say
"continue" for the next batch).

## Output format (strict)

One JSON object per line (JSONL), inside a single code block, no commentary between lines:

```
{"skeleton_id": 11, "note_type": "Discharge Summary", "main_diagnosis": "<short diagnosis label>", "note_text": "<the full note with \n newlines>"}
```

`skeleton_id` runs 11–40 (11–20 in the first response, 21–30 in the second, 31–40 in the third).

## Note structure (house style — follow it closely)

Each note must have exactly these sections, in this order, in this style:

```
Name: {{PATIENT_NAME}}                Unit No: {{MRN}}
Admission Date: {{ADMIT_DATE}}        Discharge Date: {{DISCHARGE_DATE}}
Date of Birth: {{DOB}}        Sex: {{SEX}}
Service: MEDICINE
Allergies: <NKDA or a plausible drug allergy>
Attending: {{PROVIDER_1}}

Chief Complaint:
...

Major Surgical or Invasive Procedure:
...

History of Present Illness:
<age>-year-old {{SEX}} w/ h/o ... (clinical shorthand: SOB, CP, N/V, etc.)

Past Medical History:
1. ...

Social History:
<smoking/alcohol/living situation>. Lives at {{ADDRESS}}. <ADLs, occupation>.

Physical Exam:
ADMISSION:
VS: ...
<systems>

DISCHARGE:
VS: ...

Pertinent Results:
{{ADMIT_DATE}}: WBC 12.5 Hgb 13.2 Plt 245
{{ADMIT_DATE}}: Na 138 K 4.1 ... Cr 1.1 Glu 145
{{DISCHARGE_DATE}}: WBC 8.9 ...

Brief Hospital Course:
<narrative; mention at least one lab value IN PROSE, e.g. "creatinine peaked at 2.1
on {{ADMIT_DATE}} and recovered to 1.2 by discharge">

Medications on Admission:
1. ...

Discharge Medications:
1. ... (include at least one NEW medication or dose change vs. admission)

Discharge Disposition: Home | Home with services | Rehab

Discharge Diagnosis:
Primary: ...
Secondary: ...

Discharge Condition:
Mental Status: ...
Level of Consciousness: ...
Activity Status: ...

Discharge Instructions:
- ...
- Follow up with {{PROVIDER_2}} on {{APPT_DATE_1}}
- Return for <warning signs>

Followup Instructions:
{{PROVIDER_2}} - {{APPT_DATE_1}}
Phone: {{PHONE}}
```

## Placeholder rules (critical)

Use ONLY these placeholder tokens, exactly as written (double curly braces):

- `{{PATIENT_NAME}}` — once, in the Name: header line
- `{{PATIENT_REF}}` — a reference to the patient by honorific + surname in prose
  ("{{PATIENT_REF}} tolerated the procedure well"). Use in ~half the notes, 1–2 times,
  in History of Present Illness or Brief Hospital Course.
- `{{MRN}}` — once, after the label `Unit No:` — or vary the label across notes:
  `MRN:` or `Medical Record #:`
- `{{DOB}}`, `{{SEX}}` — header
- `{{ADMIT_DATE}}`, `{{DISCHARGE_DATE}}` — reuse freely wherever that date appears
  (header, lab result lines, prose)
- `{{APPT_DATE_1}}`, `{{APPT_DATE_2}}` — follow-up appointment dates
- `{{RELATIVE_DATE}}` — a follow-up expressed as a relative time ("Follow up with PCP
  {{RELATIVE_DATE}}"). Use in ~a third of the notes, sometimes INSTEAD of
  {{APPT_DATE_1}} so some notes have no absolute follow-up date at all.
- `{{PHONE}}`, `{{PHONE_2}}` — clinic phone numbers
- `{{ADDRESS}}` — once, in Social History
- `{{PROVIDER_1}}`, `{{PROVIDER_2}}`, `{{PROVIDER_3}}` — attending, follow-up
  provider(s), consultants. Reuse the same token for the same person.

Never invent names, dates, phone numbers, addresses, or record numbers — if it
identifies someone, it must be a placeholder. Ages, lab values, medications, and
vital signs are fine as literals.

## Clinical content requirements

1. **30 different primary diagnoses**, common inpatient medicine: CAP, CHF exacerbation,
   COPD exacerbation, upper GI bleed, DKA, cellulitis, pyelonephritis, PE, AFib with RVR,
   hip fracture s/p ORIF, acute pancreatitis, ischemic stroke, AKI, hyponatremia,
   C. diff colitis, etc.
2. **Labs must appear both in the structured "Pertinent Results" list AND at least one
   value woven into the Brief Hospital Course prose.** Include some abnormal values
   consistent with the diagnosis.
3. **Eponym traps:** in at least 12 of the 30 notes, the clinical text must use one or
   more of these disease/procedure terms (as genuine clinical content, e.g. in PMH or
   HPI): Parkinson's disease, parkinsonian gait, Cushing syndrome, cushingoid features,
   Addison's disease, Addisonian crisis, Hodgkin lymphoma, non-Hodgkin lymphoma,
   Graves' disease, Crohn's disease, Wilson's disease, Huntington's disease, Barrett's
   esophagus, Paget's disease, Whipple procedure, Bell's palsy, Sweet syndrome.
   Spread them across notes; these are deliberate false-positive traps for a PHI
   detector (the same words will also be used as patient surnames elsewhere).
4. Vary follow-up timing implicitly: some notes' follow-up should read as prompt
   (within a week), others clearly later (weeks/months) — the placeholders will be
   filled accordingly, so just vary how many appointments and whether {{RELATIVE_DATE}}
   is used.
5. Keep each note 350–600 words, realistic clinical shorthand, no markdown.

Start with skeletons 11–20 now.
