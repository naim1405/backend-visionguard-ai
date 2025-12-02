# Anomaly Detection and Storage Implementation

## Overview
This implementation adds comprehensive anomaly detection storage to the VisionGuard AI backend. When anomalies are detected, they are automatically saved to the database with associated frame images stored on disk.

## Database Schema

### Anomalies Table
Located at: `app/models/anomaly.py`

**Columns:**
- `id` - UUID primary key
- `shop_id` - Foreign key to shops table
- `timestamp` - When the anomaly occurred
- `location` - Location/camera identifier (e.g., "Entrance", "Camera 1")
- `severity` - Enum: LOW, MEDIUM, HIGH, CRITICAL
- `status` - Enum: PENDING, ACKNOWLEDGED, RESOLVED, FALSE_POSITIVE
- `description` - Text description of the anomaly
- `image_url` - Relative path to saved frame image

**Additional Fields:**
- `anomaly_type` - Category (e.g., "suspicious_behavior", "fall_detection")
- `confidence_score` - AI model confidence (0.0 - 1.0)
- `resolved_by` - User ID who resolved it
- `resolved_at` - Resolution timestamp
- `notes` - Additional comments
- `extra_data` - JSONB for flexible metadata (AI outputs, bounding boxes, etc.)
- `created_at` / `updated_at` - Audit timestamps

**Indexes:**
- Individual: id, shop_id, timestamp, severity, status, anomaly_type
- Composite: (shop_id, timestamp), (shop_id, status), (severity, status)

## File Storage

### Frame Storage Location
- **Base Directory:** `backend-visionguard-ai/anomaly_frames/`
- **Structure:** `anomaly_frames/{shop_id}/{timestamp}_{uuid}.jpg`
- **Format:** JPEG with 90% quality
- **Organization:** Automatically organized by shop for easy management

**Example:**
```
anomaly_frames/
├── 123e4567-e89b-12d3-a456-426614174000/
│   ├── 20251203_141532_a1b2c3d4.jpg
│   ├── 20251203_141545_e5f6g7h8.jpg
│   └── ...
└── 987f6543-e21c-34b5-a678-123456789abc/
    ├── 20251203_142015_i9j0k1l2.jpg
    └── ...
```

## API Endpoints

### 1. Get Anomalies
**Endpoint:** `GET /api/anomalies`

**Query Parameters:**
- `shop_id` (optional) - Filter by shop
- `status` (optional) - Filter by status (pending, acknowledged, resolved, false_positive)
- `severity` (optional) - Filter by severity (low, medium, high, critical)
- `limit` (optional, default: 100) - Maximum results
- `offset` (optional, default: 0) - Pagination offset

**Response:**
```json
{
  "total": 42,
  "anomalies": [
    {
      "id": "uuid",
      "shop_id": "uuid",
      "timestamp": "2025-12-03T14:15:32Z",
      "location": "Entrance",
      "severity": "high",
      "status": "pending",
      "description": "Anomalous behavior detected (Person ID: 5, Confidence: High)",
      "image_url": "/api/anomalies/frames/shop-id/filename.jpg",
      "anomaly_type": "suspicious_behavior",
      "confidence_score": 0.87,
      "extra_data": {
        "person_id": 5,
        "bbox": {"x": 100, "y": 200, "w": 150, "h": 300},
        "frame_number": 1234
      },
      "created_at": "2025-12-03T14:15:32Z"
    }
  ]
}
```

### 2. Get Single Anomaly
**Endpoint:** `GET /api/anomalies/{anomaly_id}`

**Response:** Single anomaly object (same structure as above)

### 3. Update Anomaly Status
**Endpoint:** `PATCH /api/anomalies/{anomaly_id}`

**Request Body:**
```json
{
  "status": "resolved",
  "notes": "False alarm - authorized personnel"
}
```

**Response:** Updated anomaly object

### 4. Get Anomaly Frame Image
**Endpoint:** `GET /api/anomalies/frames/{shop_id}/{filename}`

**Response:** JPEG image file with proper caching headers

### 5. Get Anomaly Statistics
**Endpoint:** `GET /api/anomalies/stats/summary`

**Query Parameters:**
- `shop_id` (optional) - Filter by shop

**Response:**
```json
{
  "total": 42,
  "recent_24h": 8,
  "by_status": {
    "pending": 12,
    "acknowledged": 15,
    "resolved": 13,
    "false_positive": 2
  },
  "by_severity": {
    "low": 10,
    "medium": 18,
    "high": 12,
    "critical": 2
  }
}
```

## Service Layer

### AnomalyService
Located at: `app/services/anomaly_service.py`

**Key Methods:**

1. **`save_frame(frame, shop_id, timestamp)`**
   - Saves OpenCV frame to disk
   - Returns relative path for database storage
   - Organizes by shop_id

2. **`determine_severity(confidence, score)`**
   - Maps confidence levels to severity enum
   - High confidence → HIGH severity
   - Medium confidence → MEDIUM severity
   - Low confidence → LOW severity

3. **`create_anomaly(db, shop_id, location, description, frame, detection_result, anomaly_type)`**
   - Main method for creating anomaly records
   - Saves frame to disk
   - Creates database entry
   - Returns Anomaly object

4. **`get_anomalies(db, shop_id, status, severity, limit, offset)`**
   - Retrieves anomalies with filters
   - Supports pagination

5. **`update_anomaly_status(db, anomaly_id, status, resolved_by, notes)`**
   - Updates status and resolution info
   - Automatically sets resolved_at timestamp

## Integration with Detection Pipeline

### Flow
1. WebRTC stream receives video frames from frontend
2. Frame processor detects anomalies using AI models
3. When anomaly detected:
   - Send real-time alert via WebSocket
   - **Save to database** (NEW)
   - **Store frame image** (NEW)

### Modified Files

#### `app/api/signaling.py`
Added database storage in `process_video_track()`:
- Extracts shop_id from stream
- Creates database session
- Calls `AnomalyService.create_anomaly()`
- Saves annotated frame with bounding boxes
- Stores metadata in extra_data field

```python
# Save anomaly to database
db = SessionLocal()
anomaly = AnomalyService.create_anomaly(
    db=db,
    shop_id=UUID(shop_id),
    location=location,
    description=description,
    frame=annotated_frame,
    detection_result=result,
    anomaly_type="suspicious_behavior"
)
```

## Frontend Integration

### Fetching Anomalies
```typescript
// Get recent anomalies for a shop
const response = await axios.get('/api/anomalies', {
  params: {
    shop_id: shopId,
    status: 'pending',
    limit: 20
  },
  headers: {
    Authorization: `Bearer ${token}`
  }
});

const anomalies = response.data.anomalies;
```

### Displaying Frame Images
```typescript
// Image URL is already provided in the response
<img 
  src={anomaly.image_url} 
  alt="Anomaly frame"
  // URL format: /api/anomalies/frames/{shop_id}/{filename}
/>
```

### Updating Status
```typescript
await axios.patch(`/api/anomalies/${anomalyId}`, {
  status: 'resolved',
  notes: 'Verified and resolved'
}, {
  headers: {
    Authorization: `Bearer ${token}`
  }
});
```

## Security & Permissions

### Authentication
- All endpoints require JWT authentication
- Token must be provided in Authorization header

### Authorization
- Users can only access anomalies from shops they own/manage
- OWNER: Full access to their shops' anomalies
- MANAGER: Access to assigned shops' anomalies
- ADMIN: Full access to all anomalies

### File Access
- Frame images are served through authenticated API endpoint
- Direct file system access is prevented
- Shop access is verified before serving images

## Performance Considerations

### Database Indexes
Optimized for common query patterns:
- `(shop_id, timestamp)` - Recent anomalies for a shop
- `(shop_id, status)` - Pending anomalies for a shop
- `(severity, status)` - High severity pending anomalies

### File Storage
- JPEG compression (90% quality) balances quality and storage
- Organized by shop_id for efficient cleanup
- Can be easily migrated to cloud storage (S3, GCS) later

### Caching
- Image responses include Cache-Control headers
- 24-hour cache for frame images

## Migration to Cloud Storage

The current implementation stores frames locally but is designed for easy cloud migration:

```python
# Future cloud storage implementation
def save_frame_to_cloud(frame, shop_id, timestamp):
    # Upload to S3/GCS/Azure Blob
    blob_url = cloud_storage.upload(frame, f"{shop_id}/{timestamp}.jpg")
    return blob_url

# Update in AnomalyService.save_frame()
# Just change the storage backend, API remains the same
```

## Monitoring & Maintenance

### Disk Space Management
```bash
# Check anomaly frames disk usage
du -sh anomaly_frames/

# Clean up old frames (example: older than 90 days)
find anomaly_frames/ -type f -mtime +90 -delete
```

### Database Maintenance
```sql
-- Archive old resolved anomalies
-- Move to archive table after 6 months
```

## Testing

### Manual Testing
```bash
# 1. Start the backend
python main.py

# 2. Test anomaly endpoints
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/anomalies

# 3. View frame image
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/anomalies/frames/{shop_id}/{filename} \
  -o test_frame.jpg
```

## Future Enhancements

1. **Notification Integration**
   - Send push notifications for high severity anomalies
   - Email alerts for critical anomalies

2. **Analytics Dashboard**
   - Anomaly trends over time
   - Heatmap of anomaly locations
   - Pattern detection

3. **Video Clips**
   - Store 5-second video clips instead of single frames
   - Show before/after context

4. **Machine Learning Feedback**
   - Use resolved/false_positive status to retrain models
   - Improve detection accuracy over time

5. **Cloud Storage**
   - Migrate to S3/GCS for scalability
   - CDN for faster image delivery

## Summary

This implementation provides:
✅ Persistent storage of all detected anomalies
✅ Frame images saved with bounding boxes
✅ Comprehensive API for querying and management
✅ Proper authentication and authorization
✅ Efficient database indexing
✅ Easy frontend integration
✅ Prepared for cloud storage migration
