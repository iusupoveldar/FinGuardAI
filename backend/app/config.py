import os
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
RISK_MODEL_VERSION = os.getenv("RISK_MODEL_VERSION", "logistic_regression_v2")
RISK_FEATURE_VERSION = os.getenv("RISK_FEATURE_VERSION", "transaction_features_v1")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is required. Copy backend/.env.example to backend/.env "
        "and provide a PostgreSQL connection URL."
    )
