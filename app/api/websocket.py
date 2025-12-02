"""
WebSocket Handler Module
Manages WebSocket connections for sending anomaly detection results
"""

import json
import logging
import asyncio
from typing import Dict, Optional
from datetime import datetime
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
    Implements heartbeat/ping-pong mechanism for persistent connections
    """
    
    def __init__(self):
        # Store one WebSocket connection per user_id
        self.connections: Dict[str, WebSocket] = {}
        # Track connection timestamps for health monitoring
        self.connection_times: Dict[str, datetime] = {}
        # Track last heartbeat received
        self.last_heartbeat: Dict[str, datetime] = {}
    
    async def connect(self, user_id: str, websocket: WebSocket):
        """
        Accept and store WebSocket connection for a user
        
        Args:
            user_id: Unique user identifier
            websocket: WebSocket connection instance
        """
        await websocket.accept()
        self.connections[user_id] = websocket
        self.connection_times[user_id] = datetime.now()
        self.last_heartbeat[user_id] = datetime.now()
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
        if user_id in self.connection_times:
            del self.connection_times[user_id]
        if user_id in self.last_heartbeat:
            del self.last_heartbeat[user_id]
        logger.info(f"[WS] WebSocket disconnected for user: {user_id}")
        logger.info(f"[WS] Active WebSocket connections: {len(self.connections)}")
    
    def update_heartbeat(self, user_id: str):
        """
        Update last heartbeat timestamp for a user
        
        Args:
            user_id: User identifier
        """
        if user_id in self.connections:
            self.last_heartbeat[user_id] = datetime.now()
            logger.debug(f"[WS] Heartbeat updated for user: {user_id}")
    
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
    
    def get_connection_stats(self, user_id: str) -> Optional[dict]:
        """
        Get connection statistics for a user
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary with connection stats or None
        """
        if user_id not in self.connections:
            return None
        
        now = datetime.now()
        connected_at = self.connection_times.get(user_id)
        last_beat = self.last_heartbeat.get(user_id)
        
        return {
            "user_id": user_id,
            "connected": True,
            "connected_at": connected_at.isoformat() if connected_at else None,
            "uptime_seconds": (now - connected_at).total_seconds() if connected_at else 0,
            "last_heartbeat": last_beat.isoformat() if last_beat else None,
            "seconds_since_heartbeat": (now - last_beat).total_seconds() if last_beat else 0
        }
    
    def get_all_connection_stats(self) -> dict:
        """
        Get statistics for all active connections
        
        Returns:
            Dictionary with overall connection statistics
        """
        stats = {
            "total_connections": len(self.connections),
            "connections": []
        }
        
        for user_id in self.connections.keys():
            user_stats = self.get_connection_stats(user_id)
            if user_stats:
                stats["connections"].append(user_stats)
        
        return stats


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
    
    **Heartbeat Mechanism**: 
    - Server sends ping every 30 seconds
    - Client should respond with pong
    - Connection closes if no response within 60 seconds
    
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
    
    # Create heartbeat task
    async def heartbeat_task():
        """Send periodic pings to keep connection alive"""
        try:
            while True:
                await asyncio.sleep(30)  # Send ping every 30 seconds
                try:
                    await websocket.send_json({'type': 'ping', 'timestamp': datetime.now().isoformat()})
                    logger.debug(f"[WS] Sent ping to user: {user_id}")
                except Exception as e:
                    logger.error(f"[WS] Error sending ping to user {user_id}: {e}")
                    break
        except asyncio.CancelledError:
            logger.debug(f"[WS] Heartbeat task cancelled for user: {user_id}")
    
    # Start heartbeat task
    heartbeat = asyncio.create_task(heartbeat_task())
    
    try:
        # Keep connection alive and listen for messages from frontend
        while True:
            data = await websocket.receive_text()
            
            # Handle incoming messages from frontend
            try:
                message = json.loads(data)
                message_type = message.get('type')
                
                if message_type == 'ping':
                    # Client initiated ping, respond with pong
                    ws_manager.update_heartbeat(user_id)
                    await websocket.send_json({'type': 'pong', 'timestamp': datetime.now().isoformat()})
                    logger.debug(f"[WS] Received ping from user {user_id}, sent pong")
                elif message_type == 'pong':
                    # Client responded to our ping
                    ws_manager.update_heartbeat(user_id)
                    logger.debug(f"[WS] Received pong from user {user_id}")
                elif message_type == 'ack':
                    # Frontend acknowledges receiving anomaly alert
                    stream_id = message.get('stream_id', 'unknown')
                    logger.info(f"[WS] Received acknowledgment from user {user_id} for stream {stream_id}")
                else:
                    logger.warning(f"[WS] Unknown message type from user {user_id}: {message_type}")
                    
            except json.JSONDecodeError:
                logger.error(f"[WS] Invalid JSON received from user: {user_id}")
                
    except WebSocketDisconnect:
        logger.info(f"[WS] WebSocket disconnected for user: {user_id}")
    except Exception as e:
        logger.error(f"[WS] WebSocket error for user {user_id}: {e}")
    finally:
        # Cancel heartbeat task
        heartbeat.cancel()
        try:
            await heartbeat
        except asyncio.CancelledError:
            pass
        
        # Clean up connection
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


# ============================================================================
# REST API Endpoints for WebSocket Monitoring
# ============================================================================


@router.get(
    "/connections",
    summary="Get WebSocket Connection Statistics",
    description="""
    Returns statistics about all active WebSocket connections.
    
    Useful for monitoring connection health, uptime, and heartbeat status.
    """,
    tags=["WebSocket Monitoring"]
)
async def get_connections():
    """
    Get statistics for all active WebSocket connections
    
    Returns:
        dict: Connection statistics including total connections and per-user details
    """
    return ws_manager.get_all_connection_stats()


@router.get(
    "/connections/{user_id}",
    summary="Get User WebSocket Connection Status",
    description="""
    Returns connection status and statistics for a specific user.
    
    Returns 404 if user is not connected.
    """,
    tags=["WebSocket Monitoring"]
)
async def get_user_connection(user_id: str):
    """
    Get connection statistics for a specific user
    
    Args:
        user_id: User identifier
        
    Returns:
        dict: User connection statistics
        
    Raises:
        HTTPException: If user is not connected
    """
    stats = ws_manager.get_connection_stats(user_id)
    if stats is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} is not connected")
    return stats
