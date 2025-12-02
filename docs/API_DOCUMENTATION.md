# API Documentation

## OpenAPI Specification

This API follows the **OpenAPI 3.0** specification. Full interactive documentation is available at:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON Schema**: http://localhost:8000/openapi.json

## Quick Start

### 1. Start the Server

```bash
python main.py
```

### 2. Access Interactive Documentation

Navigate to http://localhost:8000/docs in your browser.

### 3. Test Endpoints

Use the interactive Swagger UI to test all endpoints directly from your browser.

## API Overview

### Base URL

```
http://localhost:8000
```

### Content Type

All requests and responses use:
```
Content-Type: application/json
```

### Authentication

Currently, no authentication is required. For production, implement:
- JWT Bearer tokens
- API keys
- OAuth 2.0

## Endpoints by Category

### Root Endpoints

#### GET `/`
**Service Discovery Endpoint**

Returns API information and available endpoints.

**Response Example:**
```json
{
  "service": "AI Video Streaming Backend",
  "version": "1.0.0",
  "status": "running",
  "endpoints": {
    "docs": "/docs",
    "redoc": "/redoc",
    "api": {
      "offer": "/api/offer",
      "sessions": "/api/sessions"
    }
  }
}
```

#### GET `/health`
**Health Check Endpoint**

Monitor application health status.

**Response Example:**
```json
{
  "status": "healthy",
  "service": "AI Video Streaming Backend",
  "version": "1.0.0",
  "video_available": true,
  "message": "Service is running"
}
```

**Status Values:**
- `healthy` - All systems operational
- `degraded` - Service running with limitations

#### GET `/info`
**Detailed Service Information**

Get complete configuration and capabilities.

**Response Example:**
```json
{
  "application": {
    "name": "AI Video Streaming Backend",
    "version": "1.0.0",
    "description": "Real-time AI video processing with WebRTC streaming"
  },
  "video": {
    "path": "sample_video.mp4",
    "exists": true,
    "target_fps": 30,
    "resolution": "640x480"
  },
  "webrtc": {
    "stun_servers": [
      {"urls": "stun:stun.l.google.com:19302"}
    ]
  },
  "ai": {
    "processing_enabled": true,
    "status": "mocked (ready for implementation)"
  },
  "cors": {
    "allowed_origins": ["*"]
  }
}
```

---

### WebRTC Signaling

#### POST `/api/offer`
**Exchange SDP Offer/Answer**

Main WebRTC signaling endpoint for establishing peer connections.

**Request Body:**
```json
{
  "sdp": "v=0\r\no=- 123456789 2 IN IP4 127.0.0.1\r\n...",
  "type": "offer",
  "video_path": null
}
```

**Request Schema:**
- `sdp` (string, required): Session Description Protocol offer from client
- `type` (string, required): Must be "offer"
- `video_path` (string, optional): Custom video file path

**Response (200 OK):**
```json
{
  "sdp": "v=0\r\no=- 987654321 2 IN IP4 127.0.0.1\r\n...",
  "type": "answer",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response Schema:**
- `sdp` (string): SDP answer to complete WebRTC handshake
- `type` (string): Will be "answer"
- `session_id` (string): UUID for tracking this session

**Error Responses:**

**400 Bad Request:**
```json
{
  "detail": "Expected type 'offer', got 'answer'"
}
```

**500 Internal Server Error:**
```json
{
  "detail": "Failed to create video stream: Video file not found"
}
```

**Process Flow:**
1. Client creates RTCPeerConnection
2. Client generates SDP offer
3. Client sends offer to this endpoint
4. Server creates peer connection with video track
5. Server returns SDP answer
6. Client applies answer to complete connection
7. Video streaming begins automatically

---

### Session Management

#### GET `/api/sessions`
**List Active Sessions**

Get all currently active WebRTC sessions.

**Response Example:**
```json
{
  "active_sessions": [
    "550e8400-e29b-41d4-a716-446655440000",
    "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
  ],
  "count": 2
}
```

#### GET `/api/session/{session_id}`
**Get Session Information**

Retrieve detailed information about a specific session.

**Path Parameters:**
- `session_id` (string): Session UUID from offer/answer exchange

**Response (200 OK):**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "connection_state": "connected",
  "ice_connection_state": "connected",
  "ice_gathering_state": "complete",
  "signaling_state": "stable"
}
```

**Connection States:**
- `new` - Initial state
- `connecting` - Connection in progress
- `connected` - Successfully connected
- `disconnected` - Connection lost (may recover)
- `failed` - Connection failed permanently
- `closed` - Connection closed cleanly

**Response (404 Not Found):**
```json
{
  "detail": "Session 550e8400-e29b-41d4-a716-446655440000 not found"
}
```

#### DELETE `/api/session/{session_id}`
**Close Session**

Manually terminate a WebRTC session and release resources.

**Path Parameters:**
- `session_id` (string): Session UUID to close

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Session 550e8400-e29b-41d4-a716-446655440000 closed",
  "active_connections": 1
}
```

**Response (404 Not Found):**
```json
{
  "detail": "Session 550e8400-e29b-41d4-a716-446655440000 not found"
}
```

#### GET `/api/health`
**Signaling Service Health**

Health check specifically for the WebRTC signaling service.

**Response Example:**
```json
{
  "status": "healthy",
  "active_connections": 2,
  "service": "WebRTC Signaling"
}
```

---

## Client Integration Examples

### JavaScript/React WebRTC Client

```javascript
// Example React component for WebRTC connection
import React, { useRef, useEffect, useState } from 'react';

function VideoPlayer() {
  const videoRef = useRef(null);
  const [pc, setPc] = useState(null);
  const [sessionId, setSessionId] = useState(null);

  const connect = async () => {
    try {
      // Create peer connection
      const peerConnection = new RTCPeerConnection({
        iceServers: [
          { urls: 'stun:stun.l.google.com:19302' }
        ]
      });

      // Handle incoming video track
      peerConnection.ontrack = (event) => {
        console.log('Received video track');
        if (videoRef.current) {
          videoRef.current.srcObject = event.streams[0];
        }
      };

      // Handle ICE connection state changes
      peerConnection.oniceconnectionstatechange = () => {
        console.log('ICE Connection State:', peerConnection.iceConnectionState);
      };

      // Create offer
      const offer = await peerConnection.createOffer({
        offerToReceiveVideo: true,
        offerToReceiveAudio: false
      });

      await peerConnection.setLocalDescription(offer);

      // Send offer to backend
      const response = await fetch('http://localhost:8000/api/offer', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          sdp: offer.sdp,
          type: offer.type
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const answer = await response.json();
      console.log('Received answer, session ID:', answer.session_id);

      // Set remote description (answer)
      await peerConnection.setRemoteDescription({
        type: answer.type,
        sdp: answer.sdp
      });

      setPc(peerConnection);
      setSessionId(answer.session_id);
      
    } catch (error) {
      console.error('Error connecting:', error);
    }
  };

  const disconnect = async () => {
    if (pc) {
      pc.close();
      setPc(null);
    }

    if (sessionId) {
      // Notify backend to close session
      await fetch(`http://localhost:8000/api/session/${sessionId}`, {
        method: 'DELETE'
      });
      setSessionId(null);
    }
  };

  useEffect(() => {
    return () => {
      if (pc) {
        pc.close();
      }
    };
  }, [pc]);

  return (
    <div>
      <video 
        ref={videoRef} 
        autoPlay 
        playsInline 
        style={{ width: '100%', maxWidth: '640px' }}
      />
      <div>
        <button onClick={connect} disabled={pc !== null}>
          Connect
        </button>
        <button onClick={disconnect} disabled={pc === null}>
          Disconnect
        </button>
      </div>
      {sessionId && <p>Session ID: {sessionId}</p>}
    </div>
  );
}

export default VideoPlayer;
```

### Python Client Example

```python
import asyncio
import aiohttp
from aiortc import RTCPeerConnection, RTCSessionDescription

async def connect_to_stream():
    """Connect to the video stream"""
    
    # Create peer connection
    pc = RTCPeerConnection()
    
    # Handle incoming tracks
    @pc.on("track")
    async def on_track(track):
        print(f"Received {track.kind} track")
        if track.kind == "video":
            # Process video frames here
            while True:
                frame = await track.recv()
                print(f"Received frame: {frame.width}x{frame.height}")
    
    # Create offer
    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    
    # Send offer to backend
    async with aiohttp.ClientSession() as session:
        async with session.post(
            'http://localhost:8000/api/offer',
            json={
                'sdp': pc.localDescription.sdp,
                'type': pc.localDescription.type
            }
        ) as response:
            answer_data = await response.json()
            print(f"Session ID: {answer_data['session_id']}")
            
            # Set remote description
            answer = RTCSessionDescription(
                sdp=answer_data['sdp'],
                type=answer_data['type']
            )
            await pc.setRemoteDescription(answer)
    
    # Keep connection alive
    await asyncio.sleep(30)
    
    # Close connection
    await pc.close()

# Run the client
asyncio.run(connect_to_stream())
```

### cURL Examples

#### Test Health Check
```bash
curl http://localhost:8000/health
```

#### Get Service Info
```bash
curl http://localhost:8000/info
```

#### List Active Sessions
```bash
curl http://localhost:8000/api/sessions
```

#### Get Session Info
```bash
curl http://localhost:8000/api/session/550e8400-e29b-41d4-a716-446655440000
```

#### Close Session
```bash
curl -X DELETE http://localhost:8000/api/session/550e8400-e29b-41d4-a716-446655440000
```

---

## Error Handling

### Standard Error Response Format

```json
{
  "detail": "Error message description"
}
```

### HTTP Status Codes

- `200 OK` - Request successful
- `400 Bad Request` - Invalid request format or parameters
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server-side error

### Common Errors

#### Video File Not Found
```json
{
  "detail": "Failed to create video stream: Video file not found"
}
```

**Solution**: Ensure video file exists at configured path.

#### Invalid SDP Offer
```json
{
  "detail": "Expected type 'offer', got 'answer'"
}
```

**Solution**: Send correct SDP offer from client.

#### Session Not Found
```json
{
  "detail": "Session 550e8400-e29b-41d4-a716-446655440000 not found"
}
```

**Solution**: Use valid session ID from offer/answer exchange.

---

## Rate Limiting

Currently, no rate limiting is implemented. For production deployment, consider:

- Request rate limiting per IP
- Connection limits per client
- API key-based quotas

---

## WebRTC Considerations

### STUN Servers

Default STUN servers are configured for NAT traversal:
- `stun:stun.l.google.com:19302`

For production, consider:
- Dedicated STUN servers
- TURN servers for restricted networks
- Multiple fallback servers

### Browser Compatibility

Tested with:
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

### Network Requirements

- UDP ports for WebRTC (typically 49152-65535)
- HTTPS required for production (browser security)
- Low latency network for real-time streaming

---

## Monitoring and Observability

### Health Checks

Monitor these endpoints:
- `GET /health` - Overall application health
- `GET /api/health` - Signaling service health

### Metrics to Track

- Active connection count
- Connection success/failure rate
- Average connection duration
- Frame processing rate
- CPU and memory usage

### Logging

All logs include:
- Timestamp
- Log level (INFO, WARNING, ERROR)
- Component name
- Session ID (when applicable)
- Detailed message

---

## Security Considerations

### Current State (Development)

⚠️ **Warning**: This is a development configuration

- No authentication required
- CORS allows all origins
- No rate limiting
- No encryption (HTTP)

### Production Recommendations

1. **Enable HTTPS**
   ```python
   uvicorn main:app --ssl-keyfile=key.pem --ssl-certfile=cert.pem
   ```

2. **Add Authentication**
   - Implement JWT tokens
   - Add API key validation
   - Use OAuth 2.0 for user authentication

3. **Restrict CORS**
   ```python
   ALLOWED_ORIGINS = [
       "https://yourdomain.com",
       "https://app.yourdomain.com"
   ]
   ```

4. **Add Rate Limiting**
   ```python
   from slowapi import Limiter
   
   limiter = Limiter(key_func=get_remote_address)
   app.state.limiter = limiter
   ```

5. **Input Validation**
   - Validate all user inputs
   - Sanitize file paths
   - Limit SDP size

6. **Network Security**
   - Use firewall rules
   - Implement DDoS protection
   - Monitor for abuse

---

## Support and Resources

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Schema**: http://localhost:8000/openapi.json
- **FastAPI Documentation**: https://fastapi.tiangolo.com
- **aiortc Documentation**: https://aiortc.readthedocs.io
- **WebRTC Specification**: https://webrtc.org

---

**Version**: 1.0.0  
**Last Updated**: November 7, 2025
