# Reinforcement Learning Training Data Storage

## Overview
Implementation of pose_dict storage system for reinforcement learning with user feedback. This allows the anomaly detection model to be retrained based on user corrections.

## What Was Implemented

### 1. Database Model (`app/models/training_data.py`)
Created `AnomalyTrainingData` model to store:
- **pose_dict**: The actual input data (skeleton keypoints) used for anomaly detection
- **Prediction data**: Original model predictions (score, confidence, label)
- **User feedback**: User corrections (true_positive, false_positive, uncertain)
- **Training metadata**: Tracking which data has been used for retraining

### 2. Database Migration
- Created Alembic migration: `0ec46c6454fb_add_anomaly_training_data_table.py`
- Applied migration to create `anomaly_training_data` table
- Includes proper indexes for efficient querying

### 3. Service Layer (`app/services/anomaly_service.py`)
Added three new methods to `AnomalyService`:

#### `save_training_data()`
Stores pose_dict and prediction data when an anomaly is detected.

#### `update_training_data_feedback()`
Updates a training record with user feedback for reinforcement learning.

#### `get_training_data_for_retraining()`
Retrieves training data filtered by feedback status for model retraining.

### 4. WebSocket Processor (`app/ai/processors/websocket_processor.py`)
Modified `process_frame()` to:
- Store pose_dict in the result dictionary (line 124)
- Pass pose_dict alongside anomaly detection results

### 5. Signaling Handler (`app/api/signaling.py`)
Updated anomaly saving logic to:
- Extract pose_dict from detection results
- Save training data immediately after anomaly creation
- Log successful training data storage

### 6. API Schemas (`app/schemas/training_data.py`)
Created Pydantic schemas for:
- `TrainingDataCreate`: Creating new training records
- `TrainingDataFeedback`: User feedback submission
- `TrainingDataResponse`: API responses
- `TrainingDataStats`: Statistics for training data

### 7. API Endpoints (`app/api/training_data.py`)
Created REST API endpoints:

#### `GET /api/training-data`
Retrieve training data with filtering options:
- Filter by user_feedback
- Filter by used_for_training status
- Pagination support

#### `PUT /api/training-data/{id}/feedback`
Submit user feedback on anomaly detection:
- true_positive: Correctly detected
- false_positive: Incorrectly flagged
- uncertain: User unsure

#### `GET /api/training-data/stats`
Get statistics about training data:
- Total samples
- Feedback counts
- Available for training

## Data Flow

```
1. Frame Processing (websocket_processor.py)
   ↓
   pose_dict extracted from frame_buffer
   ↓
2. Anomaly Detection
   ↓
   pose_dict included in results
   ↓
3. Anomaly Saved (signaling.py)
   ↓
   AnomalyService.create_anomaly()
   ↓
   AnomalyService.save_training_data()
   ↓
4. Training Data Stored in DB
   ↓
5. User Reviews & Provides Feedback
   ↓
   PUT /api/training-data/{id}/feedback
   ↓
6. Model Retraining (Future Implementation)
   ↓
   Fetch labeled data with get_training_data_for_retraining()
```

## Database Schema

### anomaly_training_data Table
```sql
- id: UUID (Primary Key)
- anomaly_id: UUID (Foreign Key → anomalies.id)
- pose_dict: JSONB (The input keypoints)
- stream_id: String
- frame_number: Float
- predicted_score: Float
- predicted_confidence: String
- predicted_label: String (Optional)
- user_feedback: String (Optional: true_positive, false_positive, uncertain)
- user_label: String (Optional)
- user_notes: Text (Optional)
- labeled_by: UUID (Foreign Key → users.id)
- labeled_at: DateTime
- used_for_training: Boolean
- training_batch_id: String
- extra_metadata: JSONB
- created_at: DateTime
- updated_at: DateTime
```

## pose_dict Structure
The stored pose_dict contains skeleton keypoints in this format:
```json
{
  "person_id_1": [
    [frame_1_keypoints_17x3],  // 17 keypoints, 3 values each (x, y, confidence)
    [frame_2_keypoints_17x3],
    ...
    [frame_24_keypoints_17x3]  // 24 frames total
  ],
  "person_id_2": [...],
  ...
}
```

## Usage Example

### Backend: Automatic Storage
When an anomaly is detected, the system automatically:
1. Stores the anomaly record
2. Stores the pose_dict training data
3. Links them together via `anomaly_id`

### Frontend: User Feedback
```javascript
// User reviews anomaly and provides feedback
await fetch(`/api/training-data/${trainingDataId}/feedback`, {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    user_feedback: 'false_positive',  // or 'true_positive', 'uncertain'
    user_label: 'normal_walking',      // Optional: corrected label
    user_notes: 'Person was just walking normally'  // Optional notes
  })
});
```

### Model Retraining Script
```python
from app.db import SessionLocal
from app.services.anomaly_service import AnomalyService

db = SessionLocal()

# Get all labeled data not yet used for training
training_samples = AnomalyService.get_training_data_for_retraining(
    db=db,
    user_feedback='true_positive',  # or None for all feedback
    used_for_training=False,
    limit=1000
)

# Extract pose_dict and labels for training
for sample in training_samples:
    pose_dict = sample.pose_dict
    user_feedback = sample.user_feedback
    user_label = sample.user_label
    
    # Use for model retraining
    # ... your training code here ...
    
    # Mark as used
    sample.used_for_training = True
    sample.training_batch_id = 'batch_20251203_001'

db.commit()
```

## Next Steps

### To Enable Reinforcement Learning:
1. **Register API Endpoints**: Add `training_data` router to main app
2. **Frontend UI**: Create interface for users to review and label anomalies
3. **Training Pipeline**: Implement model retraining script using stored data
4. **Active Learning**: Prioritize uncertain predictions for user review
5. **Model Versioning**: Track which model version made each prediction

### To Register the API Endpoints:
Add to `main.py`:
```python
from app.api.training_data import router as training_data_router
app.include_router(training_data_router)
```

## Benefits
1. **Continuous Improvement**: Model improves based on real-world feedback
2. **Error Correction**: False positives can be used to reduce future errors
3. **Domain Adaptation**: Model adapts to specific deployment environments
4. **Audit Trail**: Complete history of predictions and user corrections
5. **Data Efficiency**: Only stores relevant data (pose keypoints, not full frames)

## Storage Considerations
- pose_dict is stored as JSONB (compressed JSON in PostgreSQL)
- Each record is relatively small (~5-10 KB depending on number of persons)
- Efficient querying with indexes on feedback status and timestamps
- Can periodically archive old training data after model updates
