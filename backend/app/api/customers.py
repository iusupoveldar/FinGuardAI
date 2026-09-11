from app.database.connection import SessionLocal
from app.models.customer import Customer

from app.schemas.customer import CustomersResponse

from fastapi import APIRouter


router = APIRouter(
    prefix="/customers",
    tags=["Customers"]
)

@router.get("/", response_model = CustomersResponse)
async def get_customers():
    db = SessionLocal()

    customers = db.query(Customer).all()

    db.close()

    return customers