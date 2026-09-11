from app.database.connection import session_local
from app.models.customer import Customer
from app.services.investigation_service import investigate_customer


from fastapi import APIRouter


router = APIRouter(
    prefix="/investigate",
    tags=["Investigation"]
)

@router.post("/{customer_id}")
async def investigate(customer_id: int):
    res = investigate_customer(customer_id=customer_id)
    return res