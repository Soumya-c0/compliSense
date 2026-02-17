from pydantic import BaseModel, Field, validator
from typing import Literal


class ComplianceResult(BaseModel):
    compliance_status: Literal["Compliant", "Non-Compliant", "Partially Compliant", "Unknown"]
    reason: str = Field(min_length=5)
    risk_level: Literal["Low", "Medium", "High", "Unknown"]
    confidence_score: float = Field(ge=0.0, le=1.0)

    @validator("reason")
    def reason_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Reason cannot be empty")
        return v