system_prompt = "You are a clinical data extraction assistant. Extract information exactly as written. Return only valid JSON with no commentary and no markdown formatting."


def get_user_prompt(note):
    return (
        """Extract the following from this discharge summary. Return ONLY JSON:

{
  "discharge_date": "",
  "chief_complaint": "",
  "primary_discharge_diagnosis": "",
  "procedures_performed": [],
  "discharge_condition": {"mental_status": "", "consciousness_level": "", "activity_status": ""},
  "discharge_disposition": "",
  "medication_changes": {
    "new_medications": [{"name": "", "dose": "", "frequency": ""}],
    "dose_changes": [{"name": "", "old_dose": "", "new_dose": "", "frequency": ""}]
  },
  "follow_up_appointments": [{"provider": "", "specialty": "", "date": "", "time": ""}],
  "most_recent_labs": [{"name": "", "value": "", "date": ""}]
}

INSTRUCTIONS:
- For medication_changes:
  - new_medications: medications started during admission that were NOT on admission list
  - dose_changes: medications that were on admission list but dose was modified
- For most_recent_labs: if multiple values reported for same lab, only include the LATEST value
- For follow_up_appointments: extract provider name, specialty, date and time if available
- DO NOT ADD ANY MARKDOWN FORMATTING (no ```json or ```)
- RETURN ONLY THE JSON OBJECT

"""
        + f"""Clinical note: \"\"\"{note}\"\"\"

JSON:"""
    )
