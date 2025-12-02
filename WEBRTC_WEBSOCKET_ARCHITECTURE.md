# WebRTC + WebSocket Multi-Stream Anomaly Detection - Frontend Guide

## Architecture Overview

**Multiple video streams per user** → **Single WebSocket per user** for all alerts

- Each user can have unlimited video streams (cameras, uploads)
- Each stream = separate WebRTC connection with unique `stream_id`
- One WebSocket at `/ws/alerts/{user_id}` receives alerts from ALL user streams
- Each alert includes `stream_id` to identify which stream detected the anomaly

### ⚠️ Important: No `session_id` - Uses `user_id` + `stream_id`

The backend **does NOT return `session_id`**. Instead, it uses a dual-identifier system:

| Identifier | Purpose | Scope |
|------------|---------|-------|
| `user_id` | Identifies the user | Constant across all user's streams |
| `stream_id` | Identifies each video stream | Unique per WebRTC connection |

**What you send:** `user_id` in the offer  
**What you receive:** `user_id` + `stream_id` in the answer  
**WebSocket path:** `/ws/alerts/{user_id}` (NOT `/ws/alerts/{session_id}`)

---

## Backend Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/offer` | POST | Create new video stream connection |
| `/ws/alerts/{user_id}` | WebSocket | Receive anomaly alerts from all user streams |
| `/api/users/{user_id}/streams` | GET | List user's active streams |
| `/api/users/{user_id}/streams/{stream_id}` | DELETE | Close specific stream |
| `/api/users/{user_id}` | DELETE | Close all user streams |
| `/api/stats` | GET | Global statistics |

---

## Message Formats

### 1. WebRTC Offer (HTTP POST)

**Request to `/api/offer`:**
```json
{
  "sdp": "v=0\r\no=- ...",
  "type": "offer",
  "user_id": "user123",
  "stream_metadata": {
    "camera": "front_door",
    "location": "entrance"
  }
}
```

**Response:**
```json
{
  "sdp": "v=0\r\no=- ...",
  "type": "answer",
  "user_id": "user123",
  "stream_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**⚠️ Note:** Backend returns `user_id` + `stream_id` (NOT `session_id`)

### 2. WebSocket Alert

**Connect to:** `ws://localhost:8000/ws/alerts/{user_id}`

**⚠️ Note:** Use `user_id` in path (NOT `session_id`)

**Server sends (on anomaly):**
```json
{
  "type": "anomaly_detected",
  "user_id": "user123",
  "stream_id": "550e8400-...",
  "result": {
    "person_id": 1,
    "frame_number": 245,
    "score": -2.456,
    "is_abnormal": true,
    "classification": "Abnormal",
    "confidence": "High",
    "bbox": { "x": 120, "y": 50, "w": 180, "h": 350 }
  },
  "annotated_frame": "base64_encoded_jpeg",
  "frame_format": "jpeg"
}
```

---

## Frontend Implementation

### Step 1: Setup User ID

```javascript
const userId = localStorage.getItem('userId') || 'user_' + crypto.randomUUID();
localStorage.setItem('userId', userId);
```

### Step 2: Connect WebSocket (Once)

```javascript
const websocket = new WebSocket(`ws://localhost:8000/ws/alerts/${userId}`);

websocket.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'anomaly_detected') {
    console.log(`🚨 Anomaly from stream: ${data.stream_id}`);
    handleAnomaly(data);
  }
};
```

### Step 3: Add Video Stream

```javascript
async function addVideoStream(mediaStream, metadata) {
  // 1. Create peer connection
  const pc = new RTCPeerConnection({
    iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
  });
  
  // 2. Add video track
  mediaStream.getTracks().forEach(track => {
    pc.addTrack(track, mediaStream);
  });
  
  // 3. Create offer
  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  
  // 4. Wait for ICE gathering
  await new Promise((resolve) => {
    if (pc.iceGatheringState === 'complete') resolve();
    else pc.addEventListener('icegatheringstatechange', () => {
      if (pc.iceGatheringState === 'complete') resolve();
    });
  });
  
  // 5. Send offer to backend
  const response = await fetch('http://localhost:8000/api/offer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      sdp: pc.localDescription.sdp,
      type: pc.localDescription.type,
      user_id: userId,
      stream_metadata: metadata
    })
  });
  
  const { sdp, type, stream_id } = await response.json();
  
  // 6. Complete handshake
  await pc.setRemoteDescription({ sdp, type });
  
  console.log(`✅ Stream ${metadata.camera} connected: ${stream_id}`);
  return { peerConnection: pc, streamId: stream_id };
}
```

### Step 4: Multi-Camera Example

```javascript
// Connect WebSocket once
const ws = new WebSocket(`ws://localhost:8000/ws/alerts/${userId}`);
const streams = new Map(); // streamId -> { pc, metadata }

ws.onmessage = (event) => {
  const alert = JSON.parse(event.data);
  if (alert.type === 'anomaly_detected') {
    const streamInfo = streams.get(alert.stream_id);
    console.log(`🚨 Anomaly at ${streamInfo.metadata.camera}`);
    displayAlert(alert);
  }
};

// Add multiple cameras
const camera1 = await navigator.mediaDevices.getUserMedia({ video: true });
const stream1 = await addVideoStream(camera1, { camera: 'front_door' });
streams.set(stream1.streamId, { pc: stream1.peerConnection, metadata: { camera: 'front_door' } });

const camera2 = await navigator.mediaDevices.getUserMedia({ video: true });
const stream2 = await addVideoStream(camera2, { camera: 'back_door' });
streams.set(stream2.streamId, { pc: stream2.peerConnection, metadata: { camera: 'back_door' } });

// Upload video file
const fileInput = document.getElementById('video-file');
const video = document.createElement('video');
video.src = URL.createObjectURL(fileInput.files[0]);
await video.play();
const fileStream = video.captureStream(30);
const stream3 = await addVideoStream(fileStream, { camera: 'uploaded_video', filename: fileInput.files[0].name });
streams.set(stream3.streamId, { pc: stream3.peerConnection, metadata: { camera: 'uploaded_video' } });
```

### Step 5: Handle Alerts

```javascript
function displayAlert(alert) {
  const { stream_id, result, annotated_frame } = alert;
  
  // Get stream metadata
  const streamInfo = streams.get(stream_id);
  const cameraName = streamInfo?.metadata.camera || 'Unknown';
  
  // Display alert
  const alertDiv = document.createElement('div');
  alertDiv.innerHTML = `
    <h3>⚠️ Anomaly at ${cameraName}</h3>
    <img src="data:image/jpeg;base64,${annotated_frame}" />
    <p>Person ${result.person_id} - ${result.confidence}</p>
    <p>Stream: ${stream_id}</p>
  `;
  document.getElementById('alerts').appendChild(alertDiv);
  
  // Play sound
  new Audio('/alert.mp3').play();
  
  // Browser notification
  if (Notification.permission === 'granted') {
    new Notification(`Anomaly at ${cameraName}`, {
      body: `Person ${result.person_id} detected`
    });
  }
}
```

### Step 6: Close Stream

```javascript
async function closeStream(streamId) {
  const streamInfo = streams.get(streamId);
  if (!streamInfo) return;
  
  // Close on backend
  await fetch(`http://localhost:8000/api/users/${userId}/streams/${streamId}`, {
    method: 'DELETE'
  });
  
  // Close peer connection
  streamInfo.pc.close();
  streams.delete(streamId);
  
  console.log(`✅ Closed stream: ${streamId}`);
}

async function closeAllStreams() {
  // Close all on backend
  await fetch(`http://localhost:8000/api/users/${userId}`, {
    method: 'DELETE'
  });
  
  // Close all peer connections
  for (const [streamId, info] of streams) {
    info.pc.close();
  }
  streams.clear();
  
  // Close WebSocket
  ws.close();
}
```

---

## Complete Client Class

```javascript
class AnomalyDetectionClient {
  constructor(userId, backendUrl = 'http://localhost:8000') {
    this.userId = userId;
    this.backendUrl = backendUrl;
    this.wsUrl = backendUrl.replace('http', 'ws');
    this.websocket = null;
    this.streams = new Map(); // streamId -> { pc, metadata }
  }
  
  async connect() {
    this.websocket = new WebSocket(`${this.wsUrl}/ws/alerts/${this.userId}`);
    
    return new Promise((resolve, reject) => {
      this.websocket.onopen = () => {
        console.log('✅ WebSocket connected');
        resolve();
      };
      this.websocket.onerror = (error) => reject(error);
    });
  }
  
  onAnomaly(callback) {
    this.websocket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'anomaly_detected') {
        callback(data);
      }
    };
  }
  
  async addStream(mediaStream, metadata) {
    const pc = new RTCPeerConnection({
      iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
    });
    
    mediaStream.getTracks().forEach(track => pc.addTrack(track, mediaStream));
    
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    
    await new Promise((resolve) => {
      if (pc.iceGatheringState === 'complete') resolve();
      else pc.addEventListener('icegatheringstatechange', () => {
        if (pc.iceGatheringState === 'complete') resolve();
      });
    });
    
    const response = await fetch(`${this.backendUrl}/api/offer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sdp: pc.localDescription.sdp,
        type: pc.localDescription.type,
        user_id: this.userId,
        stream_metadata: metadata
      })
    });
    
    const { sdp, type, stream_id } = await response.json();
    await pc.setRemoteDescription({ sdp, type });
    
    this.streams.set(stream_id, { pc, metadata });
    console.log(`✅ Stream added: ${metadata.camera} (${stream_id})`);
    
    return stream_id;
  }
  
  async removeStream(streamId) {
    const stream = this.streams.get(streamId);
    if (!stream) return;
    
    await fetch(`${this.backendUrl}/api/users/${this.userId}/streams/${streamId}`, {
      method: 'DELETE'
    });
    
    stream.pc.close();
    this.streams.delete(streamId);
  }
  
  async disconnect() {
    await fetch(`${this.backendUrl}/api/users/${this.userId}`, {
      method: 'DELETE'
    });
    
    for (const [_, stream] of this.streams) {
      stream.pc.close();
    }
    this.streams.clear();
    
    if (this.websocket) {
      this.websocket.close();
    }
  }
  
  getStreamMetadata(streamId) {
    return this.streams.get(streamId)?.metadata;
  }
}

// Usage
const client = new AnomalyDetectionClient('user123');
await client.connect();

client.onAnomaly((alert) => {
  const metadata = client.getStreamMetadata(alert.stream_id);
  console.log(`🚨 Anomaly at ${metadata.camera}`);
  displayAlert(alert);
});

// Add cameras
const camera1 = await navigator.mediaDevices.getUserMedia({ video: true });
await client.addStream(camera1, { camera: 'front_door', location: 'entrance' });

const camera2 = await navigator.mediaDevices.getUserMedia({ video: true });
await client.addStream(camera2, { camera: 'back_door', location: 'rear' });

// Later: cleanup
await client.disconnect();
```

---

## Key Points

1. **No `session_id`** - Backend uses `user_id` + `stream_id` instead
2. **One WebSocket per user** - Connect at `/ws/alerts/{user_id}` before adding streams
3. **Multiple WebRTC connections** - Call `/api/offer` for each video source
4. **Alert identification** - Each alert includes `stream_id` to identify source
5. **Stream metadata** - Pass metadata in offer to track camera names/locations
6. **Independent lifecycle** - Streams can be added/removed independently
7. **Cleanup** - Close streams via DELETE endpoints or disconnect entire user

---

## Architecture Comparison

### ❌ Old Single-Stream Architecture (Deprecated)

```javascript
// Old way - session_id per connection
const response = await fetch('/api/offer', {
  body: JSON.stringify({ sdp, type })
});
const { session_id } = await response.json();

// WebSocket per session
const ws = new WebSocket(`/ws/alerts/${session_id}`);
```

**Limitations:**
- One stream per connection
- WebSocket path uses `session_id`
- No multi-stream support
- Returns: `{ sdp, type, session_id }`

### ✅ New Multi-Stream Architecture (Current)

```javascript
// New way - user_id with multiple streams
const response = await fetch('/api/offer', {
  body: JSON.stringify({ 
    sdp, 
    type, 
    user_id: 'user123',
    stream_metadata: { camera: 'front_door' }
  })
});
const { user_id, stream_id } = await response.json();

// One WebSocket for all user streams
const ws = new WebSocket(`/ws/alerts/${user_id}`);
```

**Benefits:**
- Multiple streams per user
- WebSocket path uses `user_id`
- Single WebSocket for all streams
- Returns: `{ sdp, type, user_id, stream_id }`
- Each alert includes `stream_id` for identification

---

## Testing Checklist

- [ ] Connect WebSocket with user_id
- [ ] Add first video stream (receive stream_id)
- [ ] Add second video stream (different stream_id)
- [ ] Verify alerts include correct stream_id
- [ ] Close specific stream
- [ ] Verify other streams still active
- [ ] Close all streams
- [ ] Verify WebSocket cleanup
