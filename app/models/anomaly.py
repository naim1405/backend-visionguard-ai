"""
Anomaly Models
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Index, Float, Text, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base
import enum


class AnomalyStatus(str, enum.Enum):
    """Anomaly status enum"""
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


class AnomalySeverity(str, enum.Enum):
    """Anomaly severity enum"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Anomaly(Base):
    """
    Anomaly model - represents detected anomalies/incidents
    
    Relationships:
    - Belongs to one Shop (shop relationship)
    - Can be resolved by one User (resolver relationship)
    """
    __tablename__ = "anomalies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Core anomaly information
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    location = Column(String(255), nullable=False)
    severity = Column(Enum(AnomalySeverity), nullable=False, index=True)
    status = Column(Enum(AnomalyStatus), nullable=False, default=AnomalyStatus.PENDING, index=True)
    description = Column(Text, nullable=False)
    image_url = Column(String(500), nullable=True)  # Path/URL to saved frame
    
    # Additional details
    anomaly_type = Column(String(100), nullable=True, index=True)  # e.g., "suspicious_behavior", "fall_detection"
    confidence_score = Column(Float, nullable=True)  # AI model confidence (0.0 - 1.0)
    
    # Resolution tracking
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)  # Additional notes/comments
    
    # Flexible metadata storage
    extra_data = Column(JSONB, nullable=True)  # JSON field for extra AI outputs, bounding boxes, etc.
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    shop = relationship("Shop", backref="anomalies")
    resolver = relationship("User", foreign_keys=[resolved_by], backref="resolved_anomalies")

    # Indexes for common queries
    __table_args__ = (
        Index("ix_anomaly_shop_timestamp", "shop_id", "timestamp"),
        Index("ix_anomaly_shop_status", "shop_id", "status"),
        Index("ix_anomaly_severity_status", "severity", "status"),
    )

    def __repr__(self):
        return f"<Anomaly(id={self.id}, shop_id={self.shop_id}, severity={self.severity}, status={self.status})>"
