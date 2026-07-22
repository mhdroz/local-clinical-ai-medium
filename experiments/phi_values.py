"""PHI value pools for the adversarial synthetic dataset (post #5).

Single source of truth shared by:
  - experiments/ingest_skeletons.py  (renders values INTO notes, records ground truth)
  - discharge_agent/redaction/recognizers.py  (detection regexes for the same formats)

Adversarial by design:
  - ~half the surnames are medical eponyms (Parkinson, Cushing, Addison, ...) so
    person names collide with clinical vocabulary
  - dates render in many formats, including relative phrases a regex won't catch
  - MRNs come in three formats, one of which is a bare number that looks like
    any other number in a clinical note
"""

import datetime

# ---------------------------------------------------------------- names

# (name, sex) — sex is used to keep honorifics ("Mr./Ms.") and the header's
# Sex: field consistent with the injected name
FIRST_NAMES = [
    ("Lisa", "F"), ("Margaret", "F"), ("James", "M"), ("Carlos", "M"),
    ("Dorothy", "F"), ("Robert", "M"), ("Emily", "F"), ("Frank", "M"),
    ("Grace", "F"), ("Henry", "M"), ("Alice", "F"), ("Walter", "M"),
    ("Diane", "F"), ("Paul", "M"), ("Nancy", "F"), ("Thomas", "M"),
    ("Ruth", "F"), ("Samuel", "M"), ("Karen", "F"), ("David", "M"),
    ("Helen", "F"), ("George", "M"), ("Anna", "F"), ("Peter", "M"),
    ("Clara", "F"), ("Louis", "M"), ("Martha", "F"), ("Edward", "M"),
    ("Joan", "F"), ("Arthur", "M"),
]

# Medical eponym surnames — these also appear in clinical terms
# ("Parkinson's disease", "Cushing syndrome", "Addisonian crisis", ...)
EPONYM_SURNAMES = [
    "Parkinson", "Cushing", "Addison", "Hodgkin", "Graves", "Crohn",
    "Wilson", "Huntington", "Barrett", "Paget", "Whipple", "Bell",
    "Berger", "Pott", "Sweet",
]

PLAIN_SURNAMES = [
    "Rodriguez", "Chen", "Okafor", "Kowalski", "Nguyen", "Patel",
    "Thompson", "Garcia", "Kim", "Ferreira", "Larsson", "Dubois",
    "Yamamoto", "Osei", "Novak",
]

SURNAMES = EPONYM_SURNAMES + PLAIN_SURNAMES

# Eponym clinical terms that may legitimately appear in note text.
# These are NOT PHI — they are the false-positive traps for the redaction
# engine, and later the allowlist seed for the fix iteration (Phase 4C).
EPONYM_CLINICAL_TERMS = [
    "Parkinson's disease", "parkinsonian gait", "Cushing syndrome",
    "cushingoid features", "Addison's disease", "Addisonian crisis",
    "Hodgkin lymphoma", "non-Hodgkin lymphoma", "Graves' disease",
    "Crohn's disease", "Wilson's disease", "Huntington's disease",
    "Barrett's esophagus", "Paget's disease", "Whipple procedure",
    "Bell's palsy", "Sweet syndrome",
]

# ---------------------------------------------------------------- providers

PROVIDER_CREDENTIALS = ["MD", "MD, PhD", "DO", "NP", "PA-C"]
PROVIDER_SPECIALTIES = [
    "Cardiology", "Endocrinology", "Gastroenterology", "Pulmonology",
    "Nephrology", "Neurology", "Internal Medicine", "Infectious Disease",
    "Hematology/Oncology", "Orthopedic Surgery",
]

# ---------------------------------------------------------------- MRN formats
# Each format: render(number_tuple) -> value string, regex -> detection pattern.
# The regex list feeds the custom Presidio recognizer; keep them in sync by
# construction (they live in the same dict).

MRN_FORMATS = {
    # bare 7-8 digit number, as in the original notes' "Unit No: 12345678"
    "digits": {
        "render": lambda rng: str(rng.randrange(1_000_000, 99_999_999)),
        "regex": r"\b\d{7,8}\b",
        "context": ["mrn", "unit no", "medical record", "record number"],
    },
    # letter-dash format: A-583-291
    "alpha_dash": {
        "render": lambda rng: f"{rng.choice('ABCDEFGH')}-{rng.randrange(100, 999)}-{rng.randrange(100, 999)}",
        "regex": r"\b[A-H]-\d{3}-\d{3}\b",
        "context": ["mrn", "unit no", "medical record", "record number"],
    },
    # year-prefixed format: MC-2024-00517
    "prefixed": {
        "render": lambda rng: f"MC-{rng.randrange(2018, 2026)}-{rng.randrange(10000, 99999)}",
        "regex": r"\bMC-\d{4}-\d{5}\b",
        "context": ["mrn", "unit no", "medical record", "record number"],
    },
}

# ---------------------------------------------------------------- phones

PHONE_FORMATS = [
    lambda rng: f"(617) 555-{rng.randrange(100, 999):03d}{rng.randrange(0, 10)}",
    lambda rng: f"617-555-{rng.randrange(1000, 9999)}",
    lambda rng: f"857.555.{rng.randrange(1000, 9999)}",
]

# ---------------------------------------------------------------- addresses

STREETS = [
    "Oak Street", "Maple Avenue", "Beacon Street", "Commonwealth Avenue",
    "Elm Road", "Harbor Lane", "Chestnut Street", "Willow Drive",
    "Highland Avenue", "Summer Street",
]
CITIES = [
    ("Boston", "MA", "02114"), ("Cambridge", "MA", "02139"),
    ("Somerville", "MA", "02143"), ("Quincy", "MA", "02169"),
    ("Brookline", "MA", "02445"), ("Medford", "MA", "02155"),
]


def render_address(rng):
    street = rng.choice(STREETS)
    city, state, zipc = rng.choice(CITIES)
    return f"{rng.randrange(1, 999)} {street}, {city}, {state} {zipc}"


# ---------------------------------------------------------------- dates

DATE_RENDERERS = {
    "iso": lambda d: d.isoformat(),                          # 2025-03-14
    "us_slash": lambda d: d.strftime("%m/%d/%Y"),            # 03/14/2025
    "long": lambda d: f"{d.strftime('%B')} {d.day}, {d.year}",   # March 14, 2025
    "short": lambda d: f"{d.strftime('%b')} {d.day}",        # Mar 14 (no year!)
    "day_month": lambda d: f"{d.day}-{d.strftime('%b')}-{d.year}",  # 14-Mar-2025
}

# Relative date phrases — rendered instead of an absolute date for some
# follow-up appointments. `days` is the intended offset from discharge, so
# the ground truth knows what the phrase means even though no date appears.
RELATIVE_DATE_PHRASES = [
    {"text": "in 2 weeks", "days": 14},
    {"text": "two weeks post-discharge", "days": 14},
    {"text": "in 7-10 days", "days": 7},
    {"text": "next Tuesday", "days": None},  # resolved against discharge weekday
    {"text": "within one month", "days": 30},
    {"text": "in 3 months", "days": 90},
]


def render_date(d: datetime.date, style: str) -> str:
    return DATE_RENDERERS[style](d)
