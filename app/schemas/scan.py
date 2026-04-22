from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class TopPrediction(BaseModel):
    class_name: str
    confidence: float

class PredictionResponse(BaseModel):
    predicted_class: str
    confidence: float
    top3: List[TopPrediction]

class ScanResponse(BaseModel):
    id: int
    patient_id: int
    doctor_id: Optional[int] = None
    image_url: str
    scan_name: str
    upload_date: datetime
    ai_diagnosis: Optional[str] = None
    ai_confidence: Optional[float] = None
    final_diagnosis: Optional[str] = None
    risk_level: str
    status: str
    doctor_notes: Optional[str] = None

    class Config:
        from_attributes = True

class ScanPredictionResponse(BaseModel):
    scan: ScanResponse
    prediction: PredictionResponse

class ScanVerifyRequest(BaseModel):
    final_diagnosis: str
    risk_level: str
    status: str
    doctor_notes: Optional[str] = None
