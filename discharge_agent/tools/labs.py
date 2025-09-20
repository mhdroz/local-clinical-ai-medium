from discharge_agent.tools.labs_normalization import (
    normalize_lab_name,
    parse_value,
    convert_if_needed,
)

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


def flag_labs(labs: list) -> dict:
    out = []
    for l in labs:
        name_raw = l.get("name")
        val_str = l.get("value")
        name_norm = normalize_lab_name(name_raw)
        if name_norm not in REF:
            continue
        v, unit = parse_value(val_str)
        v = convert_if_needed(name_norm, v, unit)
        if v is None:
            continue
        lo, hi = REF[name_norm]
        if v < lo or v > hi:
            out.append(
                {
                    "name_input": name_raw,
                    "name_norm": name_norm,
                    "value": val_str,
                    "value_num": v,
                    "ref_range": f"{lo}-{hi}",
                    "status": "low" if v < lo else "high",
                }
            )
    return {"abnormal": out, "ok": len(out) == 0}
