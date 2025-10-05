import re
from typing import Any, Dict, List, Tuple
from collections import Counter, defaultdict
import pandas as pd

SCALAR_FIELDS = [
    "discharge_date",
    "chief_complaint",
    "primary_discharge_diagnosis",
    "discharge_disposition",
]


def ntext(x: Any) -> str:
    s = "" if x is None else str(x).strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = s.replace(" ;", ";").replace(" ,", ",")
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
    return s


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


def tok_jacc(a: str, b: str) -> float:
    A = set(re.findall(r"[a-z0-9]+", a.lower()))
    B = set(re.findall(r"[a-z0-9]+", b.lower()))
    if not A and not B:
        return 1.0
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def parse_float(s: str):
    try:
        return True, float(re.findall(r"-?\d+\.?\d*", str(s))[0])
    except Exception:
        return False, float("nan")


def norm_scalar(field, v):
    return ndate(v) if field == "discharge_date" else ntext(v)


def scalar_scores(pred: Dict, gold: Dict) -> Dict[str, float]:
    out = {}
    for f in SCALAR_FIELDS:
        p = norm_scalar(f, pred.get(f, ""))
        g = norm_scalar(f, gold.get(f, ""))
        out[f + "_exact"] = 1.0 if (p == g and g != "") else 0.0
        out[f + "_soft"] = 1.0 if (tok_jacc(p, g) >= 0.8 and g != "") else 0.0
    out["scalar_exact_acc"] = sum(out[f + "_exact"] for f in SCALAR_FIELDS) / len(
        SCALAR_FIELDS
    )
    out["scalar_soft_acc"] = sum(out[f + "_soft"] for f in SCALAR_FIELDS) / len(
        SCALAR_FIELDS
    )
    return out


def lab_key(x):
    return ntext(x.get("name", "")), str(x.get("value", "")).strip()


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


def proc_key(x):
    return ntext(x.get("name", "") or x.get("procedure", "")), ndate(x.get("date", ""))


# Normalize gold procedures that are strings -> dicts
def normalize_gold_proc(g):
    procs = []
    for x in g.get("procedures_performed") or []:
        if isinstance(x, dict):
            procs.append(x)
        else:
            procs.append({"name": x, "date": ""})
    g = dict(g)
    g["procedures_performed"] = procs
    return g


def proc_key(x):
    # Accept dict or string
    if isinstance(x, str):
        name = x
        date = ""
    else:
        name = x.get("name") or x.get("procedure") or ""
        date = x.get("date", "")
    return ntext(name), ndate(date)


def normalize_procs_list(lst):
    """Turn list of str/dict into list of dicts with {name, date}."""
    out = []
    for x in lst or []:
        if isinstance(x, str):
            out.append({"name": x, "date": ""})
        elif isinstance(x, dict):
            out.append(
                {
                    "name": x.get("name") or x.get("procedure") or "",
                    "date": x.get("date", ""),
                }
            )
    return out


def f1_list(
    pred_list: List[Dict], gold_list: List[Dict], kind: str
) -> Tuple[int, int, int, float, float, float]:
    if kind == "labs":
        # tolerant on numeric values: ±1.0 or ±5%
        gold_map = defaultdict(list)
        for x in gold_list or []:
            k = ntext(x.get("name", ""))
            gold_map[k].append(str(x.get("value", "")).strip())
        tp = 0
        used = set()
        for x in pred_list or []:
            kname = ntext(x.get("name", ""))
            pval = str(x.get("value", "")).strip()
            for gv in gold_map.get(kname, []):
                if (kname, gv) in used:
                    continue
                ok_p, pv = parse_float(pval)
                ok_g, gvf = parse_float(gv)
                if ok_p and ok_g:
                    if (abs(pv - gvf) <= 1.0) or (
                        gvf != 0 and abs(pv - gvf) / abs(gvf) <= 0.05
                    ):
                        tp += 1
                        used.add((kname, gv))
                        break
                else:
                    if ntext(pval) == ntext(gv):
                        tp += 1
                        used.add((kname, gv))
                        break
        fp = len(pred_list or []) - tp
        fn = len(gold_list or []) - tp
    else:
        if kind == "meds":
            P = set(meds_key(x) for x in (pred_list or []))
            G = set(meds_key(x) for x in (gold_list or []))
        elif kind == "followups":
            P = set(fup_key(x) for x in (pred_list or []))
            G = set(fup_key(x) for x in (gold_list or []))
        elif kind == "procedures":
            P = set(proc_key(x) for x in (pred_list or []))
            G = set(proc_key(x) for x in (gold_list or []))
        else:
            P = set()
            G = set()
        tp = len(P & G)
        fp = len(P - G)
        fn = len(G - P)
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
    return tp, fp, fn, prec, rec, f1


# Aggregate per model
def agg_mean(df, cols, by="model"):
    if df.empty:
        return pd.DataFrame(columns=[by] + cols)
    return df.groupby(by)[cols].mean().reset_index()
