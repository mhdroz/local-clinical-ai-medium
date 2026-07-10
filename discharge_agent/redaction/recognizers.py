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


def build_analyzer() -> AnalyzerEngine:
    """AnalyzerEngine with spaCy en_core_web_lg + the custom MRN recognizer."""
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    provider = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}],
        }
    )
    analyzer = AnalyzerEngine(nlp_engine=provider.create_engine())
    analyzer.registry.add_recognizer(mrn_recognizer())
    return analyzer
