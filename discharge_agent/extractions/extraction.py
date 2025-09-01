import requests, json
from discharge_agent.extractions.prompts import system_prompt, get_user_prompt
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
