TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "flag_labs",
            "description": "Flag labs outside demo ranges.",
            "parameters": {
                "type": "object",
                "properties": {"labs": {"type": "array", "items": {"type": "object"}}},
                "required": ["labs"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "followup_gap",
            "description": "Calculates time to earliest followup",
            "parameters": {
                "type": "object",
                "properties": {
                    "discharge_date": {"type": "string", "items": {"type": "object"}},
                    "appts": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["discharge_date", "appts"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "umls_normalize",
            "description": "Normalize diagnosis/problem strings to UMLS CUIs. Clean and separate diagnoses first - extract individual conditions from complex strings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "terms": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of CLEAN, individual clinical conditions (e.g., 'femoral neck fracture', 'duodenal ulcer', 'acute blood loss anemia'). Remove abbreviations like 's/p', '2/2', split compound diagnoses.",
                    }
                },
                "required": ["terms"],
            },
        },
    },
]
