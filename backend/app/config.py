import os
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_ENABLED = os.getenv("DEEPSEEK_ENABLED", "false").lower() in {
    "1",
    "true",
    "yes",
}
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
DEEPSEEK_TIMEOUT_SECONDS = float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "20"))
DEEPSEEK_MAX_OUTPUT_TOKENS = int(os.getenv("DEEPSEEK_MAX_OUTPUT_TOKENS", "900"))
DEEPSEEK_DAILY_BUDGET_USD = float(os.getenv("DEEPSEEK_DAILY_BUDGET_USD", "0"))
DEEPSEEK_CACHE_HIT_RATE = float(os.getenv("DEEPSEEK_CACHE_HIT_RATE", "0"))
DEEPSEEK_CACHE_MISS_RATE = float(os.getenv("DEEPSEEK_CACHE_MISS_RATE", "0"))
DEEPSEEK_OUTPUT_RATE = float(os.getenv("DEEPSEEK_OUTPUT_RATE", "0"))
DEEPSEEK_PRICING_VERSION = os.getenv("DEEPSEEK_PRICING_VERSION", "unconfigured")
RISK_MODEL_VERSION = os.getenv("RISK_MODEL_VERSION", "logistic_regression_v2")
RISK_FEATURE_VERSION = os.getenv("RISK_FEATURE_VERSION", "transaction_features_v1")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is required. Copy backend/.env.example to backend/.env "
        "and provide a PostgreSQL connection URL."
    )
