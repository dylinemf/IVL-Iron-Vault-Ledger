from pydantic import BaseModel, Field

# Schema for API input
class TransactionRequest(BaseModel):
    debit_id: int = Field(..., description="ID of the debit account.")
    credit_id: int = Field(..., description="ID of the credit account.")
    amount: float = Field(..., gt=0, description="Amount of the transaction. Must be greater than 0.")
    description: str = Field(..., min_length=5, max_length=500, description="Description of the transaction.")
