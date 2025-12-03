"""
WebRTC Signaling Module
Handles SDP offer/answer exchange and WebRTC peer connection management
Receives video from frontend, processes for anomaly detection, sends alerts via WebSocket
Supports multiple streams per user with centralized session management
"""

import json
import logging
import uuid
import asyncio
from typing import Dict, Optional
from fastapi import APIRouter, HTTPException, Body, Depends
from pydantic import BaseModel, Field
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, MediaStreamTrack
from av import VideoFrame
from sqlalchemy.orm import Session

# Import session manager and WebSocket manager
from app.utils.session_manager import get_session_manager
from app.api.websocket import get_websocket_manager
from app.ai.processors.websocket_processor import WebSocketAnomalyProcessor
from app.services.anomaly_service import AnomalyService
from app.config import get_rtc_configuration

# Import authentication dependencies
from app.db import get_db
from app.models import User, Shop
from app.core.dependencies import get_current_user, verify_shop_access
from uuid import UUID as PyUUID

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI router for signaling endpoints
router = APIRouter(prefix="/api", tags=["WebRTC Signaling"])


# ============================================================================
# Pydantic Models for Request/Response
# ============================================================================


class OfferRequest(BaseModel):
    """
    Request model for receiving SDP offer from client
    Frontend will send video stream via WebRTC with user identification and shop ID
    """

    sdp: str = Field(..., description="Session Description Protocol offer")
    type: str = Field(..., description="SDP type (should be 'offer')")
    user_id: str = Field(..., description="User identifier for session management")
    shop_id: str = Field(..., description="Shop ID that this stream belongs to")
    stream_metadata: Optional[Dict] = Field(None, description="Optional stream metadata (name, camera_id, etc)")

    class Config:
        json_schema_extra = {
            "example": {
                "sdp": "v=0\r\no=- 123456789 2 IN IP4 127.0.0.1\r\n...",
                "type": "offer",
                "user_id": "user_123",
                "shop_id": "123e4567-e89b-12d3-a456-426614174000",
                "stream_metadata": {
                    "stream_name": "Camera 1",
                    "camera_id": "cam-001",
                    "location": "Entrance"
                }
            }
        }


class AnswerResponse(BaseModel):
    """
    Response model for sending SDP answer back to client
    """

    sdp: str = Field(..., description="Session Description Protocol answer")
    type: str = Field(..., description="SDP type (will be 'answer')")
    user_id: str = Field(..., description="User identifier")
    stream_id: str = Field(..., description="Unique stream identifier")

    class Config:
        json_schema_extra = {
            "example": {
                "sdp": "v=0\r\no=- 987654321 2 IN IP4 127.0.0.1\r\n...",
                "type": "answer",
                "user_id": "user_123",
                "stream_id": "stream_abc-456-def-789",
            }
        }


class SessionInfo(BaseModel):
    """
    Information about an active WebRTC session
    """

    session_id: str
    connection_state: str
    ice_connection_state: str
    ice_gathering_state: str
    signaling_state: str


class HealthResponse(BaseModel):
    """
    Health check response
    """

    status: str
    active_connections: int
    service: str


# ============================================================================
# WebRTC Connection Handlers
# ============================================================================


def create_peer_connection(user_id: str, stream_id: str, shop_id: str) -> RTCPeerConnection:
    """
    Create and configure an RTCPeerConnection with event handlers

    Args:
        user_id (str): User identifier
        stream_id (str): Unique stream identifier
        shop_id (str): Shop identifier for this stream

    Returns:
        RTCPeerConnection: Configured peer connection
    """
    # Get RTC configuration with STUN servers (returns list of RTCIceServer objects)
    ice_servers = get_rtc_configuration()
    rtc_config = RTCConfiguration(iceServers=ice_servers)

    # Create peer connection
    pc = RTCPeerConnection(configuration=rtc_config)

    # Register event handlers
    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        """Handle connection state changes"""
        logger.info(f"[{user_id}/{stream_id}] Connection state: {pc.connectionState}")

        # Clean up when connection closes
        if pc.connectionState in ["failed", "closed"]:
            await cleanup_stream(stream_id)

    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        """Handle ICE connection state changes"""
        logger.info(f"[{user_id}/{stream_id}] ICE connection state: {pc.iceConnectionState}")

        if pc.iceConnectionState == "failed":
            logger.error(f"[{user_id}/{stream_id}] ICE connection failed")
            await cleanup_stream(stream_id)

    @pc.on("icegatheringstatechange")
    async def on_icegatheringstatechange():
        """Handle ICE gathering state changes"""
        logger.info(f"[{user_id}/{stream_id}] ICE gathering state: {pc.iceGatheringState}")

    @pc.on("track")
    def on_track(track: MediaStreamTrack):
        """
        Handle incoming video track from frontend
        This is where we receive video frames for processing
        """
        logger.info(f"[{user_id}/{stream_id}] Received track from frontend: {track.kind}")
        
        if track.kind == "video":
            logger.info(f"[{user_id}/{stream_id}] Starting video frame processing...")
            
            # Create frame processor for this stream
            processor = WebSocketAnomalyProcessor(stream_id, user_id)
            
            # Get session manager and WebSocket manager
            session_mgr = get_session_manager()
            ws_manager = get_websocket_manager()
            
            # Store shop_id in a way that process_video_track can access it
            # We'll pass it as a parameter
            asyncio.create_task(process_video_track(user_id, stream_id, track, processor, ws_manager, shop_id))

    return pc


async def process_video_track(
    user_id: str,
    stream_id: str,
    track: MediaStreamTrack,
    processor: WebSocketAnomalyProcessor,
    ws_manager,
    shop_id: str
):
    """
    Process video frames from WebRTC track
    
    Args:
        user_id: User identifier
        stream_id: Stream identifier
        track: Video track from frontend
        processor: Frame processor instance
        ws_manager: WebSocket manager for sending alerts
        shop_id: Shop identifier for this stream
    """
    from app.db import SessionLocal
    from app.services.anomaly_service import AnomalyService
    from uuid import UUID as PyUUID
    
    logger.info(f"[{user_id}/{stream_id}] Video track processing started (shop: {shop_id})")
    
    try:
        while True:
            # Receive frame from WebRTC track
            frame: VideoFrame = await track.recv()
            
            # Process frame for anomaly detection
            results = await processor.process_frame(frame)
            
            # If anomalies detected, send alert via WebSocket and save to database
            if results:
                # Convert frame to numpy for annotation
                frame_np = frame.to_ndarray(format="bgr24")
                
                # Annotate frame with bounding boxes
                annotated_frame = processor.annotate_frame(frame_np, results)
                
                # Send each anomaly result
                for result in results:
                    # Send alert via WebSocket
                    await ws_manager.send_anomaly_alert(
                        user_id=user_id,
                        stream_id=stream_id,
                        detection_result=result,
                        annotated_frame=annotated_frame
                    )
                    
                    # Save anomaly to database
                    db = None
                    try:
                        db = SessionLocal()
                        
                        # Get stream metadata for location
                        stream_metadata = result.get('stream_metadata', {})
                        location = stream_metadata.get('location', stream_metadata.get('camera_id', f'Stream {stream_id[:8]}'))
                        
                        # Create description
                        person_id = result.get('person_id', 'Unknown')
                        confidence = result.get('confidence', 'Unknown')
                        description = f"Anomalous behavior detected (Person ID: {person_id}, Confidence: {confidence})"
                        
                        # Save to database
                        anomaly = AnomalyService.create_anomaly(
                            db=db,
                            shop_id=PyUUID(shop_id),
                            location=location,
                            description=description,
                            frame=annotated_frame,
                            detection_result=result,
                            anomaly_type="suspicious_behavior"
                        )
                        
                        if anomaly:
                            logger.info(f"[{user_id}/{stream_id}] Saved anomaly to database: {anomaly.id}")
                            
                            # Save pose_dict for reinforcement learning
                            pose_dict = result.get('pose_dict')
                            if pose_dict:
                                training_data = AnomalyService.save_training_data(
                                    db=db,
                                    anomaly_id=anomaly.id,
                                    pose_dict=pose_dict,
                                    stream_id=stream_id,
                                    frame_number=result.get('frame_number', 0),
                                    predicted_score=result.get('score', 0.0),
                                    predicted_confidence=result.get('confidence', 'Unknown'),
                                    predicted_label=result.get('classification'),
                                    extra_metadata={
                                        'person_id': result.get('person_id'),
                                        'bbox': result.get('bbox')
                                    }
                                )
                                if training_data:
                                    logger.info(
                                        f"[{user_id}/{stream_id}] Saved training data for reinforcement learning: {training_data.id}"
                                    )
                                else:
                                    logger.warning(
                                        f"[{user_id}/{stream_id}] Failed to save training data"
                                    )
                            
                            # Send notification message for frontend popup
                            notification_msg = {
                                'type': 'notification',
                                'data': {
                                    'notification_id': str(anomaly.id),
                                    'title': 'Alert',
                                    'message': f'{anomaly.description} at {location}',
                                    'priority': anomaly.severity.value,
                                    'type': 'alert',
                                    'timestamp': anomaly.timestamp.isoformat(),
                                    'metadata': {
                                        'anomaly_id': str(anomaly.id),
                                        'shop_id': str(shop_id),
                                        'stream_id': stream_id,
                                        'person_id': result.get('person_id')
                                    },
                                    'action_url': f'/suspicious-activity?anomaly_id={anomaly.id}'
                                }
                            }
                            await ws_manager.send_message(user_id, notification_msg)
                            logger.info(f"[{user_id}/{stream_id}] Sent notification popup for anomaly {anomaly.id}")
                        else:
                            logger.error(f"[{user_id}/{stream_id}] Failed to save anomaly to database")
                            
                    except Exception as e:
                        logger.error(f"[{user_id}/{stream_id}] Error saving anomaly to database: {e}", exc_info=True)
                    finally:
                        if db:
                            db.close()
                    
    except Exception as e:
        if "closed" in str(e).lower() or "ended" in str(e).lower():
            logger.info(f"[{user_id}/{stream_id}] Video track ended normally")
        else:
            logger.error(f"[{user_id}/{stream_id}] Error processing video track: {e}", exc_info=True)
    finally:
        logger.info(f"[{user_id}/{stream_id}] Video track processing stopped")


async def cleanup_stream(stream_id: str):
    """
    Clean up and close a specific stream

    Args:
        stream_id (str): Stream identifier to clean up
    """
    session_mgr = get_session_manager()
    await session_mgr.cleanup_stream(stream_id)
    
    # Check if user has any remaining streams
    user_id = session_mgr.get_user_for_stream(stream_id)
    if user_id:
        stream_count = session_mgr.get_user_stream_count(user_id)
        logger.info(f"[{user_id}] Stream {stream_id} cleaned up. Remaining streams: {stream_count}")


# ============================================================================
# API Endpoints
# ============================================================================


@router.post(
    "/offer",
    response_model=AnswerResponse,
    status_code=200,
    summary="Exchange WebRTC SDP Offer/Answer (Requires Authentication)",
    description="""
    ## WebRTC Signaling Endpoint (Protected)
    
    This endpoint handles the WebRTC signaling handshake by exchanging SDP (Session Description Protocol) 
    offer and answer between the client and server.
    
    **Authentication Required**: Must provide valid JWT token in Authorization header.
    **Authorization**: User must have access to the specified shop (owner or assigned manager).
    
    ### Process Flow:
    1. Client sends SDP offer containing media capabilities, video track, user_id, and shop_id
    2. Server validates user authentication and shop access
    3. Server creates an RTCPeerConnection with configured STUN servers
    4. Server generates unique stream_id for this connection
    5. Server receives video stream from frontend
    6. Server processes frames for anomaly detection
    7. Server sends anomaly alerts via WebSocket at /ws/alerts/{user_id}
    8. Server returns SDP answer with user_id and stream_id
    
    ### Features:
    - Multiple streams per user supported
    - User-based session management
    - Unique stream_id for each connection
    - All streams' alerts sent to single user WebSocket
    - Automatic cleanup on connection failure
    - Shop-based access control
    
    ### Video Processing:
    - Receives video from frontend (webcam/uploaded video)
    - Real-time frame processing with STG-NF pipeline
    - Anomaly alerts sent via WebSocket at /ws/alerts/{user_id}
    """,
    tags=["WebRTC Signaling"],
)
async def handle_offer(
    offer: OfferRequest = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Handle WebRTC offer from client and return answer (Protected Endpoint)

    This endpoint:
    1. Validates user authentication and shop access
    2. Receives SDP offer from the frontend with user_id and shop_id
    3. Creates an RTCPeerConnection
    4. Generates unique stream_id
    5. Sets up video track handler to receive frames from frontend
    6. Creates and returns SDP answer with user_id and stream_id
    7. Frontend should connect to WebSocket at /ws/alerts/{user_id}

    Args:
        offer (OfferRequest): SDP offer from client with user_id and shop_id
        current_user (User): Authenticated user from JWT token
        db (Session): Database session

    Returns:
        AnswerResponse: SDP answer with user_id and stream_id

    Raises:
        HTTPException: If offer processing fails or unauthorized
    """
    # Generate unique stream ID
    stream_id = str(uuid.uuid4())
    user_id = offer.user_id
    
    # Validate that the user_id in request matches authenticated user
    if str(current_user.id) != user_id:
        raise HTTPException(
            status_code=403,
            detail="User ID in request does not match authenticated user"
        )
    
    # Validate shop access
    try:
        shop_id = PyUUID(offer.shop_id)
        verify_shop_access(shop_id, current_user, db)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid shop ID format"
        )
    except HTTPException as e:
        # Re-raise authorization errors
        raise e
    
    logger.info(f"[{user_id}] Received WebRTC offer for new stream (shop: {offer.shop_id})")

    try:
        # Validate offer type
        if offer.type != "offer":
            raise HTTPException(
                status_code=400, detail=f"Expected type 'offer', got '{offer.type}'"
            )

        # Get session manager
        session_mgr = get_session_manager()

        # Create peer connection
        pc = create_peer_connection(user_id, stream_id, offer.shop_id)
        logger.info(f"[{user_id}/{stream_id}] Created peer connection")

        # Set remote description (client's offer)
        offer_sdp = RTCSessionDescription(sdp=offer.sdp, type=offer.type)
        await pc.setRemoteDescription(offer_sdp)
        logger.info(f"[{user_id}/{stream_id}] Set remote description")
        logger.info(f"[{user_id}/{stream_id}] Ready to receive video track from frontend")

        # Create answer (no tracks added - we only receive)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        logger.info(f"[{user_id}/{stream_id}] Created and set local description (answer)")

        # Store in session manager (processor will be added when track arrives)
        # For now, just store peer connection reference
        logger.info(f"[{user_id}] Stream {stream_id} registered")
        logger.info(f"[{user_id}] WebSocket endpoint: /ws/alerts/{user_id}")

        # Return answer to client
        return AnswerResponse(
            sdp=pc.localDescription.sdp,
            type=pc.localDescription.type,
            user_id=user_id,
            stream_id=stream_id,
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise

    except Exception as e:
        logger.error(f"[{user_id}/{stream_id}] Error handling offer: {e}", exc_info=True)

        # Clean up on error
        await cleanup_stream(stream_id)

        raise HTTPException(
            status_code=500, detail=f"Failed to process offer: {str(e)}"
        )


@router.get(
    "/users",
    summary="List All Active Users",
    description="""
    ## Get All Users with Active Streams
    
    Returns a list of all users currently connected with at least one active video stream.
    
    ### Response Includes:
    - Array of user IDs
    - Total count of active users
    - Stream counts per user
    
    ### Use Cases:
    - Monitor active users
    - Track user engagement
    - Administrative oversight
    - Capacity planning
    """,
    responses={
        200: {
            "description": "List of active users",
            "content": {
                "application/json": {
                    "example": {
                        "users": [
                            {"user_id": "user123", "stream_count": 2},
                            {"user_id": "user456", "stream_count": 1},
                        ],
                        "total_users": 2,
                        "total_streams": 3,
                    }
                }
            },
        }
    },
    tags=["User Management"],
)
async def list_users():
    """
    List all users with active streams

    Returns:
        dict: List of active users with stream counts
    """
    session_mgr = get_session_manager()
    users_data = []
    
    for user_id, session in session_mgr.user_sessions.items():
        users_data.append({
            "user_id": user_id,
            "stream_count": len(session.streams),
            "connected_at": session.connected_at.isoformat(),
        })
    
    stats = session_mgr.get_global_stats()
    
    return {
        "users": users_data,
        "total_users": stats["total_users"],
        "total_streams": stats["total_streams"],
    }


@router.get(
    "/users/{user_id}/streams",
    summary="List User's Active Streams",
    description="""
    ## Get All Active Streams for a Specific User
    
    Returns detailed information about all video streams currently active for a given user.
    
    ### Response Includes:
    - Array of stream information (stream_id, metadata, connection status)
    - Total count of user's streams
    - User connection timestamp
    
    ### Use Cases:
    - Monitor user's camera feeds
    - Debug multi-stream issues
    - Track stream metadata
    - Display stream list in admin dashboard
    """,
    responses={
        200: {
            "description": "List of user's streams",
            "content": {
                "application/json": {
                    "example": {
                        "user_id": "user123",
                        "streams": [
                            {
                                "stream_id": "550e8400-e29b-41d4-a716-446655440000",
                                "metadata": {"camera": "front_door", "location": "entrance"},
                                "created_at": "2024-01-15T10:30:00",
                            }
                        ],
                        "stream_count": 1,
                    }
                }
            },
        },
        404: {"description": "User not found"},
    },
    tags=["User Management"],
)
async def get_user_streams(user_id: str):
    """
    Get all streams for a specific user

    Args:
        user_id (str): User identifier

    Returns:
        dict: User's stream information

    Raises:
        HTTPException: If user not found
    """
    session_mgr = get_session_manager()
    streams = session_mgr.get_user_streams(user_id)
    
    if streams is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    
    streams_data = [
        {
            "stream_id": stream.stream_id,
            "metadata": stream.metadata,
            "created_at": stream.created_at.isoformat(),
        }
        for stream in streams
    ]
    
    return {
        "user_id": user_id,
        "streams": streams_data,
        "stream_count": len(streams_data),
    }


@router.delete(
    "/users/{user_id}/streams/{stream_id}",
    summary="Close Specific Stream",
    description="""
    ## Terminate a Specific Video Stream
    
    Closes an active video stream for a user while keeping their other streams active.
    
    ### Actions:
    - Closes RTCPeerConnection for the stream
    - Stops video processing for that stream
    - Releases stream resources
    - Removes stream from user's session
    - Keeps WebSocket connection active if user has other streams
    
    ### When to Use:
    - Close specific camera feed
    - User stops sharing one video source
    - Cleanup problematic stream without affecting others
    """,
    responses={
        200: {
            "description": "Stream closed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "message": "Stream closed",
                        "user_id": "user123",
                        "stream_id": "550e8400-e29b-41d4-a716-446655440000",
                        "remaining_streams": 1,
                    }
                }
            },
        },
        404: {"description": "Stream not found"},
    },
    tags=["User Management"],
)
async def close_stream(user_id: str, stream_id: str):
    """
    Close a specific stream for a user

    Args:
        user_id (str): User identifier
        stream_id (str): Stream identifier to close

    Returns:
        dict: Success message with remaining stream count

    Raises:
        HTTPException: If stream not found
    """
    session_mgr = get_session_manager()
    
    # Verify stream belongs to user
    stream_user = session_mgr.get_user_for_stream(stream_id)
    if stream_user != user_id:
        raise HTTPException(
            status_code=404, 
            detail=f"Stream {stream_id} not found for user {user_id}"
        )
    
    # Cleanup stream
    await cleanup_stream(stream_id)
    
    # Get remaining stream count
    remaining = session_mgr.get_user_stream_count(user_id)
    
    return {
        "status": "success",
        "message": "Stream closed",
        "user_id": user_id,
        "stream_id": stream_id,
        "remaining_streams": remaining,
    }


@router.delete(
    "/users/{user_id}",
    summary="Close All User Streams",
    description="""
    ## Terminate All Streams for a User
    
    Closes all active video streams for a user and cleans up their session.
    
    ### Actions:
    - Closes all RTCPeerConnections for the user
    - Stops all video processing
    - Releases all stream resources
    - Removes user session
    - Closes WebSocket connection
    
    ### When to Use:
    - User logout/disconnect
    - Force disconnect user
    - Session timeout
    - Administrative action
    """,
    responses={
        200: {
            "description": "All user streams closed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "message": "All streams closed for user",
                        "user_id": "user123",
                        "streams_closed": 2,
                    }
                }
            },
        },
        404: {"description": "User not found"},
    },
    tags=["User Management"],
)
async def close_user_streams(user_id: str):
    """
    Close all streams for a user

    Args:
        user_id (str): User identifier

    Returns:
        dict: Success message with count of closed streams

    Raises:
        HTTPException: If user not found
    """
    session_mgr = get_session_manager()
    
    # Get stream count before cleanup
    stream_count = session_mgr.get_user_stream_count(user_id)
    if stream_count == 0:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    
    # Cleanup all user streams
    await session_mgr.cleanup_user(user_id)
    
    return {
        "status": "success",
        "message": "All streams closed for user",
        "user_id": user_id,
        "streams_closed": stream_count,
    }


@router.get(
    "/stats",
    summary="Get Global Statistics",
    description="""
    ## System-Wide Connection Statistics
    
    Returns comprehensive statistics about all active connections and users.
    
    ### Statistics Include:
    - Total number of active users
    - Total number of active streams
    - Average streams per user
    - Peak concurrent users/streams
    - System capacity metrics
    
    ### Use Cases:
    - System monitoring
    - Performance metrics
    - Capacity planning
    - Analytics dashboard
    - Load balancing decisions
    """,
    responses={
        200: {
            "description": "Global statistics",
            "content": {
                "application/json": {
                    "example": {
                        "total_users": 5,
                        "total_streams": 12,
                        "average_streams_per_user": 2.4,
                        "active_peer_connections": 12,
                    }
                }
            },
        }
    },
    tags=["Statistics"],
)
async def get_stats():
    """
    Get global system statistics

    Returns:
        dict: System-wide statistics
    """
    session_mgr = get_session_manager()
    stats = session_mgr.get_global_stats()
    
    return stats


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Signaling Service Health Check",
    description="""
    ## WebRTC Signaling Service Health Status
    
    Returns the health status of the WebRTC signaling service.
    
    ### Health Indicators:
    - Service status (healthy/unhealthy)
    - Number of active connections
    - Service name
    
    ### Monitoring:
    - Used by load balancers
    - Kubernetes health probes
    - Monitoring systems (Prometheus, Datadog, etc.)
    """,
    responses={200: {"description": "Service is healthy"}},
    tags=["Health"],
)
async def health_check():
    """
    Health check endpoint for signaling service

    Returns:
        HealthResponse: Service health status
    """
    session_mgr = get_session_manager()
    stats = session_mgr.get_global_stats()
    
    return HealthResponse(
        status="healthy",
        active_connections=stats["total_streams"],
        service="WebRTC Signaling",
    )


# ============================================================================
# Cleanup on Shutdown
# ============================================================================


async def cleanup_all_connections():
    """
    Clean up all active connections and sessions
    Should be called on application shutdown
    """
    logger.info("Cleaning up all connections...")

    session_mgr = get_session_manager()
    all_users = list(session_mgr.user_sessions.keys())
    
    for user_id in all_users:
        await session_mgr.cleanup_user(user_id)

    logger.info("All connections cleaned up")
