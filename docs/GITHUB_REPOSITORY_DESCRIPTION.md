# GitHub Repository Description

## Repository Name

```text
ecommerce-after-sales-agent
```

## One-line Description

An engineering-focused simulated e-commerce after-sales Agent with tool calling, policy RAG, evaluation, FastAPI, and safety boundaries.

## GitHub About Description

Simulated e-commerce after-sales Agent built with Python, LangGraph-style workflow concepts, SQLite tools, deterministic refund rules, BM25/Dense/Hybrid policy retrieval, traceable Policy QA, FastAPI, and local evaluation scripts.

## Topics

```text
langgraph
rag
fastapi
faiss
bm25
agent
llm
python
sqlite
tool-calling
evaluation
```

## README Top Summary

```markdown
This project is an interview-oriented simulated e-commerce after-sales Agent. It uses simulated orders, policies, and support tickets to demonstrate tool calling, deterministic refund eligibility rules, policy retrieval, traceable Policy QA, FastAPI acceptance checks, and evaluation-driven engineering practices. It does not use real user data or real e-commerce policies.
```

## Project Highlights

- Simulated SQLite order database and order Tool.
- Deterministic refund eligibility rule engine.
- Explicit confirmation gate before simulated ticket creation.
- Policy knowledge base with BM25, Dense FAISS, and Hybrid RRF retrieval.
- Traceable Policy QA with citation validation.
- FastAPI `/health` and `/agent/run` endpoints.
- Local evaluation artifacts for controlled Agent tasks, retrieval, live Policy QA, API acceptance, and stability checks.
- Publication evidence pack under `docs/resume_evidence/`.

## Demo Entry Points

```powershell
python scripts\init_demo_data.py
python scripts\build_all_policy_indexes.py
python -m uvicorn app.api_server:app --host 127.0.0.1 --port 8011
```

Open:

```text
http://127.0.0.1:8011/docs
```

Demo payloads:

```text
docs/resume_evidence/demo_requests.json
```

## Current Boundaries

- All orders, policies, and tickets are simulated.
- The project does not execute real refunds, real order cancellation, or real logistics changes.
- Real API keys must only live in local `.env`, never in Git.
- Dockerfile exists, but Docker build and `/health` verification are currently marked as not verified in this environment.
- Evaluation metrics come from controlled local datasets and should not be described as production performance.
