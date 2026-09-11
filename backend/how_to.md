# Run FinGuardAI locally

Prerequisites: Python 3.11+, Node.js 20.19+ (or 22.12+), npm, Docker Desktop,
and Docker Compose.

## 1. Start the database

Open PowerShell in the project root:

```powershell
cd backend
Copy-Item .env.example .env
docker compose up -d
```

Create a Python virtual environment, install the backend packages, create the
tables, and import the sample AMLSim data:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m scripts.create_tables
python -m data_gen.etl.import_amlsim
```

The import command is safe to run again when the same dataset was already
imported. To intentionally replace the imported data, run:

```powershell
python -m data_gen.etl.import_amlsim --replace
```

## 2. Start the FastAPI server

From the `backend` directory, with the virtual environment activated:

```powershell
uvicorn main:app --reload --host 127.0.0.1 --port 9000
```

The API is available at http://localhost:9000 and its interactive Swagger docs
are at http://localhost:9000/docs.

## 3. Start the React frontend

Keep FastAPI running. Open a second PowerShell terminal in the project root:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Open http://localhost:4444. Vite automatically forwards frontend requests from
`/api` to FastAPI at `http://127.0.0.1:9000`, so no additional connection setup
is required.

The two development servers work together like this:

```text
Browser (localhost:4444) -> Vite /api proxy -> FastAPI (127.0.0.1:9000)
```

If port 9000 is unavailable, change the `target` in `frontend/vite.config.js`
to the port used by Uvicorn and restart `npm run dev`.

## Optional database commands

Open a PostgreSQL shell:

```powershell
docker exec -it finguard-database psql -U finguard -d finguard
```

Useful checks from inside that shell:

```sql
\dt
SELECT COUNT(*) FROM customers;
SELECT COUNT(*) FROM accounts;
SELECT COUNT(*) FROM transactions;
SELECT COUNT(*) FROM alerts;
SELECT COUNT(*) FROM alert_transactions;
SELECT status, row_counts FROM import_runs ORDER BY started_at DESC;
```

Development-only full database reset and reimport (destructive):

```powershell
python -m app.database.recreate_import
```
