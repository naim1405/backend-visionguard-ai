"""
Session Manager Module
Manages user sessions with multiple WebRTC streams per user
Each user has one WebSocket connection but can have multiple video streams
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict
from aiortc import RTCPeerConnection
from fastapi import WebSocket

from app.ai.processors.websocket_processor import WebSocketAnomalyProcessor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class StreamInfo:
    """Information about a single video stream"""
    stream_id: str
    peer_connection: RTCPeerConnection
    processor: WebSocketAnomalyProcessor
    metadata: Dict[str, Any]
    created_at: datetime
    
    def get_stats(self) -> Dict[str, Any]:
        """Get stream statistics"""
        stats = self.processor.get_stats()
        return {
            "stream_id": self.stream_id,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            **stats
        }


@dataclass
class UserSession:
    """User session with multiple streams"""
    user_id: str
    websocket: Optional[WebSocket]
    streams: Dict[str, StreamInfo]  # stream_id -> StreamInfo
    created_at: datetime
    
    def add_stream(self, stream_info: StreamInfo):
        """Add a stream to this user session"""
        self.streams[stream_info.stream_id] = stream_info
        logger.info(f"[Session Manager] Added stream {stream_info.stream_id} to user {self.user_id}")
    
    def remove_stream(self, stream_id: str):
        """Remove a stream from this user session"""
        if stream_id in self.streams:
            del self.streams[stream_id]
            logger.info(f"[Session Manager] Removed stream {stream_id} from user {self.user_id}")
    
    def get_stream(self, stream_id: str) -> Optional[StreamInfo]:
        """Get stream info by ID"""
        return self.streams.get(stream_id)
    
    def get_stream_count(self) -> int:
        """Get number of active streams"""
        return len(self.streams)
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all streams"""
        return {
            "user_id": self.user_id,
            "stream_count": self.get_stream_count(),
            "created_at": self.created_at.isoformat(),
            "streams": [stream.get_stats() for stream in self.streams.values()]
        }


class SessionManager:
    """
    Manages all user sessions
    - One WebSocket per user
    - Multiple WebRTC streams per user
    - Centralized session tracking
    """
    
    def __init__(self):
        self.user_sessions: Dict[str, UserSession] = {}  # user_id -> UserSession
        self.stream_to_user: Dict[str, str] = {}  # stream_id -> user_id (quick lookup)
        logger.info("[Session Manager] Initialized")
    
    # ========================================================================
    # User Session Management
    # ========================================================================
    
    def create_user_session(self, user_id: str, websocket: Optional[WebSocket] = None) -> UserSession:
        """
        Create a new user session
        
        Args:
            user_id: Unique user identifier
            websocket: Optional WebSocket connection
            
        Returns:
            UserSession object
        """
        if user_id in self.user_sessions:
            logger.warning(f"[Session Manager] User session {user_id} already exists")
            return self.user_sessions[user_id]
        
        session = UserSession(
            user_id=user_id,
            websocket=websocket,
            streams={},
            created_at=datetime.now()
        )
        
        self.user_sessions[user_id] = session
        logger.info(f"[Session Manager] Created user session: {user_id}")
        return session
    
    def get_user_session(self, user_id: str) -> Optional[UserSession]:
        """Get user session by ID"""
        return self.user_sessions.get(user_id)
    
    def remove_user_session(self, user_id: str) -> bool:
        """
        Remove user session and all associated streams
        
        Args:
            user_id: User identifier
            
        Returns:
            True if removed, False if not found
        """
        if user_id not in self.user_sessions:
            return False
        
        session = self.user_sessions[user_id]
        
        # Remove all stream mappings
        for stream_id in list(session.streams.keys()):
            if stream_id in self.stream_to_user:
                del self.stream_to_user[stream_id]
        
        # Remove session
        del self.user_sessions[user_id]
        logger.info(f"[Session Manager] Removed user session: {user_id}")
        return True
    
    def set_user_websocket(self, user_id: str, websocket: WebSocket):
        """Set or update WebSocket for user"""
        session = self.get_user_session(user_id)
        if session:
            session.websocket = websocket
            logger.info(f"[Session Manager] Set WebSocket for user {user_id}")
        else:
            logger.warning(f"[Session Manager] Cannot set WebSocket - user {user_id} not found")
    
    # ========================================================================
    # Stream Management
    # ========================================================================
    
    def add_stream(
        self,
        user_id: str,
        stream_id: str,
        peer_connection: RTCPeerConnection,
        processor: WebSocketAnomalyProcessor,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Add a stream to user session
        
        Args:
            user_id: User identifier
            stream_id: Unique stream identifier
            peer_connection: WebRTC peer connection
            processor: Frame processor
            metadata: Optional stream metadata
        """
        # Get or create user session
        session = self.get_user_session(user_id)
        if not session:
            session = self.create_user_session(user_id)
        
        # Create stream info
        stream_info = StreamInfo(
            stream_id=stream_id,
            peer_connection=peer_connection,
            processor=processor,
            metadata=metadata or {},
            created_at=datetime.now()
        )
        
        # Add to session
        session.add_stream(stream_info)
        
        # Add to lookup map
        self.stream_to_user[stream_id] = user_id
        
        logger.info(
            f"[Session Manager] Added stream {stream_id} to user {user_id} "
            f"(total streams: {session.get_stream_count()})"
        )
    
    def remove_stream(self, stream_id: str) -> bool:
        """
        Remove a stream from its user session
        
        Args:
            stream_id: Stream identifier
            
        Returns:
            True if removed, False if not found
        """
        # Find which user owns this stream
        user_id = self.stream_to_user.get(stream_id)
        if not user_id:
            logger.warning(f"[Session Manager] Stream {stream_id} not found")
            return False
        
        # Get user session
        session = self.get_user_session(user_id)
        if not session:
            logger.warning(f"[Session Manager] User {user_id} not found")
            return False
        
        # Remove stream
        session.remove_stream(stream_id)
        del self.stream_to_user[stream_id]
        
        logger.info(
            f"[Session Manager] Removed stream {stream_id} from user {user_id} "
            f"(remaining streams: {session.get_stream_count()})"
        )
        
        return True
    
    def get_stream_info(self, stream_id: str) -> Optional[StreamInfo]:
        """Get stream info by ID"""
        user_id = self.stream_to_user.get(stream_id)
        if not user_id:
            return None
        
        session = self.get_user_session(user_id)
        if not session:
            return None
        
        return session.get_stream(stream_id)
    
    def get_user_for_stream(self, stream_id: str) -> Optional[str]:
        """Get user ID that owns the stream"""
        return self.stream_to_user.get(stream_id)
    
    # ========================================================================
    # Statistics and Monitoring
    # ========================================================================
    
    def get_user_streams(self, user_id: str) -> List[str]:
        """Get list of stream IDs for a user"""
        session = self.get_user_session(user_id)
        if not session:
            return []
        return list(session.streams.keys())
    
    def get_user_stream_count(self, user_id: str) -> int:
        """Get number of streams for a user"""
        session = self.get_user_session(user_id)
        if not session:
            return 0
        return session.get_stream_count()
    
    def get_total_users(self) -> int:
        """Get total number of active users"""
        return len(self.user_sessions)
    
    def get_total_streams(self) -> int:
        """Get total number of streams across all users"""
        return len(self.stream_to_user)
    
    def get_all_user_ids(self) -> List[str]:
        """Get list of all active user IDs"""
        return list(self.user_sessions.keys())
    
    def get_user_stats(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed statistics for a user"""
        session = self.get_user_session(user_id)
        if not session:
            return None
        return session.get_all_stats()
    
    def get_global_stats(self) -> Dict[str, Any]:
        """Get global statistics for all users and streams"""
        total_frames = 0
        total_anomalies = 0
        
        for session in self.user_sessions.values():
            for stream in session.streams.values():
                stats = stream.processor.get_stats()
                total_frames += stats.get('frames_processed', 0)
                total_anomalies += stats.get('anomalies_detected', 0)
        
        return {
            "total_users": self.get_total_users(),
            "total_streams": self.get_total_streams(),
            "total_frames_processed": total_frames,
            "total_anomalies_detected": total_anomalies,
            "users": [
                {
                    "user_id": user_id,
                    "stream_count": session.get_stream_count(),
                    "created_at": session.created_at.isoformat()
                }
                for user_id, session in self.user_sessions.items()
            ]
        }
    
    # ========================================================================
    # Cleanup
    # ========================================================================
    
    async def cleanup_stream(self, stream_id: str):
        """Clean up resources for a specific stream"""
        stream_info = self.get_stream_info(stream_id)
        if not stream_info:
            return
        
        try:
            # Close peer connection
            await stream_info.peer_connection.close()
            logger.info(f"[Session Manager] Closed peer connection for stream {stream_id}")
        except Exception as e:
            logger.error(f"[Session Manager] Error closing peer connection: {e}")
        
        try:
            # Clean up processor
            stream_info.processor.cleanup()
            logger.info(f"[Session Manager] Cleaned up processor for stream {stream_id}")
        except Exception as e:
            logger.error(f"[Session Manager] Error cleaning up processor: {e}")
        
        # Remove from registry
        self.remove_stream(stream_id)
    
    async def cleanup_user(self, user_id: str):
        """Clean up all resources for a user"""
        session = self.get_user_session(user_id)
        if not session:
            return
        
        logger.info(f"[Session Manager] Cleaning up user {user_id} with {session.get_stream_count()} streams")
        
        # Clean up all streams
        for stream_id in list(session.streams.keys()):
            await self.cleanup_stream(stream_id)
        
        # Remove user session
        self.remove_user_session(user_id)
        logger.info(f"[Session Manager] User {user_id} cleanup complete")
    
    async def cleanup_all(self):
        """Clean up all users and streams"""
        logger.info("[Session Manager] Cleaning up all users and streams...")
        
        for user_id in list(self.user_sessions.keys()):
            await self.cleanup_user(user_id)
        
        logger.info("[Session Manager] All cleanup complete")


# Global session manager instance
session_manager = SessionManager()


def get_session_manager() -> SessionManager:
    """
    Get the global session manager instance
    
    Returns:
        SessionManager instance
    """
    return session_manager
