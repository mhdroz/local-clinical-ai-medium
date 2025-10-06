import requests, json
from discharge_agent.extractions.prompts import system_prompt, get_user_prompt
from discharge_agent.llm.llm_utils import MedicalDataExtractor
import os
from dotenv import load_dotenv

load_dotenv()

API = os.getenv("LLM_API")
MODEL = os.getenv("MODEL")


def extract_clinical_information(note):
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": get_user_prompt(note)},
        ],
        "stream": False,
    }
    r = requests.post(API, json=payload, timeout=120)
    return r.json()["message"]["content"]


def run_extraction_with_json_evaluation(
    df, extractor: MedicalDataExtractor, text_col="note_text", max_retries=3
):
    """
    Run extraction on a dataframe of notes and evaluate JSON validity.

    Args:
        df: pandas DataFrame with a column of note text
        extractor: MedicalDataExtractor instance (local, openai, or anthropic)
        text_col: name of the column containing note text
        max_retries: number of times to retry if JSON parsing fails

    Returns:
        results: list of successfully parsed JSON dicts
        summary: dict with total, valid, invalid, success rate
    """
    n_total = len(df)
    n_valid = 0
    n_invalid = 0
    results = []

    for i, row in df.iterrows():
        note = row[text_col]
        success = False

        for attempt in range(max_retries):
            result = extractor.extract_clinical_information(note)
            try:
                result_json = json.loads(result)
                results.append(result_json)
                n_valid += 1
                success = True
                break
            except Exception as e:
                print(f"Note {i} attempt {attempt+1} failed: {e}")

        if not success:
            n_invalid += 1

    summary = {
        "total": n_total,
        "valid": n_valid,
        "invalid": n_invalid,
        "success_rate": round(100.0 * n_valid / n_total, 1),
        "provider": extractor.provider.value,
    }

    print(f"\n=== {extractor.provider.value.upper()} Extraction Evaluation ===")
    print(f"Processed: {n_total}")
    print(f"Valid JSON: {n_valid}")
    print(f"Invalid JSON (after retries): {n_invalid}")
    print(f"Success rate: {summary['success_rate']}%")

    return results, summary
