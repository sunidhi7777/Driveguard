# DriveGuard

**Hard Drive Reliability & Warranty Risk Platform with an AI Audit Agent**

DriveGuard is a portfolio-ready storage fleet dashboard for inspecting SMART indicators, screening drives for elevated risk, and prioritizing warranty review. It pairs a React dashboard with a FastAPI service and a reproducible sample fleet.

> **Scoring note:** The included score is a transparent heuristic for triage. It is not a calibrated probability of failure, a survival model, or a warranty determination. The example data are synthetic.

## Features

- Fleet overview with health counts, risk index, estimated at-risk replacement exposure, and descriptive failure-rate cohorts.
- Drive search and status filtering, per-drive SMART signal summaries, and CSV export.
- Warranty audit queue with risk reasons, remaining coverage estimate, and downloadable JSON report.
- CSV upload validation with preview; uploaded records are intentionally not persisted in this starter.
- Single-drive scoring endpoint for integrating a calibrated model later.
- API docs at `/docs` when the backend is running.

## Stack

- React, Vite, Recharts, Lucide
- Python, FastAPI, Pydantic
- CSV seed data for a zero-setup demo

## Run locally

### Backend

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000
```

### Frontend

In another terminal:

```powershell
npm install
npm run dev
```

Open the Vite URL printed in the terminal. Vite proxies `/api` calls to `http://localhost:8000`.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/summary` | Fleet KPIs and status distribution |
| GET | `/api/drives` | Drive inventory; optional `search` and `status` query parameters |
| GET | `/api/trends` | Descriptive workload cohorts |
| GET | `/api/audit` | Explainable flagged-drive audit |
| POST | `/api/drives/score` | Screen one drive's SMART signals |
| POST | `/api/drives/import` | Validate and preview a CSV upload |

### CSV schema

Required columns: `serial`, `model`, `capacity_tb`, `purchase_date` (`YYYY-MM-DD`), `warranty_months`, `power_on_hours`, `temperature_c`, `reallocated_sectors`, `pending_sectors`, `read_error_rate`, `replacement_cost`. Optional `failure` accepts `true`/`false` and is used only for the descriptive sample cohort.

## Production roadmap

1. Replace the heuristic with a time-aware, censored survival model trained on documented data; report calibration and validation cohorts.
2. Persist telemetry and warranty events in PostgreSQL with migrations, authentication, tenant isolation, and audit history.
3. Add ingestion jobs, drift monitoring, alert delivery, model cards, and human-reviewed warranty decisions.
4. Add a retrieval-grounded audit assistant with source citations and strict read-only tools before introducing agent workflows.

## Project layout

```text
api/main.py       FastAPI endpoints and explainable screening logic
data/drives.csv   Synthetic demo fleet
src/main.jsx      React dashboard
src/style.css     Dashboard styles
```

## License

MIT. See [LICENSE](LICENSE).
