"""
Person Tracking Module
Adapted from vis-new/p2.py
Uses Deep SORT for multi-person tracking
"""

from deep_sort_realtime.deepsort_tracker import DeepSort
import cv2


class PersonTracker:
    """
    Deep SORT tracker for maintaining person identities across frames
    """
    
    def __init__(
        self,
        max_age: int = 900,
        max_iou_distance: float = 0.9,
        max_cosine_distance: float = 0.7,
        embedder: str = "torchreid",
        embedder_model_name: str = "resnet50",
        half: bool = True
    ):
        """
        Initialize Deep SORT tracker
        
        Args:
            max_age: Maximum frames to keep track without detection
            max_iou_distance: Maximum IOU distance for matching
            max_cosine_distance: Maximum cosine distance for matching
            embedder: Embedding model type
            embedder_model_name: Name of embedding model
            half: Use half precision (FP16)
        """
        self.tracker = DeepSort(
            max_age=max_age,
            max_iou_distance=max_iou_distance,
            max_cosine_distance=max_cosine_distance,
            embedder=embedder,
            embedder_model_name=embedder_model_name,
            half=half
        )
    
    def update(self, detections, frame):
        """
        Update tracker with new detections
        
        Args:
            detections: List from PersonDetector [[[x,y,w,h], conf], ...]
            frame: Current frame (BGR numpy array)
            
        Returns:
            Dictionary mapping track_id to bounding box: {id: (x, y, w, h)}
        """
        dets = []
        
        for bbox, conf in detections:
            x, y, w, h = bbox
            dets.append(([int(x), int(y), int(w), int(h)], float(conf)))
        
        # Update tracker
        tracks = self.tracker.update_tracks(dets, frame=frame)
        
        track_map = {}
        
        for track in tracks:
            if not track.is_confirmed():
                continue
            
            track_id = track.track_id
            x1, y1, x2, y2 = track.to_ltrb()
            w = x2 - x1
            h = y2 - y1
            
            track_map[track_id] = (x1, y1, w, h)
        
        # Returns {id: (x, y, w, h)}
        # id => person id
        # (x, y, w, h) => bounding box coordinates
        return track_map
