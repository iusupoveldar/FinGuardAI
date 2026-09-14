from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Register all ORM models before the first database query configures mappers.
import app.models  # noqa: F401
from app.api import customers
from app.api import investigation
from app.api import policies
from app.api import transactions

app = FastAPI(
    title = "FinGuard AI",
    description= "AML Investigation Assistant."
)

# Allow the local React development server to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4444",
        "http://127.0.0.1:4444",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(customers.router)
app.include_router(transactions.router)
app.include_router(investigation.router)
app.include_router(policies.router)

@app.get("/")
async def root():
    return {"message": "FinGuard AI API running"}
