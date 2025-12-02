"""
Anomaly Schemas
Pydantic models for anomaly API requests and responses
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


class AnomalyBase(BaseModel):
    """Base anomaly schema"""
    shop_id: UUID
    location: str
    severity: str
    description: str
    anomaly_type: Optional[str] = None


class AnomalyCreate(AnomalyBase):
    """Schema for creating an anomaly"""
    image_url: Optional[str] = None
    confidence_score: Optional[float] = None
    extra_data: Optional[dict] = None


class AnomalyUpdate(BaseModel):
    """Schema for updating an anomaly"""
    status: str = Field(..., description="New status: pending, acknowledged, resolved, false_positive")
    notes: Optional[str] = Field(None, description="Additional notes")


class AnomalyResponse(BaseModel):
    """Schema for anomaly response"""
    id: UUID
    shop_id: UUID
    timestamp: datetime
    location: str
    severity: str
    status: str
    description: str
    image_url: Optional[str]
    anomaly_type: Optional[str]
    confidence_score: Optional[float]
    resolved_by: Optional[UUID]
    resolved_at: Optional[datetime]
    notes: Optional[str]
    extra_data: Optional[dict]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AnomalyListResponse(BaseModel):
    """Schema for list of anomalies"""
    total: int
    anomalies: list[AnomalyResponse]


class AnomalyStats(BaseModel):
    """Schema for anomaly statistics"""
    total: int
    recent_24h: int
    by_status: dict
    by_severity: dict
