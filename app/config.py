"""
Configuration file for AI Video Streaming Application
Contains all constants and configuration settings for WebRTC streaming
"""

import os
from typing import List
from pathlib import Path

# ============================================================================
# BASE DIRECTORIES
# ============================================================================

# Base directory of the application
BASE_DIR = Path(__file__).resolve().parent.parent

# ============================================================================
# VIDEO CONFIGURATION
# ============================================================================

# Path to the video file to be processed
# Can be changed to any video file path or later adapted for CCTV streams
# VIDEO_FILE_PATH = os.getenv("VIDEO_FILE_PATH", "sample_video.mp4")
VIDEO_FILE_PATH = "./assets/sample.mp4"

# Target frame rate for video streaming (frames per second)
# 30 FPS is a good balance between smoothness and bandwidth
TARGET_FPS = 30

# Frame interval in seconds (calculated from FPS)
FRAME_INTERVAL = 1.0 / TARGET_FPS  # ~0.033 seconds per frame

# Video resolution settings
# These can be adjusted based on network bandwidth and requirements
DEFAULT_WIDTH = 640
DEFAULT_HEIGHT = 480

# Maximum video resolution (if we need to downscale)
MAX_WIDTH = 1280
MAX_HEIGHT = 1080

# ============================================================================
# WEBRTC CONFIGURATION
# ============================================================================

# STUN server configuration for NAT traversal
# STUN servers help establish peer-to-peer connections across NATs
# Format for display/documentation
STUN_SERVERS = [
    {"urls": "stun:stun.l.google.com:19302"},
    {"urls": "stun:stun1.l.google.com:19302"},
    {"urls": "stun:stun2.l.google.com:19302"},
]

# ICE (Interactive Connectivity Establishment) servers configuration
# aiortc expects RTCIceServer objects, which we'll create in get_rtc_configuration()
ICE_SERVERS = STUN_SERVERS

# WebRTC connection timeout settings
CONNECTION_TIMEOUT = 30  # seconds
ICE_GATHERING_TIMEOUT = 10  # seconds

# ============================================================================
# AI MODEL CONFIGURATION
# ============================================================================

# AI model settings (placeholder for future implementation)
AI_MODEL_PATH = os.getenv("AI_MODEL_PATH", "models/default_model.pt")
AI_MODEL_CONFIDENCE_THRESHOLD = 0.5

# Processing settings
ENABLE_AI_PROCESSING = os.getenv("ENABLE_AI_PROCESSING", "true").lower() == "true"
PROCESS_EVERY_N_FRAMES = 1  # Process every frame (can be increased for performance)

# ============================================================================
# STG-NF ANOMALY DETECTION CONFIGURATION
# ============================================================================

# Import torch for device detection
import torch

# Model paths
YOLO_MODEL_PATH = os.getenv("YOLO_MODEL_PATH", "./models/yolov8n.pt")
POSE_MODEL_PATH = os.getenv("POSE_MODEL_PATH", "./models/yolov8n-pose.pt")
ANOMALY_MODEL_PATH = os.getenv("ANOMALY_MODEL_PATH", "./models/stg_nf_trained.pth")

# Detection settings
PERSON_DETECTION_CONFIDENCE = float(os.getenv("PERSON_DETECTION_CONFIDENCE", "0.45"))
ANOMALY_THRESHOLD = float(os.getenv("ANOMALY_THRESHOLD", "0.0"))

# Tracking settings (Deep SORT)
TRACKER_MAX_AGE = int(os.getenv("TRACKER_MAX_AGE", "900"))
TRACKER_MAX_IOU_DISTANCE = float(os.getenv("TRACKER_MAX_IOU_DISTANCE", "0.9"))
TRACKER_MAX_COSINE_DISTANCE = float(os.getenv("TRACKER_MAX_COSINE_DISTANCE", "0.7"))

# Frame buffer settings
SEQUENCE_LENGTH = int(os.getenv("SEQUENCE_LENGTH", "30"))
FRAME_DIGITS = int(os.getenv("FRAME_DIGITS", "4"))

# Device configuration (GPU/CPU)
DEVICE = os.getenv("DEVICE", "cuda:0" if torch.cuda.is_available() else "cpu")

# Logging
ANOMALY_LOG_PATH = os.getenv("ANOMALY_LOG_PATH", "./logs/anomaly_log.txt")

# ============================================================================
# SERVER CONFIGURATION
# ============================================================================

# Environment setting (development or production)
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()

# FastAPI server settings
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
DEBUG_MODE = os.getenv("DEBUG_MODE", "true" if ENVIRONMENT == "development" else "false").lower() == "true"

# CORS settings for React frontend
# In production, set ALLOWED_ORIGINS env var with comma-separated origins
# Example: ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
ALLOWED_ORIGINS_ENV = os.getenv("ALLOWED_ORIGINS", "")
if ALLOWED_ORIGINS_ENV:
    ALLOWED_ORIGINS = [origin.strip() for origin in ALLOWED_ORIGINS_ENV.split(",")]
else:
    # Default development origins
    ALLOWED_ORIGINS = [
        "http://localhost:3000",  # React default dev server
        "http://localhost:5173",  # Vite default dev server
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

# Allow all origins ONLY in development
# In production, this is automatically disabled regardless of env var
ALLOW_ALL_ORIGINS = ENVIRONMENT == "development"

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

# Logging level
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Enable detailed WebRTC logging
WEBRTC_VERBOSE_LOGGING = os.getenv("WEBRTC_VERBOSE_LOGGING", "false").lower() == "true"

# ============================================================================
# BUFFER AND QUEUE SETTINGS
# ============================================================================

# Maximum number of frames to buffer
MAX_FRAME_BUFFER = 10

# Video stream queue size
STREAM_QUEUE_SIZE = 30

# ============================================================================
# VIDEO CODEC SETTINGS
# ============================================================================

# Preferred video codec for WebRTC
PREFERRED_VIDEO_CODEC = "H264"  # or "VP8", "VP9"

# Video quality settings
VIDEO_BITRATE = 2_000_000  # 2 Mbps
VIDEO_KEYFRAME_INTERVAL = 30  # frames

# ============================================================================
# APPLICATION METADATA
# ============================================================================

APP_NAME = "AI Video Streaming Backend"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "Real-time AI video processing with WebRTC streaming"

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_rtc_configuration():
    """
    Returns the RTCConfiguration for aiortc with properly formatted ICE servers

    aiortc expects RTCIceServer objects, not plain dictionaries.
    This function converts our configuration to the correct format.

    Returns:
        List: List of RTCIceServer objects for aiortc
    """
    from aiortc import RTCIceServer

    # Convert dict format to RTCIceServer objects
    ice_servers = []
    for server in STUN_SERVERS:
        ice_servers.append(RTCIceServer(urls=server["urls"]))

    return ice_servers


def validate_video_file() -> bool:
    """
    Validates if the video file exists at the configured path

    Returns:
        bool: True if video file exists, False otherwise
    """
    return os.path.exists(VIDEO_FILE_PATH)


def get_allowed_origins() -> List[str]:
    """
    Returns the list of allowed origins for CORS

    Returns:
        List[str]: List of allowed origin URLs
    """
    if ALLOW_ALL_ORIGINS:
        return ["*"]
    return ALLOWED_ORIGINS
