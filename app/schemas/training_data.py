"""
Training Data Schemas
Pydantic models for anomaly training data API requests and responses
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID


class TrainingDataBase(BaseModel):
    """Base training data schema"""
    anomaly_id: UUID
    stream_id: str
    frame_number: float


class TrainingDataCreate(TrainingDataBase):
    """Schema for creating training data"""
    pose_dict: Dict[str, Any]
    predicted_score: float
    predicted_confidence: str
    predicted_label: Optional[str] = None
    extra_metadata: Optional[Dict[str, Any]] = None


class TrainingDataFeedback(BaseModel):
    """Schema for updating training data with user feedback"""
    user_feedback: str = Field(..., description="User feedback: true_positive, false_positive, uncertain")
    user_label: Optional[str] = Field(None, description="User's classification/label")
    user_notes: Optional[str] = Field(None, description="Additional notes from user")


class TrainingDataResponse(BaseModel):
    """Schema for training data response"""
    id: UUID
    anomaly_id: UUID
    pose_dict: Dict[str, Any]
    stream_id: str
    frame_number: float
    predicted_score: float
    predicted_confidence: str
    predicted_label: Optional[str]
    user_feedback: Optional[str]
    user_label: Optional[str]
    user_notes: Optional[str]
    labeled_by: Optional[UUID]
    labeled_at: Optional[datetime]
    used_for_training: bool
    training_batch_id: Optional[str]
    extra_metadata: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TrainingDataListResponse(BaseModel):
    """Schema for list of training data"""
    total: int
    items: list[TrainingDataResponse]


class TrainingDataStats(BaseModel):
    """Schema for training data statistics"""
    total: int
    with_feedback: int
    true_positives: int
    false_positives: int
    uncertain: int
    used_for_training: int
    available_for_training: int
