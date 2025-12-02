"""
Anomaly Training Data Models
Stores pose_dict inputs and user feedback for reinforcement learning
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Index, Float, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base


class AnomalyTrainingData(Base):
    """
    Stores anomaly detection inputs (pose_dict) and user feedback
    for reinforcement learning and model retraining
    
    Relationships:
    - Belongs to one Anomaly (anomaly relationship)
    - Can be labeled by one User (labeled_by relationship)
    """
    __tablename__ = "anomaly_training_data"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    anomaly_id = Column(UUID(as_uuid=True), ForeignKey("anomalies.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Core training data
    pose_dict = Column(JSONB, nullable=False)  # The actual pose_dict input from frame_buffer
    stream_id = Column(String(255), nullable=False, index=True)
    frame_number = Column(Float, nullable=False)  # Frame number when detected
    
    # Original prediction
    predicted_score = Column(Float, nullable=False)  # Original anomaly score
    predicted_confidence = Column(String(50), nullable=False)  # "High", "Medium", "Low"
    predicted_label = Column(String(100), nullable=True)  # Classification if available
    
    # User feedback for reinforcement learning
    user_feedback = Column(String(50), nullable=True, index=True)  # "true_positive", "false_positive", "uncertain"
    user_label = Column(String(100), nullable=True)  # User's classification/label
    user_notes = Column(Text, nullable=True)  # Additional notes from user
    labeled_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    labeled_at = Column(DateTime, nullable=True)
    
    # Training metadata
    used_for_training = Column(Boolean, default=False, index=True)  # Flag if used in model retraining
    training_batch_id = Column(String(100), nullable=True, index=True)  # Track which training batch used this
    
    # Additional metadata
    extra_metadata = Column(JSONB, nullable=True)  # For any additional context (bbox, tracking_data, etc.)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    anomaly = relationship("Anomaly", backref="training_data")
    labeler = relationship("User", foreign_keys=[labeled_by], backref="labeled_training_data")

    # Indexes for common queries
    __table_args__ = (
        Index("ix_training_data_feedback", "user_feedback"),
        Index("ix_training_data_used_for_training", "used_for_training", "created_at"),
        Index("ix_training_data_stream_frame", "stream_id", "frame_number"),
    )

    def __repr__(self):
        return f"<AnomalyTrainingData(id={self.id}, anomaly_id={self.anomaly_id}, feedback={self.user_feedback})>"
