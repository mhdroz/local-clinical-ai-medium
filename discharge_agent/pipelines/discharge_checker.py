import requests
import json
from discharge_agent.tools.labs import flag_labs
from discharge_agent.tools.followup import followup_gap
from discharge_agent.tools.umls_client import normalize_terms_to_cui
from discharge_agent.llm.tool_specs import TOOLS
from dotenv import load_dotenv
import os

load_dotenv()

API = os.getenv("LLM_API")
MODEL = os.getenv("MODEL")


def chat(payload):
    r = requests.post(API, json=payload, timeout=120)
    r.raise_for_status()
    return r.json()


def check_discharge_safety(messages):
    for _ in range(5):  # safety cap
        resp = chat(
            {"model": MODEL, "messages": messages, "tools": TOOLS, "stream": False}
        )
        msg = resp.get("message", {})
        tool_calls = msg.get("tool_calls") or []
        # If the model asked to call tools, run them and send tool results
        if tool_calls:
            # include the assistant message that requested tools
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.get("content", ""),
                    "tool_calls": tool_calls,
                }
            )
            for call in tool_calls:
                print(call)
                fn = call["function"]["name"]
                args = call["function"].get("arguments") or {}
                if fn == "flag_labs":
                    result = flag_labs(**args)
                elif fn == "followup_gap":
                    result = followup_gap(**args)
                elif fn == "umls_normalize":
                    result = normalize_terms_to_cui(**args)
                else:
                    result = {"error": f"unknown tool {fn}"}
                messages.append(
                    {"role": "tool", "name": fn, "content": json.dumps(result)}
                )
            continue
        # Otherwise, we should have the final answer
        final = (msg.get("content") or "").strip()
        print(final)
        break
    return final
