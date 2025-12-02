"""
Notification schemas for request/response validation
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class NotificationPriority(str, Enum):
    """Notification priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationType(str, Enum):
    """Types of notifications"""
    INFO = "info"
    WARNING = "warning"
    ALERT = "alert"
    SUCCESS = "success"
    ERROR = "error"


class NotificationCreate(BaseModel):
    """Schema for creating a notification"""
    user_id: str = Field(..., description="Target user ID to send notification to")
    title: str = Field(..., min_length=1, max_length=200, description="Notification title")
    message: str = Field(..., min_length=1, max_length=1000, description="Notification message")
    priority: NotificationPriority = Field(
        default=NotificationPriority.MEDIUM,
        description="Priority level of the notification"
    )
    type: NotificationType = Field(
        default=NotificationType.INFO,
        description="Type of notification"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata for the notification"
    )
    action_url: Optional[str] = Field(
        default=None,
        description="Optional URL for notification action"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "title": "Suspicious Activity Detected",
                "message": "Unusual behavior detected in Camera 3 at Store A",
                "priority": "high",
                "type": "alert",
                "metadata": {
                    "camera_id": "camera_3",
                    "shop_id": "store_a",
                    "detection_type": "loitering"
                },
                "action_url": "/suspicious-activity"
            }
        }


class NotificationResponse(BaseModel):
    """Schema for notification response"""
    success: bool = Field(..., description="Whether the notification was sent successfully")
    message: str = Field(..., description="Status message")
    user_id: str = Field(..., description="Target user ID")
    notification_id: str = Field(..., description="Unique notification ID")
    timestamp: datetime = Field(..., description="Timestamp when notification was sent")
    delivered: bool = Field(..., description="Whether user is connected and received notification")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Notification sent successfully",
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "notification_id": "notif_abc123",
                "timestamp": "2025-12-03T10:30:00",
                "delivered": True
            }
        }


class NotificationPayload(BaseModel):
    """Schema for notification payload sent via WebSocket"""
    notification_id: str = Field(..., description="Unique notification ID")
    title: str = Field(..., description="Notification title")
    message: str = Field(..., description="Notification message")
    priority: NotificationPriority = Field(..., description="Priority level")
    type: NotificationType = Field(..., description="Notification type")
    timestamp: datetime = Field(..., description="Notification timestamp")
    metadata: Optional[Dict[str, Any]] = Field(default=None)
    action_url: Optional[str] = Field(default=None)
    
    class Config:
        json_schema_extra = {
            "example": {
                "notification_id": "notif_abc123",
                "title": "New Alert",
                "message": "Suspicious activity detected",
                "priority": "high",
                "type": "alert",
                "timestamp": "2025-12-03T10:30:00",
                "metadata": {"camera_id": "cam_1"},
                "action_url": "/alerts/123"
            }
        }
