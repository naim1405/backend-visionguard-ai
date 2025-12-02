"""
WebSocket Handler Module
Manages WebSocket connections for sending anomaly detection results
"""

import json
import logging
from typing import Dict, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from sqlalchemy.orm import Session
import base64
import cv2
import numpy as np

# Import authentication
from app.db import SessionLocal
from app.models import User
from app.core.auth import verify_token

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI router for WebSocket endpoints
router = APIRouter(prefix="/ws", tags=["WebSocket"])


# ============================================================================
# WebSocket Connection Manager
# ============================================================================


class WebSocketManager:
    """
    Manages WebSocket connections for anomaly alerts
    One WebSocket per user, handles alerts from all user's streams
    """
    
    def __init__(self):
        # Store one WebSocket connection per user_id
        self.connections: Dict[str, WebSocket] = {}
    
    async def connect(self, user_id: str, websocket: WebSocket):
        """
        Accept and store WebSocket connection for a user
        
        Args:
            user_id: Unique user identifier
            websocket: WebSocket connection instance
        """
        await websocket.accept()
        self.connections[user_id] = websocket
        logger.info(f"[WS] WebSocket connected for user: {user_id}")
        logger.info(f"[WS] Active WebSocket connections: {len(self.connections)}")
    
    def disconnect(self, user_id: str):
        """
        Remove WebSocket connection for a user
        
        Args:
            user_id: User identifier to disconnect
        """
        if user_id in self.connections:
            del self.connections[user_id]
            logger.info(f"[WS] WebSocket disconnected for user: {user_id}")
            logger.info(f"[WS] Active WebSocket connections: {len(self.connections)}")
    
    async def send_anomaly_alert(
        self,
        user_id: str,
        stream_id: str,
        detection_result: dict,
        annotated_frame: np.ndarray
    ):
        """
        Send anomaly detection result to frontend via WebSocket
        
        Args:
            user_id: User identifier
            stream_id: Stream identifier that detected the anomaly
            detection_result: Anomaly detection result dictionary
            annotated_frame: Annotated frame with bounding boxes
        """
        if user_id not in self.connections:
            logger.warning(f"[WS] No WebSocket connection for user: {user_id}")
            return
        
        websocket = self.connections[user_id]
        
        try:
            # Encode frame as JPEG
            _, buffer = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            frame_base64 = base64.b64encode(buffer.tobytes()).decode('utf-8')
            
            # Prepare message with both user_id and stream_id
            message = {
                'type': 'anomaly_detected',
                'user_id': user_id,
                'stream_id': stream_id,
                'result': detection_result,
                'annotated_frame': frame_base64,
                'frame_format': 'jpeg'
            }
            
            # Send via WebSocket
            await websocket.send_json(message)
            
            logger.info(f"[WS] Sent anomaly alert for user {user_id}, stream {stream_id}: Person {detection_result.get('person_id')}")
            
        except Exception as e:
            logger.error(f"[WS] Error sending anomaly alert to user {user_id}: {e}")
            self.disconnect(user_id)
    
    async def send_message(self, user_id: str, message: dict):
        """
        Send generic message to frontend
        
        Args:
            user_id: User identifier
            message: Message dictionary
        """
        if user_id not in self.connections:
            logger.warning(f"[WS] No WebSocket connection for user: {user_id}")
            return
        
        websocket = self.connections[user_id]
        
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"[WS] Error sending message to user {user_id}: {e}")
            self.disconnect(user_id)
    
    def get_connection(self, user_id: str) -> WebSocket | None:
        """
        Get WebSocket connection by user ID
        
        Args:
            user_id: User identifier
            
        Returns:
            WebSocket connection or None
        """
        return self.connections.get(user_id)


# Global WebSocket manager instance
ws_manager = WebSocketManager()


# ============================================================================
# WebSocket Endpoints
# ============================================================================


@router.websocket("/alerts/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    token: Optional[str] = Query(None, description="JWT authentication token")
):
    """
    WebSocket endpoint for receiving anomaly alerts (Protected)
    
    Frontend should connect to this endpoint using the user_id and provide a valid JWT token.
    All anomaly alerts from all of the user's streams will be sent here.
    
    **Authentication Required**: Must provide valid JWT token as query parameter.
    
    Example connection:
        ws://localhost:8000/ws/alerts/{user_id}?token=YOUR_JWT_TOKEN
    
    Args:
        websocket: WebSocket connection
        user_id: User identifier (should match user_id in WebRTC offer)
        token: JWT authentication token (query parameter)
    """
    # Authenticate user via token
    if not token:
        await websocket.close(code=1008, reason="Authentication token required")
        return
    
    # Verify token
    payload = verify_token(token)
    if payload is None:
        await websocket.close(code=1008, reason="Invalid or expired token")
        return
    
    # Extract user ID from token and verify it matches
    token_user_id = payload.get("sub")
    if token_user_id != user_id:
        await websocket.close(code=1008, reason="User ID mismatch")
        return
    
    # Verify user exists
    db = SessionLocal()
    try:
        from uuid import UUID
        user = db.query(User).filter(User.id == UUID(token_user_id)).first()
        if not user:
            await websocket.close(code=1008, reason="User not found")
            return
    finally:
        db.close()
    
    logger.info(f"[WS] Authenticated WebSocket connection for user: {user.email}")
    
    await ws_manager.connect(user_id, websocket)
    
    try:
        # Keep connection alive and listen for messages from frontend (optional)
        while True:
            data = await websocket.receive_text()
            
            # Handle incoming messages from frontend (if needed)
            try:
                message = json.loads(data)
                message_type = message.get('type')
                
                if message_type == 'ping':
                    # Respond to ping with pong
                    await websocket.send_json({'type': 'pong'})
                elif message_type == 'ack':
                    # Frontend acknowledges receiving anomaly alert
                    stream_id = message.get('stream_id', 'unknown')
                    logger.info(f"[WS] Received acknowledgment from user {user_id} for stream {stream_id}")
                else:
                    logger.warning(f"[WS] Unknown message type: {message_type}")
                    
            except json.JSONDecodeError:
                logger.error(f"[WS] Invalid JSON received from user: {user_id}")
                
    except WebSocketDisconnect:
        logger.info(f"[WS] WebSocket disconnected for user: {user_id}")
        ws_manager.disconnect(user_id)
    except Exception as e:
        logger.error(f"[WS] WebSocket error for user {user_id}: {e}")
        ws_manager.disconnect(user_id)


# ============================================================================
# Utility Functions
# ============================================================================


def get_websocket_manager() -> WebSocketManager:
    """
    Get the global WebSocket manager instance
    
    Returns:
        WebSocketManager instance
    """
    return ws_manager
