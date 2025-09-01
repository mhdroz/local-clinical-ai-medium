# Clinical Data Extraction & Local Discharge Agent with GPT-OSS

Testing local healthcare AI workflows with OpenAI’s open-weight models — from raw note extraction to actionable discharge readiness checks — all running offline on your laptop.

## Overview

This repository builds on my blog posts:
-  [I Ran OpenAI’s New Open Model on My Laptop to Extract Medical Data — Here’s What Happened](https://medium.com/towards-artificial-intelligence/i-ran-openais-new-open-model-on-my-laptop-to-extract-medical-data-here-s-what-happened-aeb6acddfede)
-  [I Built a Local Clinical AI Agent from Scratch - Here's How]()

It contains:

1. Synthetic discharge notes
2. A discharge agent: small Python tools for:
  - Abnormal lab detection
  - Follow-up gap checks
  - Diagnosis normalization (UMLS / demo lexicon)
3. End-to-end workflow → from text note ➝ structured JSON ➝ readiness decision

All notes are synthetic, no real patient data.

## Contents

- `data/synthetic_notes.csv` — 10 synthetic discharge summaries
- `discharge_agent/extractions` - code and prompts for information extraction from raw notes
- `discharge_agent/llm` — prompt templates and tools specs
- `discharge_agent/pieplines` - orchestration code
- `discharge_agent/tools` - labs, date reasoning, UMLS normalization
- `discharge_agent_example.ipynb` - end to end example

## Quickstart
use the `.env_template` to create your own `.env` with your UMLS API key or leave it empty to use the provided demo mappings

## Synthetic Clinical Notes

All clinical notes in this repository are **completely synthetic** and created for demonstration purposes. No real patient data was used. These examples are designed to showcase clinical AI extraction capabilities while maintaining complete privacy.

The synthetic notes include realistic:
- Patient demographics and contact information
- Medical histories and clinical terminology
- Medication regimens and dosing
- Lab values and diagnostic procedures
- Provider information and follow-up scheduling

## Note on Privacy

This approach demonstrates healthcare AI that preserves patient privacy by running entirely on local hardware. No patient information ever leaves your environment.

## Contributing

This is an early exploration. 

Contributions welcome — whether it’s:

- Adding new tools (e.g., vitals stability, RxNorm for meds)
- Improving normalization
- Expanding the synthetic dataset

## Questions or feedback?

Let’s connect on [LinkedIn](https://www.linkedin.com/in/marie-humbert-droz/)
