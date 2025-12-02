"""
WebSocket Frame Processor Module
Processes video frames received from WebRTC for anomaly detection
No disk I/O - pure frame processing pipeline
"""

import cv2
import numpy as np
import logging
import asyncio
from typing import Dict, List, Optional
from av import VideoFrame

from app.ai.detection.person_detector import PersonDetector
from app.ai.detection.tracker import PersonTracker
from app.ai.detection.frame_buffer import FrameBufferManager
from app.ai.detection.anomaly_detector import AnomalyDetector
from app.ai.model_manager import get_model_manager
from app.config import (
    YOLO_MODEL_PATH,
    POSE_MODEL_PATH,
    ANOMALY_MODEL_PATH,
    ANOMALY_THRESHOLD,
    DEVICE,
    SEQUENCE_LENGTH,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WebSocketAnomalyProcessor:
    """
    Process video frames received from WebRTC stream
    Runs anomaly detection pipeline without video file reading
    
    Pipeline:
    1. Receive frame from WebRTC
    2. Person Detection (YOLOv8)
    3. Tracking (Deep SORT)
    4. Pose Estimation (YOLOv8-Pose)
    5. Frame Buffering (24 frames with sliding window)
    6. Anomaly Detection (STG-NF)
    7. Return results when anomaly detected
    """

    def __init__(self, stream_id: str, user_id: str):
        """
        Initialize the processor for a specific stream
        Uses shared model instances from ModelManager for efficiency.
        
        Args:
            stream_id: Unique stream identifier
            user_id: User identifier owning this stream
        """
        self.stream_id = stream_id
        self.user_id = user_id
        self.frame_count = 0
        self.anomaly_count = 0
        
        logger.info(f"[Processor {user_id}/{stream_id}] Initializing anomaly detection pipeline...")
        
        # Get shared model instances from ModelManager
        model_manager = get_model_manager()
        
        logger.info(f"[Processor {user_id}/{stream_id}] Getting shared person detector...")
        self.detector: PersonDetector = model_manager.get_person_detector()
        
        logger.info(f"[Processor {user_id}/{stream_id}] Initializing tracker...")
        self.tracker: PersonTracker = PersonTracker()
        
        logger.info(f"[Processor {user_id}/{stream_id}] Getting shared pose estimator...")
        pose_config = model_manager.get_pose_model_config()
        self.frame_buffer: FrameBufferManager = FrameBufferManager(
            pose_model_path=pose_config['model_path'],
            sequence_length=pose_config['buffer_size'],
            device=pose_config['device']
        )
        
        logger.info(f"[Processor {user_id}/{stream_id}] Getting shared anomaly detector...")
        self.anomaly_detector: AnomalyDetector = model_manager.get_anomaly_detector()
        
        logger.info(f"[Processor {user_id}/{stream_id}] ✓ Pipeline initialized successfully (using shared models)")
    
    async def process_frame(self, av_frame: VideoFrame) -> Optional[List[Dict]]:
        """
        Process a single video frame from WebRTC
        
        Args:
            av_frame: av.VideoFrame from WebRTC track
            
        Returns:
            List of anomaly detection results (only abnormal detections)
            None if no anomalies detected
        """
        try:
            # Convert av.VideoFrame to numpy array (OpenCV format)
            frame = av_frame.to_ndarray(format="bgr24")
            self.frame_count += 1
            
            # Step 1: Person detection
            detections = self.detector.detect(frame)
            
            if not detections or len(detections) == 0:
                # No persons detected in frame
                return None
            
            # Step 2: Tracking
            tracking_data = self.tracker.update(detections, frame)
            
            if not tracking_data:
                # No tracked persons
                return None
            
            # Step 3: Pose extraction and buffering
            pose_dict, multiple = self.frame_buffer.update(frame, tracking_data)
            
            if len(pose_dict) == 0:
                # Buffer not ready yet
                return None
            
            # Step 4: Anomaly detection (when buffer full)
            results = self.anomaly_detector.predict(
                pose_dict,
                scene_id="live",
                clip_id=self.stream_id
            )
            
            if not results:
                return None
            
            # Step 5: Filter only abnormal detections
            abnormal_results = []
            for result in results:
                if result['is_abnormal']:
                    self.anomaly_count += 1
                    
                    # Add frame number, stream_id, and user_id
                    result['frame_number'] = self.frame_count
                    result['stream_id'] = self.stream_id
                    result['user_id'] = self.user_id
                    
                    # Store pose_dict for reinforcement learning
                    # This will be used to retrain the model based on user feedback
                    result['pose_dict'] = pose_dict
                    
                    # Get bounding box from tracking data
                    person_id = result['person_id']
                    if person_id in tracking_data:
                        bbox = tracking_data[person_id]
                        result['bbox'] = {
                            'x': int(bbox[0]),
                            'y': int(bbox[1]),
                            'w': int(bbox[2]),
                            'h': int(bbox[3])
                        }
                    
                    abnormal_results.append(result)
                    
                    # Log anomaly with emoji
                    logger.info(
                        f"🚨 [Processor {self.user_id}/{self.stream_id}] ANOMALY DETECTED! "
                        f"Person {person_id} | Score: {result['score']:.3f} | "
                        f"Confidence: {result['confidence']}"
                    )
            
            # Return only if we have abnormal detections
            if abnormal_results:
                return abnormal_results
            
            return None
            
        except Exception as e:
            logger.error(f"[Processor {self.user_id}/{self.stream_id}] Error processing frame: {e}", exc_info=True)
            return None
    
    def annotate_frame(self, frame: np.ndarray, results: List[Dict]) -> np.ndarray:
        """
        Draw bounding boxes and labels for anomalies on frame
        
        Args:
            frame: Original frame (numpy array)
            results: List of anomaly detection results
            
        Returns:
            Annotated frame
        """
        frame_copy = frame.copy()
        
        for result in results:
            if not result.get('is_abnormal'):
                continue
            
            # Get bounding box
            bbox = result.get('bbox')
            if not bbox:
                continue
            
            x1 = bbox['x']
            y1 = bbox['y']
            w = bbox['w']
            h = bbox['h']
            x2 = x1 + w
            y2 = y1 + h
            
            # Red color for anomaly
            color = (0, 0, 255)
            
            # Draw bounding box
            cv2.rectangle(frame_copy, (x1, y1), (x2, y2), color, 3)
            
            # Prepare labels
            person_id = result['person_id']
            score = result['score']
            confidence = result['confidence']
            
            labels = [
                f"⚠️ ANOMALY",
                f"ID: {person_id}",
                f"Score: {score:.2f}",
                f"Conf: {confidence}"
            ]
            
            # Draw text background and text
            y_offset = y1 - 10
            for i, text in enumerate(labels):
                text_y = y_offset - (len(labels) - i) * 25
                
                if text_y < 25:  # Too close to top edge
                    text_y = y1 + h + 25 + i * 25  # Draw below bbox instead
                
                # Background rectangle
                (text_w, text_h), _ = cv2.getTextSize(
                    text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2
                )
                cv2.rectangle(
                    frame_copy,
                    (x1, text_y - text_h - 5),
                    (x1 + text_w + 10, text_y + 5),
                    color,
                    -1
                )
                
                # Text
                cv2.putText(
                    frame_copy,
                    text,
                    (x1 + 5, text_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    2
                )
        
        return frame_copy
    
    def get_stats(self) -> Dict:
        """
        Get processing statistics
        
        Returns:
            Dictionary with statistics
        """
        return {
            'user_id': self.user_id,
            'stream_id': self.stream_id,
            'frames_processed': self.frame_count,
            'anomalies_detected': self.anomaly_count,
            'anomaly_rate': (self.anomaly_count / self.frame_count * 100) if self.frame_count > 0 else 0
        }
    
    def cleanup(self):
        """
        Clean up resources
        """
        logger.info(f"[Processor {self.user_id}/{self.stream_id}] Cleaning up processor...")
        
        # Log final statistics
        stats = self.get_stats()
        logger.info(
            f"[Processor {self.user_id}/{self.stream_id}] Final stats: "
            f"{stats['frames_processed']} frames, "
            f"{stats['anomalies_detected']} anomalies "
            f"({stats['anomaly_rate']:.2f}%)"
        )
        
        # Clear references - type: ignore to allow setting to None for cleanup
        del self.detector
        del self.tracker
        del self.frame_buffer
        del self.anomaly_detector
        
        logger.info(f"[Processor {self.user_id}/{self.stream_id}] ✓ Cleanup complete")
