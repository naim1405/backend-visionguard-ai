"""
Notification API Endpoints
Handles sending notifications to users via WebSocket
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.schemas.notification import (
    NotificationCreate,
    NotificationResponse,
    NotificationPayload,
    NotificationPriority,
    NotificationType
)
from app.api.websocket import get_websocket_manager, WebSocketManager
from app.db import get_db
from app.models import User
from app.core.dependencies import get_current_user

# Configure logging
logger = logging.getLogger(__name__)

# Create FastAPI router
router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@router.post(
    "/send",
    response_model=NotificationResponse,
    summary="Send Notification to User",
    description="""
    Send a notification to a specific user via WebSocket.
    
    The notification will be delivered in real-time if the user is connected.
    
    **Priority Levels:**
    - `low`: Informational notifications
    - `medium`: Standard notifications (default)
    - `high`: Important notifications requiring attention
    - `critical`: Urgent notifications requiring immediate action
    
    **Notification Types:**
    - `info`: Informational message
    - `warning`: Warning message
    - `alert`: Alert/Danger message
    - `success`: Success message
    - `error`: Error message
    """
)
async def send_notification(
    notification: NotificationCreate,
    db: Session = Depends(get_db),
    ws_manager: WebSocketManager = Depends(get_websocket_manager),
    current_user: User = Depends(get_current_user)
):
    """
    Send a notification to a user via WebSocket
    
    Args:
        notification: Notification details
        db: Database session
        ws_manager: WebSocket manager instance
        current_user: Authenticated user sending the notification
        
    Returns:
        NotificationResponse with delivery status
        
    Raises:
        HTTPException: If user not found or notification fails
    """
    try:
        # Validate target user exists
        from uuid import UUID
        try:
            target_user = db.query(User).filter(User.id == UUID(notification.user_id)).first()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user ID format")
        
        if not target_user:
            raise HTTPException(status_code=404, detail=f"User {notification.user_id} not found")
        
        # Generate unique notification ID
        notification_id = f"notif_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now()
        
        # Create notification payload
        payload = NotificationPayload(
            notification_id=notification_id,
            title=notification.title,
            message=notification.message,
            priority=notification.priority,
            type=notification.type,
            timestamp=timestamp,
            metadata=notification.metadata,
            action_url=notification.action_url
        )
        
        # Prepare WebSocket message
        ws_message = {
            "type": "notification",
            "data": payload.model_dump(mode='json')
        }
        
        # Check if user is connected
        user_connection = ws_manager.get_connection(notification.user_id)
        delivered = user_connection is not None
        
        if delivered:
            # Send notification via WebSocket
            await ws_manager.send_message(notification.user_id, ws_message)
            logger.info(
                f"[Notification] Sent {notification.priority} notification to user {notification.user_id}: "
                f"{notification.title}"
            )
        else:
            logger.warning(
                f"[Notification] User {notification.user_id} not connected - "
                f"notification queued: {notification.title}"
            )
        
        # Return response
        return NotificationResponse(
            success=True,
            message="Notification sent successfully" if delivered else "User not connected - notification queued",
            user_id=notification.user_id,
            notification_id=notification_id,
            timestamp=timestamp,
            delivered=delivered
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Notification] Error sending notification: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send notification: {str(e)}")


@router.post(
    "/test",
    response_model=NotificationResponse,
    summary="Test Notification Endpoint",
    description="""
    Test endpoint to send a sample notification to any user.
    
    Use this endpoint to test the notification system without authentication requirements.
    Simply provide a user_id and the notification will be sent if the user is connected.
    """
)
async def test_notification(
    notification: NotificationCreate,
    ws_manager: WebSocketManager = Depends(get_websocket_manager),
    db: Session = Depends(get_db)
):
    """
    Test endpoint to send notifications without authentication
    
    Args:
        notification: Notification details
        ws_manager: WebSocket manager instance
        db: Database session
        
    Returns:
        NotificationResponse with delivery status
    """
    try:
        # Validate target user exists
        from uuid import UUID
        try:
            target_user = db.query(User).filter(User.id == UUID(notification.user_id)).first()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user ID format")
        
        if not target_user:
            raise HTTPException(status_code=404, detail=f"User {notification.user_id} not found")
        
        # Generate unique notification ID
        notification_id = f"notif_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now()
        
        # Create notification payload
        payload = NotificationPayload(
            notification_id=notification_id,
            title=notification.title,
            message=notification.message,
            priority=notification.priority,
            type=notification.type,
            timestamp=timestamp,
            metadata=notification.metadata,
            action_url=notification.action_url
        )
        
        # Prepare WebSocket message
        ws_message = {
            "type": "notification",
            "data": payload.model_dump(mode='json')
        }
        
        # Check if user is connected
        user_connection = ws_manager.get_connection(notification.user_id)
        delivered = user_connection is not None
        
        if delivered:
            # Send notification via WebSocket
            await ws_manager.send_message(notification.user_id, ws_message)
            logger.info(
                f"[Notification Test] Sent {notification.priority} notification to user {notification.user_id}: "
                f"{notification.title}"
            )
        else:
            logger.warning(
                f"[Notification Test] User {notification.user_id} not connected"
            )
        
        # Return response
        return NotificationResponse(
            success=True,
            message="Test notification sent successfully" if delivered else "User not connected",
            user_id=notification.user_id,
            notification_id=notification_id,
            timestamp=timestamp,
            delivered=delivered
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Notification Test] Error sending test notification: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send test notification: {str(e)}")


@router.get(
    "/test/users",
    summary="List All Users for Testing",
    description="Get a list of all users in the system for testing notifications"
)
async def list_users_for_testing(db: Session = Depends(get_db)):
    """
    List all users in the system for testing purposes
    
    Args:
        db: Database session
        
    Returns:
        List of users with id, name, and email
    """
    users = db.query(User).all()
    return {
        "total_users": len(users),
        "users": [
            {
                "id": str(user.id),
                "name": user.name,
                "email": user.email,
                "role": user.role.value if user.role else None
            }
            for user in users
        ]
    }
