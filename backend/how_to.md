# Local database workflow

# Start Docker after starting Docker Desktop
docker compose up -d

# From the backend folder, apply reviewed migrations

python -m scripts.create_tables

# Import the AMLSim data. An identical completed dataset is a no-op.
python -m data_gen.etl.import_amlsim

# Intentionally replace existing imported data
python -m data_gen.etl.import_amlsim --replace

# Check the database
docker exec -it finguard-database psql -U finguard -d finguard
\dt

# Development-only full reset (destructive)
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;


# Verify Tables
SELECT COUNT(*) FROM customers;

SELECT COUNT(*) FROM accounts;

SELECT COUNT(*) FROM transactions;

SELECT COUNT(*) FROM alerts;

SELECT COUNT(*) FROM alert_transactions;

SELECT status, row_counts FROM import_runs ORDER BY started_at DESC;
