# AI Video Streaming Backend

Real-time AI video processing with WebRTC streaming to React frontend.

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [API Documentation](#api-documentation)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Future Enhancements](#future-enhancements)
- [Additional Documentation](#additional-documentation)

## 🎯 Overview

This backend application processes video frames in real-time using AI models and streams the processed video to web clients via WebRTC. The system is built with FastAPI and aiortc, providing a robust and scalable solution for live video processing.

### Key Components

- **FastAPI**: Modern Python web framework for building APIs
- **aiortc**: WebRTC implementation for Python
- **OpenCV**: Video processing and frame manipulation
- **PyAV**: Media container and codec handling

## ✨ Features

- ✅ Real-time video frame processing
- ✅ WebRTC streaming to browser clients
- ✅ RESTful API following OpenAPI 3.0 standards
- ✅ CORS support for React frontends
- ✅ Automatic connection management
- ✅ STUN server configuration for NAT traversal
- ✅ Modular architecture for easy AI model integration
- ✅ Comprehensive logging and error handling
- ✅ Health check and monitoring endpoints

## 🏗️ Architecture

```
┌─────────────────┐         WebRTC          ┌──────────────────┐
│  React Client   │◄────────(Video)─────────┤  FastAPI Backend │
│   (Browser)     │                         │                  │
└─────────────────┘         HTTP/HTTPS      │  ┌────────────┐  │
        │                                    │  │  Signaling │  │
        │           SDP Offer/Answer         │  │   Router   │  │
        └────────────(REST API)──────────────┼─►│            │  │
                                             │  └────────────┘  │
                                             │                  │
                                             │  ┌────────────┐  │
                                             │  │ AI Stream  │  │
                                             │  │   Track    │  │
                                             │  └──────┬─────┘  │
                                             │         │        │
                                             │  ┌──────▼─────┐  │
                                             │  │    AI      │  │
                                             │  │ Processor  │  │
                                             │  └──────┬─────┘  │
                                             │         │        │
                                             │  ┌──────▼─────┐  │
                                             │  │   Video    │  │
                                             │  │   Source   │  │
                                             │  └────────────┘  │
                                             └──────────────────┘
```

## 📦 Installation

### Prerequisites

- Python 3.8 or higher
- FFmpeg libraries (for PyAV)
- Virtual environment (recommended)

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd visiongaurd-backend
```

### Step 2: Create Virtual Environment

```bash
python3 -m venv env
source env/bin/activate.fish  # For fish shell
# or
source env/bin/activate  # For bash/zsh
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Install FFmpeg (if not already installed)

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install ffmpeg libavformat-dev libavcodec-dev libavdevice-dev libavutil-dev libswscale-dev
```

**macOS:**
```bash
brew install ffmpeg
```

## ⚙️ Configuration

Edit `config.py` to customize the application:

### Video Configuration

```python
VIDEO_FILE_PATH = "sample_video.mp4"  # Path to your video file
TARGET_FPS = 30                        # Target frame rate
DEFAULT_WIDTH = 640                    # Video width
DEFAULT_HEIGHT = 480                   # Video height
```

### WebRTC Configuration

```python
STUN_SERVERS = [
    {"urls": "stun:stun.l.google.com:19302"},
]
```

### Server Configuration

```python
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8000
DEBUG_MODE = True
```

### Environment Variables

You can also use environment variables:

```bash
export VIDEO_FILE_PATH="/path/to/your/video.mp4"
export SERVER_PORT=8000
export DEBUG_MODE=true
```

## 🚀 Running the Application

### Method 1: Using Python Directly

```bash
python main.py
```

### Method 2: Using Uvicorn

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Method 3: Production Deployment

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

The server will start on `http://localhost:8000`

## 📚 API Documentation

The API follows **OpenAPI 3.0** standards. Interactive documentation is available at:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### Core Endpoints

#### Root Endpoints

##### `GET /`
Get API information and available endpoints.

**Response:**
```json
{
  "service": "AI Video Streaming Backend",
  "version": "1.0.0",
  "status": "running",
  "endpoints": {
    "docs": "/docs",
    "api": {
      "offer": "/api/offer"
    }
  }
}
```

##### `GET /health`
Health check endpoint for monitoring.

**Response:**
```json
{
  "status": "healthy",
  "service": "AI Video Streaming Backend",
  "version": "1.0.0",
  "video_available": true
}
```

##### `GET /info`
Get detailed service configuration.

**Response:**
```json
{
  "application": {
    "name": "AI Video Streaming Backend",
    "version": "1.0.0"
  },
  "video": {
    "path": "sample_video.mp4",
    "exists": true,
    "target_fps": 30,
    "resolution": "640x480"
  },
  "webrtc": {
    "stun_servers": [...]
  }
}
```

#### WebRTC Signaling Endpoints

##### `POST /api/offer`
Exchange SDP offer/answer for WebRTC connection.

**Request Body:**
```json
{
  "sdp": "v=0\r\no=- 123456789 2 IN IP4 127.0.0.1\r\n...",
  "type": "offer",
  "video_path": null
}
```

**Response:**
```json
{
  "sdp": "v=0\r\no=- 987654321 2 IN IP4 127.0.0.1\r\n...",
  "type": "answer",
  "session_id": "abc123-def456-ghi789"
}
```

**Status Codes:**
- `200 OK`: Offer processed successfully
- `400 Bad Request`: Invalid offer format
- `500 Internal Server Error`: Server error processing offer

##### `GET /api/sessions`
List all active WebRTC sessions.

**Response:**
```json
{
  "active_sessions": [
    "abc123-def456-ghi789",
    "xyz789-uvw456-rst123"
  ],
  "count": 2
}
```

##### `GET /api/session/{session_id}`
Get information about a specific session.

**Parameters:**
- `session_id` (path): Session UUID

**Response:**
```json
{
  "session_id": "abc123-def456-ghi789",
  "connection_state": "connected",
  "ice_connection_state": "connected",
  "ice_gathering_state": "complete",
  "signaling_state": "stable"
}
```

##### `DELETE /api/session/{session_id}`
Manually close a WebRTC session.

**Parameters:**
- `session_id` (path): Session UUID

**Response:**
```json
{
  "status": "success",
  "message": "Session abc123-def456-ghi789 closed",
  "active_connections": 1
}
```

##### `GET /api/health`
Health check for signaling service.

**Response:**
```json
{
  "status": "healthy",
  "active_connections": 2,
  "service": "WebRTC Signaling"
}
```

## 🧪 Testing

### 1. Prepare a Test Video

Place a video file in the project root or specify the path in `config.py`:

```bash
# Download a sample video (example)
wget https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4 -O sample_video.mp4
```

Or use any `.mp4`, `.avi`, or other video format supported by OpenCV.

### 2. Start the Backend

```bash
python main.py
```

You should see:
```
======================================================================
Starting AI Video Streaming Backend v1.0.0
======================================================================
✓ Video file found: sample_video.mp4
✓ CORS: Allowing all origins (development mode)
✓ Application started successfully
======================================================================
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 3. Test API Endpoints

#### Test Health Check

```bash
curl http://localhost:8000/health
```

#### Test Info Endpoint

```bash
curl http://localhost:8000/info
```

#### View API Documentation

Open your browser and navigate to:
- http://localhost:8000/docs (Swagger UI)
- http://localhost:8000/redoc (ReDoc)

### 4. Test WebRTC Connection

You can test the WebRTC connection using the interactive API docs:

1. Go to http://localhost:8000/docs
2. Find the `POST /api/offer` endpoint
3. Click "Try it out"
4. Paste a valid SDP offer (from your React client)
5. Execute the request

### 5. Integration Testing with React Frontend

Create a simple React component to test the WebRTC connection:

```javascript
// Example React component
const VideoPlayer = () => {
  const [pc, setPc] = useState(null);
  const videoRef = useRef(null);

  const connect = async () => {
    const peerConnection = new RTCPeerConnection({
      iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
    });

    peerConnection.ontrack = (event) => {
      videoRef.current.srcObject = event.streams[0];
    };

    // Create offer
    const offer = await peerConnection.createOffer();
    await peerConnection.setLocalDescription(offer);

    // Send to backend
    const response = await fetch('http://localhost:8000/api/offer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sdp: offer.sdp,
        type: offer.type
      })
    });

    const answer = await response.json();
    await peerConnection.setRemoteDescription(answer);
    
    setPc(peerConnection);
  };

  return (
    <div>
      <video ref={videoRef} autoPlay playsInline />
      <button onClick={connect}>Connect</button>
    </div>
  );
};
```

## 📁 Project Structure

```
visiongaurd-backend/
│
├── main.py              # FastAPI application entry point
├── config.py            # Configuration and constants
├── signaling.py         # WebRTC signaling endpoints (OpenAPI compliant)
├── ai_stream.py         # Custom aiortc VideoStreamTrack
├── model.py             # AI model and frame processing
├── requirements.txt     # Python dependencies
├── README.md            # This file
│
├── env/                 # Virtual environment (not in git)
├── sample_video.mp4     # Test video file (not in git)
│
└── note/                # Development notes
    └── prompt.md
```

### Module Descriptions

#### `config.py`
- Configuration constants
- Environment variable handling
- STUN server configuration
- Video and server settings

#### `model.py`
- `AIProcessor` class for video capture
- Frame reading with OpenCV
- AI processing interface (mocked for now)
- Async frame delivery

#### `ai_stream.py`
- `AIProcessedStream` class (extends `VideoStreamTrack`)
- Frame rate control (30 FPS)
- NumPy to av.VideoFrame conversion
- Timestamp management

#### `signaling.py`
- FastAPI router for WebRTC signaling
- SDP offer/answer exchange
- Peer connection management
- Session lifecycle handling
- **OpenAPI 3.0 compliant** with Pydantic models

#### `main.py`
- FastAPI application setup
- CORS middleware configuration
- Router inclusion
- Lifecycle management (startup/shutdown)
- Error handlers
- **OpenAPI documentation** at `/docs` and `/redoc`

## 🔄 Future Enhancements

### 1. Integrate Real AI Model

Replace the mock AI processing in `model.py`:

```python
# Example: YOLOv8 integration
from ultralytics import YOLO

class AIProcessor:
    def _load_ai_model(self):
        self.model = YOLO('yolov8n.pt')
        self.model_loaded = True
    
    def _run_inference(self, frame: np.ndarray):
        results = self.model(frame)
        return results
    
    def _draw_detections(self, frame: np.ndarray, detections):
        # Draw bounding boxes and labels
        for detection in detections:
            # ... drawing logic
        return frame
```

### 2. Add Authentication

Implement JWT authentication for API endpoints:

```python
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

@router.post("/offer")
async def handle_offer(
    offer: OfferRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    # Verify JWT token
    # ...
```

### 3. Support Live CCTV Streams

Extend `AIProcessor` to support RTSP streams:

```python
def initialize(self, source: str):
    if source.startswith('rtsp://'):
        self.cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
    else:
        self.cap = cv2.VideoCapture(source)
```

### 4. Add Redis for Session Management

Use Redis for distributed session storage:

```python
import redis

redis_client = redis.Redis(host='localhost', port=6379, db=0)

# Store session info
redis_client.setex(
    f"session:{session_id}",
    3600,  # 1 hour TTL
    json.dumps(session_info)
)
```

### 5. Implement Recording

Add endpoint to record processed video:

```python
@router.post("/api/record/{session_id}")
async def start_recording(session_id: str):
    # Start recording processed frames
    pass
```

### 6. Add Metrics and Monitoring

Integrate Prometheus for metrics:

```python
from prometheus_client import Counter, Histogram

frames_processed = Counter('frames_processed_total', 'Total frames processed')
processing_time = Histogram('frame_processing_seconds', 'Frame processing time')
```

## 🐛 Troubleshooting

### Video File Not Found

```
⚠ Video file not found: sample_video.mp4
```

**Solution**: Place a video file in the project root or update `VIDEO_FILE_PATH` in `config.py`.

### Port Already in Use

```
ERROR: [Errno 48] Address already in use
```

**Solution**: Change the port in `config.py` or kill the process using port 8000:
```bash
lsof -ti:8000 | xargs kill -9
```

### FFmpeg Not Found

```
ImportError: No module named 'av'
```

**Solution**: Install FFmpeg libraries:
```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg libavformat-dev libavcodec-dev

# macOS
brew install ffmpeg
```

### WebRTC Connection Fails

**Solution**: 
1. Check STUN server configuration in `config.py`
2. Verify CORS settings allow your frontend origin
3. Check browser console for WebRTC errors
4. Ensure both client and server can reach STUN servers

## 📄 License

[Add your license here]

## 👥 Contributors

[Add contributors here]

## 📞 Support

For issues and questions:
- Open an issue on GitHub
- Contact: [your-email@example.com]

---

**Built with ❤️ using FastAPI and aiortc**

## 📖 Additional Documentation

For more detailed information, please refer to the following documentation files in the `doc/` folder:

- **[API Documentation](doc/API_DOCUMENTATION.md)** - Detailed API reference and examples
- **[Environment Setup](doc/ENVIRONMENT_SETUP.md)** - Step-by-step environment configuration
- **[How to Run](doc/HOW_TO_RUN.md)** - Detailed instructions for running the application
- **[Model Optimization](doc/MODEL_OPTIMIZATION.md)** - AI model optimization techniques
- **[WebRTC Architecture](doc/WEBRTC_WEBSOCKET_ARCHITECTURE.md)** - WebRTC and WebSocket implementation details
- **[Import Fix Applied](doc/IMPORT_FIX_APPLIED.md)** - Documentation of import fixes
- **[Files to Delete](doc/FILES_TO_DELETE.md)** - Cleanup and maintenance guide

