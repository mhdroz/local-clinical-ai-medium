"""Ground truth for the ORIGINAL 10 notes (1-10) via template-aware regexes.

    python -m experiments.annotate_original_notes [--review]

The original notes predate the placeholder generator, so their PHI can't be
recorded at injection time. They are, however, strongly templated (fixed
header, "Dr. First Last" providers, one address line, one phone format), so
targeted regexes recover the spans; --review prints every annotation in
context for manual verification before merging into data/phi_ground_truth.json
(existing entries for notes 11-40 are preserved).

Annotation policy (HIPAA Safe Harbor-ish, documented for the eval):
  - full dates (with month+day) are PHI DATE; bare years ("quit 2020") are not
  - appointment times ("2:00 PM") are NOT PHI — if the engine masks them they
    count as (benign) false positives
  - family member names count as PATIENT_NAME (non-provider persons)
  - employers/schools are out of scope (no ORG category in the eval)
"""

import argparse
import json
import os
import re

import pandas as pd

HONORIFIC = r"(?:Mr\.|Ms\.|Mrs\.)"
NAME = r"[A-Z][a-zà-ÿ]+(?:\s[A-Z][a-zà-ÿ]+)?"

PATTERNS = [
    # header fields — value group only
    ("PATIENT_NAME", re.compile(r"Name:\s*([A-ZÀ-Þ]+,\s*[A-ZÀ-Þ ]+?)(?:\s{2,}|\n)")),
    ("MRN", re.compile(r"Unit No:\s*(\d{6,10})")),
    ("DOB", re.compile(r"Date of Birth:\s*(\d{4}-\d{2}-\d{2})")),
    # providers: Dr. First [Middle] Last (word chars incl. accents)
    ("PROVIDER_NAME", re.compile(r"Dr\.\s([A-ZÀ-Þ][\wà-ÿ]+(?:\s[A-ZÀ-Þ][\wà-ÿ]+)*)")),
    # family members: "wife Helen Anderson", "daughter Nancy Brown", ...
    (
        "PATIENT_NAME",
        re.compile(
            r"\b(?:wife|husband|daughter|son|mother|father|sister|brother)\s+(" + NAME + r")"
        ),
    ),
    ("PATIENT_NAME", re.compile(HONORIFIC + r"\s(" + NAME + r")")),
    ("PHONE", re.compile(r"(\(\d{3}\)\s?\d{3}-\d{4}|\d{3}-\d{3}-\d{4}|\d{3}\.\d{3}\.\d{4})")),
    # addresses: "123 Oak Street, Boston MA 02114" (zip optional)
    (
        "ADDRESS",
        re.compile(
            # (?<![:\d]) keeps times ("10:00 AM") out; "Dr"/"St" only count as
            # street suffixes when not followed by "." (vs "Dr. Chen")
            r"(?<![:\d])(\d{1,4}\s[A-Z][\w]+(?:\s[A-Z][\w]+)*\s"
            r"(?:Street|Avenue|Ave|Drive|Road|Rd|Lane|Ln|Boulevard|Blvd|(?:St|Dr)(?!\.))\b"
            r"(?:,\s[A-Z][\w]+(?:\s[A-Z][\w]+)*\s?,?\s?(?:MA|NH|RI|CT)(?:\s\d{5})?)?)"
        ),
    ),
    # full dates: yyyy-mm-dd, m/d/yyyy, m/d (lab lines)
    ("DATE", re.compile(r"(\d{4}-\d{2}-\d{2})")),
    ("DATE", re.compile(r"(\d{1,2}/\d{1,2}/\d{4})")),
    # bare m/d ("03/15: WBC ...") — validated + context-gated in code below, so
    # pain scores ("CP 8/10"), BPs ("95/60") and shorthand ("2/2") stay out
    ("DATE_MD", re.compile(r"(?<![\d/])(\d{1,2}/\d{1,2})(?![\d/])")),
]

# a bare m/d only counts as a date in these contexts
MD_BEFORE = re.compile(r"(?:\bon |\bthrough |\bby |\buntil |\bCXR |\bCath |\bEcho |\(|- )$")


def _valid_md(val, text, start, end):
    m, d = val.split("/")
    if not (1 <= int(m) <= 12 and 1 <= int(d) <= 31):
        return False
    follows_colon = end < len(text) and text[end] == ":"
    closes_paren = end < len(text) and text[end] == ")"
    # lab lines with military time: "01/20 0300: BG 485"
    follows_time = bool(re.match(r"\s\d{4}:", text[end:]))
    return follows_colon or closes_paren or follows_time or bool(MD_BEFORE.search(text[:start]))

# spans matched by an earlier pattern win (e.g. DOB before generic DATE,
# provider "Dr. X" before honorific person)


def annotate_note(text):
    entities = []
    taken = []

    def free(s, e):
        return all(e <= a or s >= b for a, b in taken)

    for etype, rx in PATTERNS:
        for m in rx.finditer(text):
            s, e = m.span(1)
            val = m.group(1).strip()
            e = s + len(val)
            etype_out = etype
            if etype == "DATE_MD":
                if not _valid_md(val, text, s, e):
                    continue
                etype_out = "DATE"
            if not free(s, e):
                continue
            taken.append((s, e))
            entities.append(
                {"entity_type": etype_out, "text": val, "start": s, "end": e, "placeholder": None}
            )
    entities.sort(key=lambda x: x["start"])
    return entities


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--notes", default="data/synthetic_notes.csv")
    parser.add_argument("--out", default="data/phi_ground_truth.json")
    parser.add_argument("--review", action="store_true", help="print annotations in context")
    args = parser.parse_args()

    df = pd.read_csv(args.notes)

    ground_truth = {}
    if os.path.exists(args.out):
        with open(args.out) as f:
            ground_truth = json.load(f)

    for _, row in df.iterrows():
        note_id = str(int(row["noteid"]))
        text = row["note_text"]
        entities = annotate_note(text)
        for e in entities:
            assert text[e["start"] : e["end"]] == e["text"], (note_id, e)
        ground_truth[note_id] = {
            "entities": entities,
            "meta": {"source": "annotate_original_notes.py regex + manual review"},
        }
        if args.review:
            print(f"\n===== note {note_id} ({len(entities)} entities) =====")
            for e in entities:
                lo, hi = max(0, e["start"] - 30), min(len(text), e["end"] + 30)
                ctx = text[lo:hi].replace("\n", " ")
                print(f"  {e['entity_type']:<14} {e['text']!r:<40} …{ctx}…")

    with open(args.out, "w") as f:
        json.dump(ground_truth, f, indent=2)
    counts = {}
    for nid, v in ground_truth.items():
        if nid == "meta":
            continue
        for e in v["entities"]:
            counts[e["entity_type"]] = counts.get(e["entity_type"], 0) + 1
    print(f"\nwrote {args.out}; totals: {json.dumps(counts)}")


if __name__ == "__main__":
    main()
