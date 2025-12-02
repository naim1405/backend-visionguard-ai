"""
AI Video Streaming Backend - Main Application
Real-time AI video processing with WebRTC streaming to React frontend
"""

import logging
from contextlib import asynccontextmanager
from typing import Dict, List, Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict
import json

# Import configuration
from config import (
    APP_NAME,
    APP_VERSION,
    APP_DESCRIPTION,
    get_allowed_origins,
    validate_video_file,
    VIDEO_FILE_PATH,
)

# Import for validation error handling
from fastapi.exceptions import RequestValidationError
from fastapi import Request, status

# Import signaling router
from signaling import router as signaling_router, cleanup_all_connections

# Import WebSocket handler
from websocket_handler import router as websocket_router

# Import session manager
from session_manager import get_session_manager

# Import model manager
from model_manager import get_model_manager

# Import database
from database import init_db

# Import auth and shop routers
from auth_routes import router as auth_router
from shop_routes import router as shop_router

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic Response Models for Auto-Generated OpenAPI Documentation
# ============================================================================


class APIEndpoints(BaseModel):
    """Available API endpoints"""

    docs: str = Field(..., description="Swagger UI documentation URL")
    redoc: str = Field(..., description="ReDoc documentation URL")
    api: Dict[str, str] = Field(..., description="API endpoints")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "docs": "/docs",
                "redoc": "/redoc",
                "api": {"offer": "/api/offer", "sessions": "/api/sessions"},
            }
        }
    )


class RootResponse(BaseModel):
    """Root endpoint response model"""

    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    status: str = Field(..., description="Service status")
    description: str = Field(..., description="Service description")
    endpoints: APIEndpoints = Field(..., description="Available endpoints")
    video_file: str = Field(..., description="Configured video file path")
    video_exists: bool = Field(..., description="Whether video file exists")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "service": "AI Video Streaming Backend",
                "version": "1.0.0",
                "status": "running",
                "description": "Real-time AI video processing with WebRTC streaming",
                "endpoints": {
                    "docs": "/docs",
                    "redoc": "/redoc",
                    "api": {"offer": "/api/offer", "sessions": "/api/sessions"},
                },
                "video_file": "sample_video.mp4",
                "video_exists": True,
            }
        }
    )


class HealthCheckResponse(BaseModel):
    """Health check response model"""

    status: str = Field(..., description="Health status: 'healthy' or 'degraded'")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    video_file: str = Field(..., description="Video file path")
    video_available: bool = Field(..., description="Whether video file is available")
    message: str = Field(..., description="Status message")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "service": "AI Video Streaming Backend",
                "version": "1.0.0",
                "video_file": "sample_video.mp4",
                "video_available": True,
                "message": "Service is running",
            }
        }
    )


class ApplicationInfo(BaseModel):
    """Application information"""

    name: str = Field(..., description="Application name")
    version: str = Field(..., description="Application version")
    description: str = Field(..., description="Application description")


class VideoInfo(BaseModel):
    """Video configuration information"""

    path: str = Field(..., description="Video file path")
    exists: bool = Field(..., description="Whether video file exists")
    target_fps: int = Field(..., description="Target frame rate")
    resolution: str = Field(..., description="Video resolution")


class WebRTCInfo(BaseModel):
    """WebRTC configuration information"""

    stun_servers: List[Dict[str, str]] = Field(
        ..., description="STUN servers configuration"
    )


class AIInfo(BaseModel):
    """AI processing information"""

    processing_enabled: bool = Field(
        ..., description="Whether AI processing is enabled"
    )
    status: str = Field(..., description="AI model status")


class CORSInfo(BaseModel):
    """CORS configuration information"""

    allowed_origins: List[str] = Field(..., description="Allowed origins for CORS")


class ServiceInfoResponse(BaseModel):
    """Detailed service information response model"""

    application: ApplicationInfo = Field(..., description="Application information")
    video: VideoInfo = Field(..., description="Video configuration")
    webrtc: WebRTCInfo = Field(..., description="WebRTC configuration")
    ai: AIInfo = Field(..., description="AI processing information")
    cors: CORSInfo = Field(..., description="CORS configuration")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "application": {
                    "name": "AI Video Streaming Backend",
                    "version": "1.0.0",
                    "description": "Real-time AI video processing with WebRTC streaming",
                },
                "video": {
                    "path": "sample_video.mp4",
                    "exists": True,
                    "target_fps": 30,
                    "resolution": "640x480",
                },
                "webrtc": {"stun_servers": [{"urls": "stun:stun.l.google.com:19302"}]},
                "ai": {
                    "processing_enabled": True,
                    "status": "mocked (ready for implementation)",
                },
                "cors": {"allowed_origins": ["*"]},
            }
        }
    )


class ErrorResponse(BaseModel):
    """Error response model"""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    path: Optional[str] = Field(None, description="Request path")
    suggestion: Optional[str] = Field(None, description="Suggestion to fix the error")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "Not Found",
                "message": "The requested endpoint does not exist",
                "path": "/invalid-path",
                "suggestion": "Visit /docs for API documentation",
            }
        }
    )


# ============================================================================
# Application Lifecycle Management
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle (startup and shutdown events)

    Startup:
    - Load AI models at startup (shared instances)
    - Validate video file exists
    - Log configuration
    - Initialize any required resources

    Shutdown:
    - Clean up all WebRTC peer connections
    - Release AI model resources
    - Release other resources
    """
    # Startup
    logger.info("=" * 70)
    logger.info(f"Starting {APP_NAME} v{APP_VERSION}")
    logger.info("=" * 70)

    # Initialize database
    logger.info("Initializing database...")
    try:
        init_db()
        logger.info("✓ Database initialized successfully")
    except Exception as e:
        logger.error(f"✗ Failed to initialize database: {e}")
        logger.warning("  Authentication features may not work without database")

    # Load AI models at startup (singleton pattern - load once, share across all streams)
    logger.info("Loading AI models (this may take a moment)...")
    try:
        model_manager = get_model_manager()
        model_manager.load_models()
        logger.info("✓ AI models loaded successfully (shared across all streams)")
    except Exception as e:
        logger.error(f"✗ Failed to load AI models: {e}")
        logger.error("  Streams will fail to initialize without models")
        raise

    # Validate video file
    if validate_video_file():
        logger.info(f"✓ Video file found: {VIDEO_FILE_PATH}")
    else:
        logger.warning(f"⚠ Video file not found: {VIDEO_FILE_PATH}")
        logger.warning("  Please ensure a video file exists before starting streams")

    # Log CORS configuration
    allowed_origins = get_allowed_origins()
    if allowed_origins == ["*"]:
        logger.info("✓ CORS: Allowing all origins (development mode)")
    else:
        logger.info(f"✓ CORS: Allowing origins: {allowed_origins}")

    logger.info("✓ Application started successfully")
    logger.info("=" * 70)

    yield  # Application is running

    # Shutdown
    logger.info("=" * 70)
    logger.info("Shutting down application...")
    logger.info("=" * 70)

    # Clean up all user sessions and streams
    session_mgr = get_session_manager()
    all_users = list(session_mgr.user_sessions.keys())
    for user_id in all_users:
        logger.info(f"Cleaning up user: {user_id}")
        await session_mgr.cleanup_user(user_id)
    
    # Clean up remaining WebRTC connections
    await cleanup_all_connections()
    
    # Clean up AI models
    logger.info("Releasing AI model resources...")
    model_manager = get_model_manager()
    model_manager.cleanup()
    logger.info("✓ AI models cleaned up")

    logger.info("✓ Application shutdown complete")
    logger.info("=" * 70)


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
    lifespan=lifespan,
    docs_url="/docs",  # Swagger UI at /docs
    redoc_url="/redoc",  # ReDoc at /redoc
)


# ============================================================================
# CORS Middleware Configuration
# ============================================================================

# Add CORS middleware to allow requests from React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),  # Allow configured origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

logger.info("✓ CORS middleware configured")


# ============================================================================
# Include Routers
# ============================================================================

# Include WebRTC signaling router
app.include_router(signaling_router)
logger.info("✓ WebRTC signaling router included at /api")

# Include WebSocket router
app.include_router(websocket_router)
logger.info("✓ WebSocket router included at /ws")

# Include authentication router
app.include_router(auth_router)
logger.info("✓ Authentication router included at /auth")

# Include shop management router
app.include_router(shop_router)
logger.info("✓ Shop management router included at /shops")


# ============================================================================
# Root Endpoints
# ============================================================================


@app.get(
    "/",
    response_model=RootResponse,
    summary="API Root",
    description="""
    ## API Information and Service Discovery
    
    Returns comprehensive information about the API, including:
    - Service name and version
    - Current status
    - Available endpoints
    - Video configuration
    
    This endpoint serves as the entry point for API discovery.
    """,
    tags=["Root"],
)
async def root() -> RootResponse:
    """
    Root endpoint - Health check and API information

    Returns:
        RootResponse: Application information and available endpoints
    """
    return RootResponse(
        service=APP_NAME,
        version=APP_VERSION,
        status="running",
        description=APP_DESCRIPTION,
        endpoints=APIEndpoints(
            docs="/docs",
            redoc="/redoc",
            api={
                "offer": "/api/offer",
                "sessions": "/api/sessions",
                "health": "/api/health",
            },
        ),
        video_file=VIDEO_FILE_PATH,
        video_exists=validate_video_file(),
    )


@app.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Application Health Check",
    description="""
    ## Service Health Status
    
    Returns the overall health status of the application.
    
    ### Status Values:
    - **healthy**: Service is fully operational, video file available
    - **degraded**: Service running but video file not found
    
    ### Use Cases:
    - Kubernetes liveness/readiness probes
    - Load balancer health checks
    - Monitoring and alerting systems
    - Service discovery
    
    ### Response Includes:
    - Overall status
    - Service information
    - Video file availability
    - Diagnostic message
    """,
    tags=["Health"],
)
async def health_check() -> HealthCheckResponse:
    """
    Health check endpoint for monitoring and load balancers

    Returns:
        HealthCheckResponse: Health status of the service
    """
    video_available = validate_video_file()

    return HealthCheckResponse(
        status="healthy" if video_available else "degraded",
        service=APP_NAME,
        version=APP_VERSION,
        video_file=VIDEO_FILE_PATH,
        video_available=video_available,
        message="Service is running" if video_available else "Video file not found",
    )


@app.get(
    "/info",
    summary="Service Information",
    description="""
    ## Detailed Service Configuration and Capabilities
    
    Returns comprehensive configuration information about the video streaming service.
    
    ### Information Includes:
    
    #### Application:
    - Service name and version
    - Description
    
    #### Video Configuration:
    - Video file path
    - Availability status
    - Target frame rate
    - Resolution settings
    
    #### WebRTC Configuration:
    - STUN server list
    - ICE server configuration
    
    #### AI Processing:
    - Processing status
    - Model information
    - Capabilities
    
    #### CORS Settings:
    - Allowed origins
    - Cross-origin policy
    
    ### Use Cases:
    - Client capability negotiation
    - Configuration verification
    - Debugging and diagnostics
    - Service documentation
    """,
    responses={
        200: {
            "description": "Detailed service information",
            "content": {
                "application/json": {
                    "example": {
                        "application": {
                            "name": "AI Video Streaming Backend",
                            "version": "1.0.0",
                        },
                        "video": {
                            "path": "sample_video.mp4",
                            "exists": True,
                            "target_fps": 30,
                            "resolution": "640x480",
                        },
                        "webrtc": {
                            "stun_servers": [{"urls": "stun:stun.l.google.com:19302"}]
                        },
                        "ai": {
                            "processing_enabled": True,
                            "status": "mocked (ready for implementation)",
                        },
                    }
                }
            },
        }
    },
    tags=["Information"],
)
async def get_info():
    """
    Get detailed information about the streaming service

    Returns:
        dict: Service configuration and capabilities
    """
    from config import (
        TARGET_FPS,
        DEFAULT_WIDTH,
        DEFAULT_HEIGHT,
        STUN_SERVERS,
        ENABLE_AI_PROCESSING,
    )

    return {
        "application": {
            "name": APP_NAME,
            "version": APP_VERSION,
            "description": APP_DESCRIPTION,
        },
        "video": {
            "path": VIDEO_FILE_PATH,
            "exists": validate_video_file(),
            "target_fps": TARGET_FPS,
            "resolution": f"{DEFAULT_WIDTH}x{DEFAULT_HEIGHT}",
        },
        "webrtc": {
            "stun_servers": STUN_SERVERS,
        },
        "ai": {
            "processing_enabled": ENABLE_AI_PROCESSING,
            "status": "mocked (ready for implementation)",
        },
        "cors": {
            "allowed_origins": get_allowed_origins(),
        },
    }


@app.get("/video-data")
def video_data():
    """
    Endpoint to retrieve video data for testing purposes.
    """
    with open("data.json", "r") as data_file:
        data = json.load(data_file)
    return JSONResponse(content=data)


# ============================================================================
# Error Handlers
# ============================================================================


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Custom validation error handler to provide detailed error messages
    """
    errors = []
    for error in exc.errors():
        errors.append({
            "field": " -> ".join(str(x) for x in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "message": "Request validation failed",
            "details": errors,
            "body_received": exc.body if hasattr(exc, 'body') else None,
        },
    )


@app.exception_handler(404)
async def not_found_handler(request, exc):
    """
    Custom 404 error handler
    """
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": "The requested endpoint does not exist",
            "path": str(request.url.path),
            "suggestion": "Visit /docs for API documentation",
        },
    )


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """
    Custom 500 error handler
    """
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
            "suggestion": "Please check server logs for details",
        },
    )


# ============================================================================
# Application Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    from config import SERVER_HOST, SERVER_PORT, DEBUG_MODE

    logger.info("Starting server with uvicorn...")

    # Run the application
    uvicorn.run(
        "main:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=DEBUG_MODE,  # Auto-reload in debug mode
    )
