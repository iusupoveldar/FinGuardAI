from pydantic import BaseModel

class CustomersResponse(BaseModel):
    id: int
    name: str
    country: str
    risk: int

    class Config:
        from_attributes = True