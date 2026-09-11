# Run Docker after starting docker desktop
docker compose up -d


# How to create db from backend folder run 

python -m scripts.create_tables
python -m data_gen.etl.import_amlsim

# Check if worked
docker exec -it finguard-database psql -U finguard -d finguard
\dt

# Reset DB
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;


# Verify Tables