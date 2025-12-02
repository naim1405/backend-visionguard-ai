"""
Person Detection Module
Adapted from vis-new/p1.py
Uses YOLOv8 for person detection
"""

import cv2
import numpy as np
from ultralytics import YOLO


class PersonDetector:
    """
    YOLOv8-based person detector
    """
    
    def __init__(self, model_path: str, device: str = "cuda:0", conf_threshold: float = 0.45):
        """
        Initialize person detector
        
        Args:
            model_path: Path to YOLOv8 model file
            device: Device to run on ('cuda:0' or 'cpu')
            conf_threshold: Confidence threshold for detections
        """
        self.model = YOLO(model_path)
        self.model.to(device)
        self.conf_threshold = conf_threshold
        self.device = device
    
    def detect(self, frame: np.ndarray):
        """
        Detect persons in a frame
        
        Args:
            frame: BGR image (numpy array)
            
        Returns:
            List of detections: [[[x, y, w, h], confidence], ...]
            where (x, y) is top-left corner, (w, h) is width/height
        """
        results = self.model(frame)
        detections = []
        
        for box in results[0].boxes:
            x1, y1, x2, y2 = box.xyxy[0]
            conf = float(box.conf)
            cls = int(box.cls)
            
            # class 0 = person in COCO dataset
            if cls == 0 and conf > self.conf_threshold:
                detections.append([
                    [float(x1), float(y1), float(x2 - x1), float(y2 - y1)],
                    conf
                ])
        
        return detections
