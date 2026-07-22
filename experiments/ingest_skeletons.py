"""Turn LLM-generated note skeletons into the extended dataset + exact ground truth.

    python -m experiments.ingest_skeletons [--skeletons data/skeletons/skeletons.jsonl]

Input: JSONL skeletons with {{PLACEHOLDER}} tokens (see generation_prompt.md).
Output:
  - data/synthetic_notes_extended.csv   (noteid 11-40, same columns as the original)
  - data/phi_ground_truth.json          (exact spans, plus per-note meta)

Ground truth is exact BY CONSTRUCTION: PHI values are injected here, and spans
are recorded during substitution (offset bookkeeping), never re-searched. A
final validation pass asserts every recorded span matches its note slice and
hard-fails otherwise.

Only injected values are PHI. Eponym clinical terms the skeleton contains
("Cushing syndrome", "Parkinson's disease", ...) are clinical vocabulary, NOT
ground-truth entities — they are the false-positive traps for the redaction
engine.
"""

import argparse
import datetime
import json
import os
import random
import re

from experiments.phi_values import (
    EPONYM_SURNAMES,
    FIRST_NAMES,
    MRN_FORMATS,
    PHONE_FORMATS,
    PLAIN_SURNAMES,
    PROVIDER_CREDENTIALS,
    PROVIDER_SPECIALTIES,
    RELATIVE_DATE_PHRASES,
    DATE_RENDERERS,
    render_address,
)

PLACEHOLDER_RE = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")

REQUIRED_PLACEHOLDERS = {
    "PATIENT_NAME",
    "MRN",
    "DOB",
    "SEX",
    "ADMIT_DATE",
    "DISCHARGE_DATE",
    "ADDRESS",
    "PROVIDER_1",
    "PHONE",
}

BASE_SEED = 20260709  # recorded in the output meta for reproducibility

DATE_STYLES = list(DATE_RENDERERS.keys())


class NoteSampler:
    """Samples one note's worth of consistent PHI values."""

    def __init__(self, skeleton_id: int, seed: int):
        self.rng = random.Random(seed + skeleton_id)
        first, sex = self.rng.choice(FIRST_NAMES)
        # half the patients get an eponym surname — the adversarial case
        surname_pool = EPONYM_SURNAMES if self.rng.random() < 0.5 else PLAIN_SURNAMES
        self.first, self.sex = first, sex
        self.last = self.rng.choice(surname_pool)

        today = datetime.date(2025, 6, 1)
        self.admit = today - datetime.timedelta(days=self.rng.randrange(30, 400))
        self.discharge = self.admit + datetime.timedelta(days=self.rng.randrange(3, 11))
        age_years = self.rng.randrange(45, 91)
        self.dob = self.admit - datetime.timedelta(days=age_years * 365 + self.rng.randrange(0, 365))
        self.appt_dates = {
            "APPT_DATE_1": self.discharge + datetime.timedelta(days=self.rng.randrange(2, 11)),
            "APPT_DATE_2": self.discharge + datetime.timedelta(days=self.rng.randrange(11, 29)),
        }
        self.relative = self.rng.choice(RELATIVE_DATE_PHRASES)

        self.mrn_format = self.rng.choice(sorted(MRN_FORMATS))
        self.mrn = MRN_FORMATS[self.mrn_format]["render"](self.rng)
        self.address = render_address(self.rng)
        self.phones = {}
        self.providers = {}

    def provider(self, token: str) -> str:
        if token not in self.providers:
            pfirst, _ = self.rng.choice(FIRST_NAMES)
            # providers draw from the full surname pool too — "Dr. James Cushing"
            plast = self.rng.choice(EPONYM_SURNAMES + PLAIN_SURNAMES)
            style = self.rng.randrange(4)
            if style == 0:
                rendered = f"Dr. {pfirst} {plast}"
            elif style == 1:
                rendered = f"Dr. {pfirst} {plast}, MD"
            elif style == 2:
                cred = self.rng.choice(PROVIDER_CREDENTIALS)
                spec = self.rng.choice(PROVIDER_SPECIALTIES)
                rendered = f"Dr. {pfirst} {plast}, {cred}, {spec}"
            else:
                rendered = f"{pfirst} {plast}, NP"
            self.providers[token] = rendered
        return self.providers[token]

    def phone(self, token: str) -> str:
        if token not in self.phones:
            self.phones[token] = self.rng.choice(PHONE_FORMATS)(self.rng)
        return self.phones[token]

    def date_str(self, d: datetime.date) -> str:
        return DATE_RENDERERS[self.rng.choice(DATE_STYLES)](d)

    def resolve(self, token: str):
        """-> (rendered_text, entity_type or None)"""
        if token == "PATIENT_NAME":
            return f"{self.last.upper()}, {self.first.upper()}", "PATIENT_NAME"
        if token == "PATIENT_REF":
            honorific = "Mr." if self.sex == "M" else "Ms."
            return f"{honorific} {self.last}", "PATIENT_NAME"
        if token == "SEX":
            return self.sex, None
        if token == "MRN":
            return self.mrn, "MRN"
        if token == "DOB":
            return self.date_str(self.dob), "DOB"
        if token == "ADMIT_DATE":
            return self.date_str(self.admit), "DATE"
        if token == "DISCHARGE_DATE":
            return self.date_str(self.discharge), "DATE"
        if token in self.appt_dates:
            return self.date_str(self.appt_dates[token]), "DATE"
        if token == "RELATIVE_DATE":
            return self.relative["text"], "DATE"
        if token.startswith("PHONE"):
            return self.phone(token), "PHONE"
        if token == "ADDRESS":
            return self.address, "ADDRESS"
        if token.startswith("PROVIDER"):
            return self.provider(token), "PROVIDER_NAME"
        raise ValueError(f"unknown placeholder {{{{{token}}}}}")

    def meta(self) -> dict:
        return {
            "sex": self.sex,
            "patient_name": f"{self.first} {self.last}",
            "eponym_surname": self.last in EPONYM_SURNAMES,
            "mrn_format": self.mrn_format,
            "admit_date": self.admit.isoformat(),
            "discharge_date": self.discharge.isoformat(),
            "appt_dates": {k: v.isoformat() for k, v in self.appt_dates.items()},
            "relative_date_phrase": self.relative["text"],
            "relative_date_days": self.relative["days"],
        }


def inject(skeleton_text: str, sampler: NoteSampler):
    """Substitute placeholders, recording exact spans as we build the string."""
    out_parts = []
    entities = []
    pos = 0
    offset = 0  # length of output built so far
    for m in PLACEHOLDER_RE.finditer(skeleton_text):
        literal = skeleton_text[pos : m.start()]
        out_parts.append(literal)
        offset += len(literal)
        rendered, entity_type = sampler.resolve(m.group(1))
        if entity_type is not None:
            entities.append(
                {
                    "entity_type": entity_type,
                    "text": rendered,
                    "start": offset,
                    "end": offset + len(rendered),
                    "placeholder": m.group(1),
                }
            )
        out_parts.append(rendered)
        offset += len(rendered)
        pos = m.end()
    out_parts.append(skeleton_text[pos:])
    return "".join(out_parts), entities


def validate(note_text: str, entities: list, skeleton_id: int):
    leftovers = PLACEHOLDER_RE.findall(note_text)
    assert not leftovers, f"note {skeleton_id}: unresolved placeholders {leftovers}"
    for e in entities:
        actual = note_text[e["start"] : e["end"]]
        assert actual == e["text"], (
            f"note {skeleton_id}: span mismatch for {e['placeholder']}: "
            f"expected {e['text']!r}, got {actual!r}"
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skeletons", default="data/skeletons/skeletons.jsonl")
    parser.add_argument("--out-csv", default="data/synthetic_notes_extended.csv")
    parser.add_argument("--out-gt", default="data/phi_ground_truth.json")
    parser.add_argument("--seed", type=int, default=BASE_SEED)
    args = parser.parse_args()

    skeletons = []
    with open(args.skeletons) as f:
        for line in f:
            line = line.strip()
            if line:
                skeletons.append(json.loads(line))
    print(f"loaded {len(skeletons)} skeletons from {args.skeletons}")

    rows = []
    ground_truth = {
        "meta": {
            "seed": args.seed,
            "generator": "experiments/ingest_skeletons.py",
            "skeleton_file": args.skeletons,
        }
    }
    for sk in skeletons:
        sid = int(sk["skeleton_id"])
        found = set(PLACEHOLDER_RE.findall(sk["note_text"]))
        missing = REQUIRED_PLACEHOLDERS - found
        assert not missing, f"skeleton {sid} missing required placeholders: {sorted(missing)}"
        assert "APPT_DATE_1" in found or "RELATIVE_DATE" in found, (
            f"skeleton {sid} has no follow-up date placeholder"
        )

        sampler = NoteSampler(sid, args.seed)
        note_text, entities = inject(sk["note_text"], sampler)
        validate(note_text, entities, sid)

        rows.append(
            {
                "noteid": sid,
                "note_type": sk.get("note_type", "Discharge Summary"),
                "note_text": note_text,
                "main_diagnosis": sk.get("main_diagnosis", ""),
            }
        )
        ground_truth[str(sid)] = {"entities": entities, "meta": sampler.meta()}

    import pandas as pd

    df = pd.DataFrame(rows, columns=["noteid", "note_type", "note_text", "main_diagnosis"])
    os.makedirs(os.path.dirname(args.out_csv) or ".", exist_ok=True)
    df.to_csv(args.out_csv, index=False)
    with open(args.out_gt, "w") as f:
        json.dump(ground_truth, f, indent=2)

    n_entities = sum(len(v["entities"]) for k, v in ground_truth.items() if k != "meta")
    by_type = {}
    for k, v in ground_truth.items():
        if k == "meta":
            continue
        for e in v["entities"]:
            by_type[e["entity_type"]] = by_type.get(e["entity_type"], 0) + 1
    print(f"wrote {len(rows)} notes -> {args.out_csv}")
    print(f"wrote {n_entities} ground-truth entities -> {args.out_gt}")
    print("entities by type:", json.dumps(by_type, indent=2))


if __name__ == "__main__":
    main()
