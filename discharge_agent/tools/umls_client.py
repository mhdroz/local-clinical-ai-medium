import requests
from typing import List, Dict
from functools import lru_cache
import os

UMLS_BASE = os.getenv("UMLS_BASE")
UMLS_API_KEY = os.getenv("UMLS_API_KEY")

_DEMO_CUI = {
    "upper gastrointestinal bleeding": {
        "cui": "C0041909",
        "pref_name": "Upper gastrointestinal hemorrhage",
        "semantic_types": ["Pathologic Function"],
    },
    "duodenal ulcer": {
        "cui": "C0013295",
        "pref_name": "Duodenal Ulcer",
        "semantic_types": ["Disease or Syndrome"],
    },
    "acute blood loss anemia": {
        "cui": "C0154298",
        "pref_name": "Acute posthemorrhagic anemia",
        "semantic_types": ["Disease or Syndrome"],
    },
    "hypertension": {
        "cui": "C0020538",
        "pref_name": "Hypertensive disease",
        "semantic_types": ["Disease or Syndrome"],
    },
    "chronic back pain": {
        "cui": "C0740418",
        "pref_name": "Chronic back pain",
        "semantic_types": ["Sign or Symptom"],
    },
    "diabetic ketoacidosis": {
        "cui": "C0011880",
        "pref_name": "Diabetic Ketoacidosis",
        "semantic_types": ["Disease or Syndrome"],
    },
}


def _get(url, params=None):
    params = params or {}
    params["apiKey"] = UMLS_API_KEY
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json().get("result", {})


@lru_cache(maxsize=2048)
def umls_search_cui(term: str, sabs=None, max_hits=5):
    """
    Term -> list of candidate CUIs with names. Uses normalizedString search.
    sabs: optional comma-separated sources to bias (e.g., 'SNOMEDCT_US,ICD10CM')
    """
    params = {
        "string": term,
        "searchType": "normalizedString",  # robust matching
        "pageSize": max_hits,
    }
    if sabs:
        params["sabs"] = sabs
    res = _get(f"{UMLS_BASE}/search/current", params)
    out = []
    for row in res.get("results", []):
        if row.get("ui") and row["ui"] != "NONE":
            out.append(
                {
                    "cui": row["ui"],
                    "name": row.get("name"),
                    "rootSource": row.get("rootSource"),
                }
            )
    return out


@lru_cache(maxsize=4096)
def umls_cui_info(cui: str):
    """CUI -> preferred name, semantic types"""
    res = _get(f"{UMLS_BASE}/content/current/CUI/{cui}")
    name = res.get("name")
    stys = [st["name"] for st in res.get("semanticTypes", [])]
    return {"cui": cui, "name": name, "semantic_types": stys}


def normalize_terms_to_cui(terms, prefer_sabs=None):
    """
    terms: list[str]
    returns: {term: {'cui': ..., 'pref_name': ..., 'semantic_types': [...],}}
    """
    out = {}
    for t in terms:
        cands = umls_search_cui(t, sabs=prefer_sabs)
        top = cands[0] if cands else None
        if not top:
            out[t] = {
                "cui": None,
                "pref_name": None,
                "semantic_types": [],
            }
            continue
        info = umls_cui_info(top["cui"])
        out[t] = {
            "cui": info["cui"],
            "pref_name": info["name"],
            "semantic_types": info["semantic_types"],
        }
    return out


def umls_normalize(terms: List[str]) -> List[Dict]:
    if UMLS_API_KEY:
        # Use real API-backed normalization
        return normalize_terms_to_cui(terms, prefer_sabs="SNOMEDCT_US")
    else:
        # Demo fallback
        print("No access to UMLS API, using the demo dictionary")
        out = []
        for t in terms:
            key = t.lower().strip()
            if key in _DEMO_CUI:
                entry = _DEMO_CUI[key]
                out.append(
                    {
                        "input": t,
                        "cui": entry["cui"],
                        "pref_name": entry["pref_name"],
                        "semantic_types": entry["semantic_types"],
                    }
                )
            else:
                out.append(
                    {"input": t, "cui": None, "pref_name": None, "semantic_types": []}
                )
        return out


# def umls_normalize(terms: List[str]) -> List[Dict]:
#    return normalize_terms_to_cui(terms, prefer_sabs="SNOMEDCT_US", include_snomed=True)
