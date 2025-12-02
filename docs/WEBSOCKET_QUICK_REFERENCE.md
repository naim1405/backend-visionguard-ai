# WebSocket Persistent Connection - Quick Reference

## Connection Details

**URL**: `ws://localhost:8000/ws/alerts/{user_id}?token={JWT_TOKEN}`

**Authentication**: JWT token required as query parameter

## Features

✅ **Automatic Reconnection** - Exponential backoff (1s → 30s)  
✅ **Heartbeat Monitoring** - Ping/pong every 30 seconds  
✅ **Connection Health Tracking** - Real-time uptime and heartbeat stats  
✅ **Stale Connection Cleanup** - Auto-cleanup after 60s of no heartbeat  
✅ **One Connection Per User** - All streams share single WebSocket  

## Quick Commands

### Check Connection Status
```bash
# All connections
curl http://localhost:8000/ws/connections

# Specific user
curl http://localhost:8000/ws/connections/{user_id}
```

### Test WebSocket Connection
```bash
cd /home/ezio/Documents/work/backend-visionguard-ai
python test_websocket_connection.py
```

### Test with wscat
```bash
# Install wscat
npm install -g wscat

# Connect
wscat -c "ws://localhost:8000/ws/alerts/{user_id}?token={token}"

# Send ping
> {"type":"ping"}

# Expect pong
< {"type":"pong"}
```

## Message Types

| Type | Direction | Description |
|------|-----------|-------------|
| `ping` | ↔️ | Heartbeat check |
| `pong` | ↔️ | Heartbeat response |
| `anomaly_detected` | ← | Alert from backend |
| `ack` | → | Acknowledge alert |

## Configuration

### Backend (`app/api/websocket.py`)
```python
PING_INTERVAL = 30      # seconds
HEARTBEAT_TIMEOUT = 60  # seconds
```

### Frontend (`hooks/useAnomalyAlerts.ts`)
```typescript
INITIAL_RECONNECT_DELAY = 1000     // 1 second
MAX_RECONNECT_DELAY = 30000        // 30 seconds
HEARTBEAT_INTERVAL = 30000         // 30 seconds
HEARTBEAT_TIMEOUT = 60000          // 60 seconds
```

### Environment Variables
```bash
# Frontend .env.local
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

## Monitoring Endpoints

### Get All Connections
```
GET /ws/connections
```

Response:
```json
{
  "total_connections": 3,
  "connections": [
    {
      "user_id": "...",
      "connected": true,
      "uptime_seconds": 3600,
      "seconds_since_heartbeat": 15
    }
  ]
}
```

### Get User Connection
```
GET /ws/connections/{user_id}
```

Response:
```json
{
  "user_id": "...",
  "connected": true,
  "connected_at": "2024-12-03T10:30:00",
  "uptime_seconds": 3600,
  "last_heartbeat": "2024-12-03T11:29:45",
  "seconds_since_heartbeat": 15
}
```

## Troubleshooting

### Connection Not Established
1. Check backend is running: `curl http://localhost:8000/health`
2. Verify JWT token is valid
3. Check user is authenticated
4. Review browser console for WebSocket errors

### Connection Keeps Dropping
1. Check network stability
2. Verify firewall allows WebSocket connections
3. Check backend logs for disconnection reasons
4. Monitor heartbeat intervals

### No Alerts Received
1. Verify WebSocket connection status
2. Check video stream is active
3. Ensure anomaly detection is running
4. Review backend logs for processing errors

## Code Examples

### Frontend Usage
```tsx
import { useAnomalyAlerts } from '@/hooks/useAnomalyAlerts'

function MyComponent() {
  const { alerts, connected, clearAlerts } = useAnomalyAlerts()
  
  return (
    <div>
      <p>Status: {connected ? '🟢 Connected' : '🔴 Disconnected'}</p>
      <p>Alerts: {alerts.length}</p>
    </div>
  )
}
```

### Backend Usage
```python
from app.api.websocket import get_websocket_manager

ws_manager = get_websocket_manager()

# Send alert
await ws_manager.send_anomaly_alert(
    user_id="user_123",
    stream_id="stream_456",
    detection_result=result,
    annotated_frame=frame
)

# Check connection
stats = ws_manager.get_connection_stats("user_123")
if stats:
    print(f"User uptime: {stats['uptime_seconds']}s")
```

## Documentation

- **Full Backend Docs**: `/docs/WEBSOCKET_PERSISTENT_CONNECTION.md`
- **Frontend Guide**: `/WEBSOCKET_CONNECTION.md`
- **Implementation Summary**: `/docs/IMPLEMENTATION_SUMMARY.md`
- **Test Script**: `/test_websocket_connection.py`

## Support

For issues or questions:
1. Check the comprehensive documentation files
2. Run the test script to verify functionality
3. Review browser console and backend logs
4. Check connection statistics endpoints

---

**Last Updated**: December 3, 2025  
**Version**: 1.0.0
