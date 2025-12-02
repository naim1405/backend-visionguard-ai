"""
Training Data API Endpoints
API routes for managing anomaly training data and user feedback
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from app.db import get_db
from app.models import User
from app.services.anomaly_service import AnomalyService
from app.schemas.training_data import (
    TrainingDataResponse,
    TrainingDataListResponse,
    TrainingDataFeedback,
    TrainingDataStats
)
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/api/training-data", tags=["training-data"])


@router.get("", response_model=TrainingDataListResponse)
async def get_training_data(
    user_feedback: Optional[str] = Query(None, description="Filter by feedback: true_positive, false_positive, uncertain"),
    used_for_training: Optional[bool] = Query(False, description="Filter by training status"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get training data for reinforcement learning
    Admin only endpoint to retrieve training samples
    """
    # TODO: Add admin role check
    # if current_user.role != UserRole.ADMIN:
    #     raise HTTPException(status_code=403, detail="Admin access required")
    
    items = AnomalyService.get_training_data_for_retraining(
        db=db,
        user_feedback=user_feedback,
        used_for_training=used_for_training,
        limit=limit,
        offset=offset
    )
    
    # Get total count
    from app.models.training_data import AnomalyTrainingData
    query = db.query(AnomalyTrainingData)
    if user_feedback:
        query = query.filter(AnomalyTrainingData.user_feedback == user_feedback)
    query = query.filter(AnomalyTrainingData.used_for_training == used_for_training)
    total = query.count()
    
    return TrainingDataListResponse(total=total, items=items)


@router.put("/{training_data_id}/feedback", response_model=TrainingDataResponse)
async def update_training_data_feedback(
    training_data_id: UUID,
    feedback: TrainingDataFeedback,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update training data with user feedback
    
    User feedback options:
    - true_positive: Correctly detected anomaly
    - false_positive: Incorrectly flagged as anomaly
    - uncertain: User is unsure
    
    This endpoint allows users to provide feedback on anomaly detections,
    which will be used for reinforcement learning to improve the model.
    """
    training_data = AnomalyService.update_training_data_feedback(
        db=db,
        training_data_id=training_data_id,
        user_feedback=feedback.user_feedback,
        labeled_by=current_user.id,
        user_label=feedback.user_label,
        user_notes=feedback.user_notes
    )
    
    if not training_data:
        raise HTTPException(status_code=404, detail="Training data not found")
    
    return training_data


@router.get("/stats", response_model=TrainingDataStats)
async def get_training_data_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get statistics about training data
    Admin only endpoint
    """
    # TODO: Add admin role check
    
    from app.models.training_data import AnomalyTrainingData
    
    total = db.query(AnomalyTrainingData).count()
    with_feedback = db.query(AnomalyTrainingData).filter(
        AnomalyTrainingData.user_feedback.isnot(None)
    ).count()
    
    true_positives = db.query(AnomalyTrainingData).filter(
        AnomalyTrainingData.user_feedback == "true_positive"
    ).count()
    
    false_positives = db.query(AnomalyTrainingData).filter(
        AnomalyTrainingData.user_feedback == "false_positive"
    ).count()
    
    uncertain = db.query(AnomalyTrainingData).filter(
        AnomalyTrainingData.user_feedback == "uncertain"
    ).count()
    
    used_for_training = db.query(AnomalyTrainingData).filter(
        AnomalyTrainingData.used_for_training == True
    ).count()
    
    available_for_training = db.query(AnomalyTrainingData).filter(
        AnomalyTrainingData.used_for_training == False,
        AnomalyTrainingData.user_feedback.isnot(None)
    ).count()
    
    return TrainingDataStats(
        total=total,
        with_feedback=with_feedback,
        true_positives=true_positives,
        false_positives=false_positives,
        uncertain=uncertain,
        used_for_training=used_for_training,
        available_for_training=available_for_training
    )
