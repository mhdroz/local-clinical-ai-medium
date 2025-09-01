import re

ALIASES = {
    "hct": "hematocrit",
    "hematocrit": "hematocrit",
    "bun": "bun",
    "blood urea nitrogen": "bun",
    "platelets": "platelet count",
    "plt": "platelet count",
    "platelet count": "platelet count",
    "hbA1c": "hemoglobin a1c",
    "hba1c": "hemoglobin a1c",
    "a1c": "hemoglobin a1c",
    "beta-hydroxybutyrate": "beta-hydroxybutyrate",
    "bhb": "beta-hydroxybutyrate",
    "3-hydroxybutyrate": "beta-hydroxybutyrate",
    "wbc": "wbc",
    "na": "sodium",
    "sodium": "sodium",
    "hgb": "hemoglobin",
    "hemoglobin": "hemoglobin",
    "cr": "creatinine",
    "creatinine": "creatinine",
    "glucose": "glucose",
}


def normalize_lab_name(name: str) -> str:
    key = (name or "").strip().lower().replace("%", "").replace(".", "")
    # collapse extra spaces/hyphens
    key = " ".join(key.replace("-", " ").split())
    return ALIASES.get(key, key)  # fall back to itself


def parse_value(val_str: str):
    """Extract numeric value and crude unit token if present."""
    s = (val_str or "").strip().lower()
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    num = float(m.group(0)) if m else None
    # detect a few units if provided
    unit = None
    if "mmol/l" in s:
        unit = "mmol/L"
    elif "mg/dl" in s:
        unit = "mg/dL"
    elif "%" in s:
        unit = "%"
    elif "x10" in s or "×10" in s:
        unit = "x10^9/L"
    return num, unit


def convert_if_needed(name_norm: str, value: float, unit: str):
    """Minimal conversions for common pitfalls; otherwise passthrough."""
    if value is None:
        return None
    # Example: allow glucose mmol/L → mg/dL (1 mmol/L glucose ≈ 18 mg/dL)
    if name_norm == "glucose" and unit == "mmol/L":
        return value * 18.0
    # BHB sometimes reported in mg/dL; convert mg/dL → mmol/L (factor ~0.096)
    if name_norm == "beta-hydroxybutyrate" and unit == "mg/dL":
        return value * 0.096
    # Add more unit conversions for other use cases...
    return value
