import re

# --- Canonical reference ranges (adults) ---
# Units noted in comments. Use your alias/unit normalizer in front of flag_labs.

REF = {
    # CBC / heme
    "wbc": (4.0, 11.0),  # x10^9/L
    "hemoglobin": (12.0, 16.0),  # g/dL  (sex-specific ranges exist)
    "hematocrit": (36.0, 50.0),  # %
    "platelet count": (150, 450),  # x10^9/L
    # Basic chem / renal / glucose
    "sodium": (135, 145),  # mmol/L
    "potassium": (3.5, 5.0),  # mmol/L
    "creatinine": (0.6, 1.3),  # mg/dL
    "bun": (7.0, 24.0),  # mg/dL
    "glucose": (70, 140),  # mg/dL (random/non-fasting demo)
    # Acid–base / ABG
    "ph": (7.35, 7.45),  # arterial blood
    "hco3": (22, 28),  # mEq/L
    "pco2": (35, 45),  # mmHg (arterial)
    "po2": (80, 100),  # mmHg (room air)
    "anion gap": (8, 16),  # mEq/L (lab-dependent)
    # Lipids (typical desirable ranges; fasting affects TG)
    "cholesterol total": (0, 199),  # mg/dL
    "ldl cholesterol": (0, 129),  # mg/dL (optimal <100)
    "hdl cholesterol": (40, 100),  # mg/dL (no firm upper bound; >=40 desirable)
    "triglycerides": (0, 149),  # mg/dL (normal <150)
    # Cardiac / enzymes
    "creatine kinase": (30, 200),  # U/L (assay & lab dependent)
    "troponin i": (0.00, 0.04),  # ng/mL (ASSAY-SPECIFIC! demo cutoff)
    # LFTs / cholestasis
    "alt": (7, 56),  # U/L (lab dependent)
    "ast": (10, 40),  # U/L
    "alkaline phosphatase": (44, 147),  # U/L
    "total bilirubin": (0.1, 1.2),  # mg/dL
    "direct bilirubin": (0.0, 0.3),  # mg/dL
    # Endocrine / diabetes
    "hba1c": (4.0, 5.6),  # %
    "beta-hydroxybutyrate": (0.0, 0.3),  # mmol/L
    # Heart failure marker
    "bnp": (0, 99),  # pg/mL (age-dependent in reality)
    # Imaging-derived metric (treated like a “lab” here for flagging)
    "ejection fraction": (55, 70),  # % (normal; <50 reduced)
}

# --- Aliases: map messy names → canonical REF keys ---
ALIASES = {
    # CBC
    "wbc": "wbc",
    "hgb": "hemoglobin",
    "hemoglobin": "hemoglobin",
    "hct": "hematocrit",
    "hematocrit": "hematocrit",
    "plt": "platelet count",
    "platelets": "platelet count",
    "platelet count": "platelet count",
    # Basic chem / renal / glucose
    "na": "sodium",
    "sodium": "sodium",
    "k": "potassium",
    "potassium": "potassium",
    "cr": "creatinine",
    "creatinine": "creatinine",
    "bun": "bun",
    "glucose": "glucose",
    "blood glucose": "glucose",
    "bg": "glucose",
    # Acid–base / ABG
    "ph": "ph",
    "hco3": "hco3",
    "bicarbonate": "hco3",
    "pco2": "pco2",
    "po2": "po2",
    "anion gap": "anion gap",
    # Lipids
    "chol": "cholesterol total",
    "total cholesterol": "cholesterol total",
    "ldl": "ldl cholesterol",
    "hdl": "hdl cholesterol",
    "tg": "triglycerides",
    "triglycerides": "triglycerides",
    # Cardiac / enzymes
    "ck": "creatine kinase",
    "creatine kinase": "creatine kinase",
    "trop i": "troponin i",
    "troponin i": "troponin i",
    # LFTs
    "alt": "alt",
    "ast": "ast",
    "alk phos": "alkaline phosphatase",
    "alkaline phosphatase": "alkaline phosphatase",
    "t bili": "total bilirubin",
    "total bilirubin": "total bilirubin",
    "d bili": "direct bilirubin",
    "direct bilirubin": "direct bilirubin",
    # Endocrine
    "hba1c": "hba1c",
    "hemoglobin a1c": "hba1c",
    "beta-hydroxybutyrate": "beta-hydroxybutyrate",
    "bhb": "beta-hydroxybutyrate",
    # Cardiac marker
    "bnp": "bnp",
    # Imaging-derived metric
    "echo ef": "ejection fraction",
    "ejection fraction": "ejection fraction",
}

# Tip for your normalizer:
#  - lower() + strip punctuation
#  - replace hyphens with spaces, collapse spaces
#  - look up in ALIASES; if found, use REF[ALIASES[name]]


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
