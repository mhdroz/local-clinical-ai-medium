import re
from collections import Counter, defaultdict
from statistics import median
from typing import Any, Dict, List


# ---- Normalizers ----
def ntext(x: Any) -> str:
    s = "" if x is None else str(x).strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def ndate(x: Any) -> str:
    if not x:
        return ""
    s = str(x).strip()
    m = re.match(r"^(\d{4})[-/](\d{2})[-/](\d{2})$", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", s)
    if m:
        return f"{m.group(3)}-{m.group(1)}-{m.group(2)}"
    m = re.match(r"^(\d{2})/(\d{2})$", s)
    if m:
        return f"0000-{m.group(1)}-{m.group(2)}"
    return s  # keep other formats as-is (e.g., "03/01 0600")


def ntime(x: Any) -> str:
    if not x:
        return ""
    s = str(x).strip().lower().replace(" ", "")
    m = re.search(r"(\d{1,2}):(\d{2})(am|pm)", s)
    if m:
        h = int(m.group(1))
        mi = int(m.group(2))
        ap = m.group(3)
        if ap == "pm" and h != 12:
            h += 12
        if ap == "am" and h == 12:
            h = 0
        return f"{h:02d}:{mi:02d}"
    m = re.search(r"^(\d{1,2}):(\d{2})$", s)
    if m:
        return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"
    return s


# Optional: simple lab synonym map for better merge (extend as needed)
LAB_SYNONYM = {
    "trop i": "troponin i",
    "chol": "cholesterol",
    "tg": "triglycerides",
}


def canon_lab_name(n: str) -> str:
    n2 = ntext(n)
    return LAB_SYNONYM.get(n2, n2)


# ---- Keys for set-like matching ----
def meds_key(x):
    return (
        ntext(x.get("name", "")),
        ntext(x.get("dose", "")),
        ntext(x.get("frequency", "")),
    )


def fup_key(x):
    return (
        ntext(x.get("provider", "")),
        ntext(x.get("specialty", "")),
        ndate(x.get("date", "")),
        ntime(x.get("time", "")),
    )


def proc_to_dict(x):
    if isinstance(x, str):
        return {"name": x, "date": ""}
    return {
        "name": (x.get("name") or x.get("procedure") or ""),
        "date": x.get("date", ""),
    }


def proc_key(x):
    d = proc_to_dict(x)
    return (ntext(d["name"]), ndate(d["date"]))


# ---- Majority chooser for scalars ----
def majority_value(values: List[str]) -> str:
    vals = [v for v in values if v]
    if not vals:
        return ""
    cnt = Counter(vals)
    top, freq = cnt.most_common(1)[0]
    # tie-break: longest non-empty
    ties = [v for v, c in cnt.items() if c == freq]
    return max(ties, key=len)


# ---- Consensus for a single note ----
def consensus_for_note(note_outputs: Dict[str, Dict], quorum: float = 0.5) -> Dict:
    models = list(note_outputs.values())
    mcount = max(1, len(models))
    need = max(1, int(round(quorum * mcount)))

    gold = {
        "discharge_date": "",
        "chief_complaint": "",
        "primary_discharge_diagnosis": "",
        "discharge_disposition": "",
        "procedures_performed": [],
        "discharge_condition": {},
        "medication_changes": {"new_medications": [], "dose_changes": []},
        "follow_up_appointments": [],
        "most_recent_labs": [],
    }

    # Scalars (majority)
    scalar_fields = [
        "discharge_date",
        "chief_complaint",
        "primary_discharge_diagnosis",
        "discharge_disposition",
    ]
    for f in scalar_fields:
        vals = []
        for out in models:
            v = out.get(f, "")
            vals.append(ndate(v) if f == "discharge_date" else ntext(v))
        gold[f] = majority_value(vals)

    # Labs (per name; numeric -> median; else mode). Require quorum on *name* presence.
    name_to_vals = defaultdict(list)
    for out in models:
        for lab in out.get("most_recent_labs") or []:
            name = lab.get("name", "")
            if not name:
                continue
            value = str(lab.get("value", "")).strip()
            name_to_vals[name].append(value)

    labs_consensus = []
    for name, vals in name_to_vals.items():
        if len(vals) < need:
            continue
        # numeric median if possible, else mode
        nums = []
        for v in vals:
            m = re.findall(r"-?\d+\.?\d*", v)
            nums.append(float(m[0])) if m else None
        if sum(1 for v in vals if re.search(r"-?\d+\.?\d*", v)) >= need:
            # enough numeric reports -> median
            num_vals = [
                float(re.findall(r"-?\d+\.?\d*", v)[0])
                for v in vals
                if re.search(r"-?\d+\.?\d*", v)
            ]
            val = str(median(num_vals))
        else:
            val = Counter([ntext(v) for v in vals if v]).most_common(1)[0][0]
        labs_consensus.append({"name": name, "value": val})
    gold["most_recent_labs"] = labs_consensus

    # New medications (quorum on exact triple)
    med_counts = Counter()
    med_example = {}
    for out in models:
        for m in (out.get("medication_changes") or {}).get("new_medications") or []:
            k = meds_key(m)
            med_counts[k] += 1
            med_example[k] = {"name": k[0], "dose": k[1], "frequency": k[2]}
    gold["medication_changes"]["new_medications"] = [
        med_example[k] for k, c in med_counts.items() if c >= need
    ]

    # Follow-ups (quorum on tuple)
    fup_counts = Counter()
    fup_example = {}
    for out in models:
        for fu in out.get("follow_up_appointments") or []:
            k = fup_key(fu)
            fup_counts[k] += 1
            fup_example[k] = {
                "provider": k[0],
                "specialty": k[1],
                "date": k[2],
                "time": k[3],
            }
    gold["follow_up_appointments"] = [
        fup_example[k] for k, c in fup_counts.items() if c >= need
    ]

    # Procedures (string or dict; quorum on tuple)
    proc_counts = Counter()
    proc_example = {}
    for out in models:
        for p in out.get("procedures_performed") or []:
            k = proc_key(p)
            proc_counts[k] += 1
            d = proc_to_dict(p)
            proc_example[k] = {"name": d["name"], "date": d["date"]}
    gold["procedures_performed"] = [
        proc_example[k] for k, c in proc_counts.items() if c >= need
    ]

    # (optional) Discharge condition: naive union of most common keys/values
    dc_kv = defaultdict(list)
    for out in models:
        for k, v in (out.get("discharge_condition") or {}).items():
            dc_kv[k].append(ntext(v))
    gold["discharge_condition"] = {
        k: Counter(vs).most_common(1)[0][0]
        for k, vs in dc_kv.items()
        if len(vs) >= need
    }

    return gold


# ---- Build consensus for all notes ----
def consensus_gold_all(data: List[Dict[str, Dict]], quorum: float = 0.5) -> List[Dict]:
    return [consensus_for_note(note_models, quorum=quorum) for note_models in data]
