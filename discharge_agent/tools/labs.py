from discharge_agent.tools.labs_normalization import (
    normalize_lab_name,
    parse_value,
    convert_if_needed,
)

REF = {
    "hematocrit": (36.0, 50.0),  # percent; female 36-45%, male up to 50%
    "bun": (7.0, 24.0),  # mg/dL
    "platelets": (150, 450),  # x10^9/L
    "hbA1c": (4.0, 5.6),  # percentage
    "beta-hydroxybutyrate": (0.0, 0.3),  # mmol/L
    "wbc": (4.0, 11.0),
    "na": (135, 145),
    "hemoglobin": (12.0, 16.0),
    "creatinine": (0.6, 1.3),
    "glucose": (70, 140),
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
