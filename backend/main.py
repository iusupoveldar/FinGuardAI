from fastapi import FastAPI
from app.api import customers
from app.api import transactions
from app.api import investigation

app = FastAPI(
    title = "FinGuard AI",
    description= "AML Investigation Assistant."
)

app.include_router(customers.router)
app.include_router(transactions.router)
app.include_router(investigation.router)

@app.get("/")
async def root():
    return {"message": "FinGuard AI API running"}