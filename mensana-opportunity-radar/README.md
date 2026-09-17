# Mensana Opportunity Radar — Local MVP

Mensana Opportunity Radar ranks Canadian and U.S. companies using explainable business signals, keeps public contact details beside each lead, logs outreach, prevents repeat calls, and learns from confirmed call outcomes. Everything runs locally and uses no paid API.

## Fastest start on Windows

1. Right-click `INSTALL-AND-START.ps1` and choose **Run with PowerShell**.
2. The script downloads Git and Docker Desktop from their official Windows package sources when needed, initializes version history, and starts the application.
3. On later launches, simply double-click `START-MENSANA.bat`.
4. Open <http://localhost:8000> (the launcher normally opens it for you).

The first launch builds the app and creates a local database. Demo companies are included so every screen can be tested immediately.

## What V0.1 does

- Ranked lead queue with Canada/U.S., search, industry, score, and contactability filters.
- Explainable 100-point score: financial (30), operational (20), transformation (20), document/language (20), and fit (10).
- Company profile with evidence, website, public phone, contact role/person, source, and verification date.
- Call logging with reached/voicemail/no-answer/wrong-number outcomes.
- A company leaves the new-lead queue as soon as any call is saved, preventing accidental repeat outreach.
- Follow-ups live in their own queue. Closed, opportunity, client, and do-not-contact records remain searchable in History.
- Only confirmed Yes/No outcomes become ML labels. Voicemail and unanswered calls never become false negatives.
- Local logistic-regression retraining after enough labels; a candidate model is accepted only when evaluation is possible and does not regress.
- CSV import/export and an optional SEC public-data importer.
- Audit log and duplicate matching by SEC CIK, normalized domain, ticker/country, and normalized legal name/country.

## Without Docker

Requires Python 3.11+.

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m app.seed
uvicorn app.main:app --reload --port 8000
```

## Import companies

Use **Data → Import CSV** in the app. Start with `data/company-import-template.csv`. Existing companies are updated instead of duplicated.

For free U.S. public data, use **Data → SEC import**, enter a real contact identity (the SEC requests an identifying User-Agent), and provide CIKs. The importer retrieves SEC submissions and company facts with conservative pacing. It does not scrape search results or bypass access rules.

Canadian public filing ingestion is deliberately CSV-first in this MVP because SEDAR+ does not provide an equivalent unrestricted bulk issuer API. Publicly obtained issuer facts can still be imported using the same template, with source URLs retained.

## Run tests

```bash
docker compose run --rm app pytest
```

or locally:

```bash
pytest
```

## Important limits

The score is a prioritization aid, not a factual claim that a company needs consulting. Phone/email fields display their source and verification status; the application never invents direct contact information. Comply with privacy, telemarketing, securities-data, website, and internal outreach policies before contacting anyone.

## Project map

- `app/main.py` — API and web server.
- `app/database.py` — SQLite setup and safe transaction helpers.
- `app/services.py` — scoring, duplicate resolution, call workflow, and dashboard queries.
- `app/ml.py` — local feedback model training and prediction.
- `app/sec_importer.py` — free SEC HTTP importer.
- `app/static/` — browser interface.
- `tests/` — automated workflow tests.
- `START-MENSANA.bat` — one-click Windows launcher.
- `INSTALL-AND-START.ps1` — retrieves prerequisites, initializes Git, and launches the app.

## Future edits

This repository is the source of truth. Future changes can be applied as small replacement blocks or patches and committed with Git, so you never need to juggle multiple downloaded copies.
