# Clinical Data Extraction & Local Discharge Agent with GPT-OSS

Testing local healthcare AI workflows with OpenAI’s open-weight models — from raw note extraction to actionable discharge readiness checks — all running offline on your laptop.

## Overview

This repository builds on my blog posts:
-  [I Ran OpenAI’s New Open Model on My Laptop to Extract Medical Data — Here’s What Happened](https://medium.com/towards-artificial-intelligence/i-ran-openais-new-open-model-on-my-laptop-to-extract-medical-data-here-s-what-happened-aeb6acddfede)
-  [I Built a Local Clinical AI Agent from Scratch - Here's How](https://medium.com/towards-artificial-intelligence/i-built-a-local-clinical-ai-agent-from-scratch-heres-how-90783c59afdc)
-  [Do AI Agents Really Use the Tools You Build for Them? I Tested It.](https://medium.com/towards-artificial-intelligence/i-built-a-clinical-ai-agent-and-it-skipped-the-tools-i-gave-it-d9d7c3d25051)
-  [Can Local AI Keep Up with the Cloud? I Tested 8 Models on Clinical Data](https://medium.com/towards-artificial-intelligence/can-local-ai-keep-up-with-the-cloud-i-tested-8-models-on-clinical-data-739e23b71a65)

It contains:

1. Synthetic discharge notes
2. A discharge agent: small Python tools for:
  - Abnormal lab detection
  - Follow-up gap checks
  - Diagnosis normalization (UMLS / demo lexicon)
3. End-to-end workflow → from text note ➝ structured JSON ➝ readiness decision
4. Tool use evaluation framework
5. Simple benchmark framework to compare the extraction quality between various LLMs
6. Agent observability: self-hosted Langfuse tracing with in-process PHI redaction
   (Presidio), plus a redaction-quality / debuggability experiment suite

All notes are synthetic, no real patient data.

## Contents

- `data/synthetic_notes.csv` — 10 synthetic discharge summaries
- `data/phi_ground_truth.json` — exact PHI spans per note (redaction eval ground truth)
- `discharge_agent/extractions` - code and prompts for information extraction from raw notes
- `discharge_agent/llm` — prompt templates and tools specs
- `discharge_agent/pipelines` - agent loop (tool-calling orchestration)
- `discharge_agent/pipeline.py` + `discharge_agent/run.py` - end-to-end pipeline module and CLI
- `discharge_agent/tracing` - Langfuse instrumentation (generation/tool/agent spans)
- `discharge_agent/redaction` - Presidio masking layer wired into the Langfuse `mask` callback
- `discharge_agent/tools` - labs, date reasoning, UMLS normalization
- `discharge_agent/evaluation` - benchmark code
- `experiments/` - tracing + redaction experiment scripts (see `results/EXPERIMENT_SUMMARY.md`)
- `docker/langfuse/` - self-hosted Langfuse v3 compose (localhost-only)
- `discharge_agent_example.ipynb` - end to end example
- `extraction_benchmark.ipynb` - end to end benchmark
- `tracing_redaction_demo.ipynb` - tracing + redaction demo

## Quickstart
use the `.env_template` to create your own `.env` with your UMLS API key or leave it empty to use the provided demo mappings

## Tracing + PHI redaction (post #5)

Everything runs locally: Ollama serves the model, Langfuse (self-hosted in
Docker) stores traces, and PHI is masked **in-process** before any span leaves
the agent — the model sees the full note, the telemetry never does.

```bash
# 1. Langfuse (first boot provisions org/project/API keys headlessly)
cd docker/langfuse && cp .env.example .env   # edit secrets
docker compose up -d                          # UI at http://127.0.0.1:3000

# 2. Python deps
pip install -r requirements.txt
python -m spacy download en_core_web_lg

# 3. copy LANGFUSE_* keys into the repo-root .env (see .env_template), then:
python -m discharge_agent.run --note-id 1 --redaction on
python -m discharge_agent.run --note-id 1 --redaction off   # A/B the same note

# experiments (redaction quality, debuggability, fix iteration)
python -m experiments.run_all_notes --redaction on
python -m experiments.run_redaction_eval
python -m experiments.run_redaction_eval --policy v2
python -m experiments.run_iteration_comparison
```

Results and the honest findings live in `results/EXPERIMENT_SUMMARY.md`.

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

Interested in collaborating or working on a healthcare AI project? [Visit my website](https://www.mhd-ai.com/) to get in touch or book a call.
