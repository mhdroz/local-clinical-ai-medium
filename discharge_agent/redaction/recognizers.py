"""Presidio analyzer setup: default recognizers + custom MRN recognizer.

The MRN regexes come from experiments/phi_values.py — the SAME definitions used
to generate the synthetic MRNs — so generator and detector can't drift apart.
(That also means MRN detection is best-case here; a real deployment would need
to discover its MRN formats the hard way. Noted as a limitation in the writeup.)
"""

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer

from experiments.phi_values import MRN_FORMATS

# Entities we ask Presidio for. Everything else (US_DRIVER_LICENSE, CRYPTO...)
# just adds noise on clinical text.
DEFAULT_ENTITIES = [
    "PERSON",
    "DATE_TIME",
    "PHONE_NUMBER",
    "LOCATION",
    "EMAIL_ADDRESS",
    "US_SSN",
    "MRN",
]


def mrn_recognizer() -> PatternRecognizer:
    patterns = [
        Pattern(
            name=f"mrn_{fmt_name}",
            regex=fmt["regex"],
            # bare digit runs are weak evidence on their own (lab values, zip
            # codes); prefixed formats are strong
            score=0.4 if fmt_name == "digits" else 0.75,
        )
        for fmt_name, fmt in MRN_FORMATS.items()
    ]
    context = sorted({w for fmt in MRN_FORMATS.values() for w in fmt["context"]})
    return PatternRecognizer(
        supported_entity="MRN",
        name="mrn_recognizer",
        patterns=patterns,
        context=context,
    )


def header_name_recognizer() -> PatternRecognizer:
    """Names in the structured header ('Name: JOHNSON, ALEX').

    Experiment A found spaCy NER misses all-caps header names entirely some of
    the time (worse when the surname is a medical eponym like PARKINSON) — but
    the note template makes them trivially matchable. This is the Phase 4C
    'custom recognizer' fix: lean on document structure where NER is weak.
    """
    return PatternRecognizer(
        supported_entity="PERSON",
        name="header_name_recognizer",
        patterns=[
            Pattern(
                name="name_header",
                regex=r"(?<=Name: )[A-ZÀ-Þ][A-ZÀ-Þ'\-]+,\s*[A-ZÀ-Þ][A-ZÀ-Þ'\-]+(?: [A-ZÀ-Þ][A-ZÀ-Þ'\-]+)*",
                score=0.9,
            )
        ],
    )


def md_date_recognizer() -> PatternRecognizer:
    """Bare month/day dates ('03/15:' lab lines) that spaCy's DATE_TIME misses.

    Month is range-constrained so blood pressures ('95/60') don't match;
    pain scores ('8/10') and strength ('4/5') still can — the policy's benign
    filters drop those denominators. Ambiguity is inherent and documented.
    """
    return PatternRecognizer(
        supported_entity="DATE_TIME",
        name="md_date_recognizer",
        patterns=[
            Pattern(
                name="bare_month_day",
                regex=r"\b(?:0?[1-9]|1[0-2])/(?:[0-2]?[0-9]|3[01])\b(?!/)",
                score=0.6,
            ),
            # "Jun 11", "June 19, 2024" — spaCy misses short month-name dates
            Pattern(
                name="month_name_day",
                regex=r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:,\s*\d{4})?\b",
                score=0.6,
            ),
            # "4-Dec-2024"
            Pattern(
                name="day_month_year",
                regex=r"\b\d{1,2}-(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*-\d{4}\b",
                score=0.6,
            ),
        ],
    )


def build_analyzer(extended: bool = False) -> AnalyzerEngine:
    """AnalyzerEngine with spaCy en_core_web_lg + the custom MRN recognizer.

    extended=True adds the Phase 4C structural recognizers (header names,
    bare m/d dates) — used by redaction policy v2."""
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    provider = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}],
        }
    )
    analyzer = AnalyzerEngine(nlp_engine=provider.create_engine())
    analyzer.registry.add_recognizer(mrn_recognizer())
    if extended:
        analyzer.registry.add_recognizer(header_name_recognizer())
        analyzer.registry.add_recognizer(md_date_recognizer())
    return analyzer
