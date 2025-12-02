"""
STG-NF Video Stream Module
Advanced video frame streamer with STG-NF anomaly detection pipeline
Integrates: Detection → Tracking → Pose → Anomaly Detection → WebRTC Streaming
"""

import cv2
import numpy as np
from aiortc import VideoStreamTrack
from aiortc.mediastreams import MediaStreamError
from av import VideoFrame
from fractions import Fraction

from detection.person_detector import PersonDetector
from detection.tracker import PersonTracker
from detection.frame_buffer import FrameBufferManager
from detection.anomaly_detector import AnomalyDetector
from config import (
    YOLO_MODEL_PATH,
    POSE_MODEL_PATH,
    ANOMALY_MODEL_PATH,
    ANOMALY_THRESHOLD,
    DEVICE,
    SEQUENCE_LENGTH,
    ANOMALY_LOG_PATH
)


class VideoFrameStreamSTGNF(VideoStreamTrack):
    """
    Advanced video stream with STG-NF pose-based anomaly detection
    
    Pipeline:
    1. Person Detection (YOLOv8)
    2. Tracking (Deep SORT)
    3. Pose Estimation (YOLOv8-Pose)
    4. Frame Buffering (30 frames)
    5. Anomaly Detection (STG-NF)
    6. Visual Annotation
    7. WebRTC Streaming
    """

    kind = "video"

    def __init__(self, video_url: str):
        """
        Initialize the STG-NF video stream
        
        Args:
            video_url (str): URL or path to the video file
        """
        super().__init__()
        self.video_url = video_url
        self.cap: cv2.VideoCapture | None = None
        self._timestamp = 0
        
        print(f"[STG-NF Stream] Initializing pipeline for: {video_url}")
        
        # Initialize all pipeline components
        print("[STG-NF Stream] Loading person detector...")
        self.detector = PersonDetector(YOLO_MODEL_PATH, device=DEVICE)
        
        print("[STG-NF Stream] Loading tracker...")
        self.tracker = PersonTracker()
        
        print("[STG-NF Stream] Loading pose estimator...")
        self.frame_buffer = FrameBufferManager(
            pose_model_path=POSE_MODEL_PATH,
            sequence_length=SEQUENCE_LENGTH,
            device=DEVICE
        )
        
        print("[STG-NF Stream] Loading anomaly detector...")
        self.anomaly_detector = AnomalyDetector(
            checkpoint_path=ANOMALY_MODEL_PATH,
            threshold=ANOMALY_THRESHOLD,
            device=DEVICE
        )
        
        # Logging
        self.anomaly_log = open(ANOMALY_LOG_PATH, "a")
        print(f"[STG-NF Stream] ✓ Pipeline initialized successfully")

    def open(self) -> bool:
        """
        Open the video stream
        
        Returns:
            bool: True if opened successfully, False otherwise
        """
        self.cap = cv2.VideoCapture(self.video_url)
        is_opened = self.cap.isOpened()
        if is_opened:
            print(f"[STG-NF Stream] ✓ Video opened: {self.video_url}")
        else:
            print(f"[STG-NF Stream] ✗ Failed to open video: {self.video_url}")
        return is_opened

    async def recv(self) -> VideoFrame:
        """
        Receive the next video frame (required by MediaStreamTrack)
        
        Returns:
            VideoFrame: The next frame as av.VideoFrame for WebRTC streaming
        """
        # Get frame from OpenCV
        if self.cap is None or not self.cap.isOpened():
            self.open()

        if self.cap is None:
            raise Exception("Failed to open video capture")

        ret, frame = self.cap.read()
        if not ret or frame is None:
            # Video ended - stop the track and close connection gracefully
            print("[STG-NF Stream] Video ended, closing stream")
            self.stop()
            raise MediaStreamError

        # Step 1: Person detection
        detections = self.detector.detect(frame)
        
        if detections and len(detections) > 0:
            # Step 2: Tracking
            tracking_data = self.tracker.update(detections, frame)
            
            # Step 3: Pose extraction and buffering
            pose_dict, multiple = self.frame_buffer.update(frame, tracking_data)
            
            # Step 4: Anomaly detection (when buffer full)
            results = []
            if len(pose_dict) > 0:
                results = self.anomaly_detector.predict(
                    pose_dict,
                    scene_id="live",
                    clip_id="stream"
                )
                
                # Print detection results with emojis
                if results:
                    print("\n" + "="*60)
                    for result in results:
                        person_id = result['person_id']
                        score = result['score']
                        is_abnormal = result['is_abnormal']
                        classification = result['classification']
                        confidence = result['confidence']
                        
                        if is_abnormal:
                            emoji = "🚨"
                            color_code = "\033[91m"  # Red
                        else:
                            emoji = "✅"
                            color_code = "\033[92m"  # Green
                        
                        reset_code = "\033[0m"
                        
                        print(f"{emoji} {color_code}Person {person_id}: {classification}{reset_code}")
                        print(f"   Score: {score:.3f} | Confidence: {confidence}")
                    print("="*60 + "\n")
            
            # Step 5: Annotate frame
            frame = self._annotate_frame(frame, tracking_data, results)
            
            # Step 6: Log anomalies
            for result in results:
                if result['is_abnormal']:
                    self.anomaly_log.write(
                        f"[{self._timestamp}] Person {result['person_id']}: "
                        f"ANOMALY detected (score={result['score']:.3f}, "
                        f"confidence={result['confidence']})\n"
                    )
                    self.anomaly_log.flush()
        
        # Ensure frame is uint8 numpy array
        frame_uint8 = np.asarray(frame, dtype=np.uint8)

        # Convert OpenCV frame (BGR numpy array) to av.VideoFrame
        video_frame = VideoFrame.from_ndarray(frame_uint8, format="bgr24")

        # Set timestamp
        video_frame.pts = self._timestamp
        video_frame.time_base = Fraction(1, 90000)

        self._timestamp += 3000  # Increment for ~30fps (90000/30 = 3000)

        return video_frame

    def _annotate_frame(self, frame, tracking_data, results):
        """
        Draw bounding boxes and labels on frame
        
        Args:
            frame: Original frame
            tracking_data: Dict of {person_id: (x, y, w, h)}
            results: List of anomaly detection results
            
        Returns:
            Annotated frame
        """
        frame_copy = frame.copy()
        
        # Create result lookup by person_id
        result_map = {r['person_id']: r for r in results}
        
        for person_id, bbox in tracking_data.items():
            x1, y1, w, h = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
            x2, y2 = x1 + w, y1 + h
            
            # Get anomaly result if available
            result = result_map.get(int(person_id))
            
            if result:
                # Have anomaly detection result
                is_abnormal = result['is_abnormal']
                score = result['score']
                confidence = result['confidence']
                
                # Color: Red for anomaly, Green for normal
                color = (0, 0, 255) if is_abnormal else (0, 255, 0)
                
                # Draw bounding box
                cv2.rectangle(frame_copy, (x1, y1), (x2, y2), color, 3)
                
                # Prepare labels
                labels = [
                    f"ID:{person_id}",
                    f"{'ANOMALY' if is_abnormal else 'NORMAL'}",
                    f"Score:{score:.2f}",
                    f"Conf:{confidence}"
                ]
                
                # Draw text background and text
                y_offset = y1 - 10
                for i, text in enumerate(labels):
                    text_y = y_offset - (len(labels) - i) * 25
                    
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
            else:
                # Buffering - no result yet
                color = (255, 255, 0)  # Yellow
                cv2.rectangle(frame_copy, (x1, y1), (x2, y2), color, 2)
                cv2.putText(
                    frame_copy,
                    f"ID:{person_id} Buffering...",
                    (x1, y1-10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    2
                )
        
        return frame_copy

    def close(self):
        """
        Close the video stream and release resources
        """
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        if self.anomaly_log is not None:
            self.anomaly_log.close()
        print("[STG-NF Stream] Stream closed and resources released")
