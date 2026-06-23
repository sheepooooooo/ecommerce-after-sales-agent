# Contributing

Thanks for your interest in this simulated e-commerce after-sales Agent project.

## Python Version

Use Python 3.10 or newer. The Dockerfile currently uses `python:3.10-slim`.

## Install Dependencies

```powershell
python -m pip install -r requirements.txt
```

## Initialize Data

```powershell
python scripts\init_demo_data.py
python scripts\build_all_policy_indexes.py
```

## Run Tests

```powershell
python -m pytest -q
python scripts\run_full_checks.py
```

## Issues

When opening an issue, include:

- What command you ran.
- Expected behavior.
- Actual behavior.
- Relevant error message with secrets removed.
- Whether `.env` or external API access was required.

## Security and Data Rules

Do not commit:

- `.env`
- API keys
- account credentials
- real user data
- real order data
- real customer service records
- unreviewed logs

All policies, orders, and tickets in this project are simulated and are intended for learning, evaluation, and interview demonstration only.
