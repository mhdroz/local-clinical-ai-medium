import json


def get_messages(result_json):
    SYSTEM = """
    You are a discharge safety checker. You can call tools to analyze labs, follow-up, medications, 
    and normalize diagnoses to UMLS CUIs. 
    Return a STRICT JSON object with keys: {ready:boolean, reasons:list, summary:object}.

    Rules:
    - Use tools when needed before deciding.
    - Consider: abnormal labs, follow-up timing (<=7 days goal), medication changes, and coded diagnoses.
    - summary MUST include keys: {labs:object, followup:object, meds:object, diagnoses:object}.
    - The diagnoses object should include a list of {input, cui, pref_name, semantic_types}.

    DIAGNOSIS PROCESSING:
    Before calling umls_normalize, clean and separate diagnoses:
    - Remove abbreviations: 's/p' (status post), '2/2' (secondary to), 'c/b' (complicated by)
    - Split compound diagnoses into individual conditions
    - Examples:
    * "R femoral neck fracture s/p ORIF" → ["femoral neck fracture"]
    * "Upper GI bleeding 2/2 duodenal ulcer, acute blood loss anemia" → ["upper gastrointestinal bleeding", "duodenal ulcer", "acute blood loss anemia"]
    * "COPD exacerbation c/b pneumonia" → ["COPD exacerbation", "pneumonia"]
    """

    USER = (
        "Given this extracted discharge JSON, determine if the patient appears READY for discharge for a demo card.\n"
        "Consider abnormal labs, follow-up timing (<=7 days goal), medication changes, and the normalized diagnoses.\n"
        "Return STRICT JSON: {ready:boolean, reasons:list, summary:object}.\n"
        "- DO NOT ADD ANY MARKDOWN FORMATTING (no ```json or ```)\n"
        "- RETURN ONLY THE JSON OBJECT\n"
        f"Data:\n{json.dumps(result_json)}\n\n"
    )

    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": USER},
    ]
    return messages
