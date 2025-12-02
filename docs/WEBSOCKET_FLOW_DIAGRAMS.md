# WebSocket Connection Flow Diagram

## Connection Lifecycle

```
┌──────────────┐                                    ┌──────────────┐
│   Frontend   │                                    │   Backend    │
│  (React App) │                                    │  (FastAPI)   │
└──────┬───────┘                                    └──────┬───────┘
       │                                                   │
       │ 1. Connect with JWT token                        │
       │ ws://backend/ws/alerts/{user_id}?token=XXX       │
       ├──────────────────────────────────────────────────>│
       │                                                   │
       │                 2. Authenticate user              │
       │                    Verify token                   │
       │                    Check user exists              │
       │                                                   │
       │ 3. Connection accepted                            │
       │<──────────────────────────────────────────────────┤
       │                                                   │
       │                                    4. Start       │
       │                                    heartbeat task │
       │                                    (ping every 30s)
       │                                                   │
       ├───────────────── Connected ────────────────────── ┤
       │                                                   │
       │ 5. Frontend starts                                │
       │    heartbeat monitoring                           │
       │    (ping every 30s)                               │
       │                                                   │
```

## Heartbeat Loop

```
┌──────────────┐                                    ┌──────────────┐
│   Frontend   │                                    │   Backend    │
└──────┬───────┘                                    └──────┬───────┘
       │                                                   │
       │              Every 30 seconds                     │
       │                                                   │
       │ {"type": "ping", "timestamp": "..."}              │
       ├──────────────────────────────────────────────────>│
       │                                                   │
       │                                    Update         │
       │                                    last_heartbeat │
       │                                                   │
       │ {"type": "pong", "timestamp": "..."}              │
       │<──────────────────────────────────────────────────┤
       │                                                   │
       │ Update last_heartbeat                             │
       │                                                   │
       │                                                   │
       │              Server ping (every 30s)              │
       │                                                   │
       │ {"type": "ping", "timestamp": "..."}              │
       │<──────────────────────────────────────────────────┤
       │                                                   │
       │ {"type": "pong", "timestamp": "..."}              │
       ├──────────────────────────────────────────────────>│
       │                                                   │
       │                                    Update         │
       │                                    last_heartbeat │
       │                                                   │
```

## Anomaly Detection Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Frontend   │     │   Backend    │     │   WebRTC     │     │ AI Pipeline  │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │                    │
       │                    │ Video stream       │                    │
       │                    │ via WebRTC         │                    │
       │                    │<───────────────────┤                    │
       │                    │                    │                    │
       │                    │ Process frame      │                    │
       │                    ├────────────────────────────────────────>│
       │                    │                    │                    │
       │                    │                    │    Detect anomaly  │
       │                    │                    │    (person found)  │
       │                    │                    │                    │
       │                    │ Detection result   │                    │
       │                    │<────────────────────────────────────────┤
       │                    │                    │                    │
       │                    │ Send alert via WS  │                    │
       │                    │ {                  │                    │
       │                    │   type: "anomaly_detected",              │
       │                    │   stream_id: "...", │                   │
       │                    │   result: {...},    │                   │
       │                    │   frame: "base64"   │                   │
       │                    │ }                   │                   │
       │<───────────────────┤                    │                    │
       │                    │                    │                    │
       │ Display alert      │                    │                    │
       │ Show frame         │                    │                    │
       │                    │                    │                    │
       │ {"type": "ack", "stream_id": "..."}     │                    │
       ├────────────────────>│                    │                    │
       │                    │                    │                    │
       │                    │ Log acknowledgment │                    │
       │                    │                    │                    │
```

## Reconnection Flow

```
┌──────────────┐                                    ┌──────────────┐
│   Frontend   │                                    │   Backend    │
└──────┬───────┘                                    └──────┬───────┘
       │                                                   │
       │ Connection lost (network issue)                   │
       │ ╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳│
       │                                                   │
       │ Detect disconnect                                 │
       │ connected = false                                 │
       │                                                   │
       │ Wait 1 second (initial delay)                     │
       │                                                   │
       │ Reconnect attempt #1                              │
       ├──────────────────────────────────────────────────>│
       │                                                   │
       │ Failed (network still down)                       │
       │ ╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳│
       │                                                   │
       │ Wait 1.5 seconds (1 × 1.5)                        │
       │                                                   │
       │ Reconnect attempt #2                              │
       ├──────────────────────────────────────────────────>│
       │                                                   │
       │ Failed                                            │
       │ ╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳│
       │                                                   │
       │ Wait 2.25 seconds (1.5 × 1.5)                     │
       │                                                   │
       │ Reconnect attempt #3                              │
       ├──────────────────────────────────────────────────>│
       │                                                   │
       │ Success! Connected                                │
       │<──────────────────────────────────────────────────┤
       │                                                   │
       │ Reset reconnect delay to 1s                       │
       │ Reset reconnect attempts to 0                     │
       │ Start heartbeat monitoring                        │
       │                                                   │
       ├───────────────── Connected ────────────────────── ┤
       │                                                   │
```

## Heartbeat Timeout Flow

```
┌──────────────┐                                    ┌──────────────┐
│   Frontend   │                                    │   Backend    │
└──────┬───────┘                                    └──────┬───────┘
       │                                                   │
       │ {"type": "ping", "timestamp": "..."}              │
       ├──────────────────────────────────────────────────>│
       │                                                   │
       │ Start 60s timeout                                 │
       │ Waiting for pong...                               │
       │                                                   │
       │ (Backend crashes or network issue)                │
       │                                                   │
       │ ... 60 seconds pass ...                           │
       │                                                   │
       │ No pong received!                                 │
       │ Timeout triggered                                 │
       │                                                   │
       │ Close connection                                  │
       │ connected = false                                 │
       │                                                   │
       │ Start reconnection with                           │
       │ exponential backoff                               │
       │                                                   │
       │ Reconnect attempt                                 │
       ├──────────────────────────────────────────────────>│
       │                                                   │
       │ Connection accepted                               │
       │<──────────────────────────────────────────────────┤
       │                                                   │
       ├───────────────── Connected ────────────────────── ┤
       │                                                   │
```

## Connection Monitoring

```
┌──────────────┐                                    ┌──────────────┐
│   Admin UI   │                                    │   Backend    │
└──────┬───────┘                                    └──────┬───────┘
       │                                                   │
       │ GET /ws/connections                               │
       ├──────────────────────────────────────────────────>│
       │                                                   │
       │                                    Query          │
       │                                    WebSocketManager
       │                                    Get all stats  │
       │                                                   │
       │ {                                                 │
       │   "total_connections": 5,                         │
       │   "connections": [                                │
       │     {                                             │
       │       "user_id": "...",                           │
       │       "connected": true,                          │
       │       "uptime_seconds": 3600,                     │
       │       "last_heartbeat": "...",                    │
       │       "seconds_since_heartbeat": 15               │
       │     },                                            │
       │     ...                                           │
       │   ]                                               │
       │ }                                                 │
       │<──────────────────────────────────────────────────┤
       │                                                   │
       │ Display in dashboard                              │
       │                                                   │
```

## Legend

```
──────>  Request/Message sent
<──────  Response/Message received
╳╳╳╳╳╳  Failed connection/timeout
═══════  Persistent connection
```

## Key Points

1. **Authentication**: All connections require valid JWT token
2. **One per User**: Each user maintains one WebSocket connection
3. **Bidirectional Heartbeat**: Both client and server initiate pings
4. **Automatic Recovery**: Exponential backoff reconnection on failure
5. **Health Monitoring**: Real-time connection statistics via REST API
6. **Graceful Cleanup**: Automatic resource cleanup on disconnect
7. **Timeout Detection**: 60-second timeout for heartbeat response
8. **State Tracking**: Connection time, uptime, and heartbeat timestamps
