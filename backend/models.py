from pydantic import BaseModel
from typing import Optional


class UploadResponse(BaseModel):
    total_cases_detected: int
    pages_processed: int
    extraction_time: float
    engine_used: str


class CaseResponse(BaseModel):
    sno: int
    content: str
    page_number: Optional[int] = None
