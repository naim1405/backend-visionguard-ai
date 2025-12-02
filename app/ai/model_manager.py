"""
Model Manager - Singleton for AI Models
Loads models once at startup and shares them across all streams
"""

import logging
from typing import Optional
from app.ai.detection.person_detector import PersonDetector
from app.ai.detection.anomaly_detector import AnomalyDetector
from app.config import (
    YOLO_MODEL_PATH,
    POSE_MODEL_PATH,
    ANOMALY_MODEL_PATH,
    ANOMALY_THRESHOLD,
    DEVICE,
    SEQUENCE_LENGTH,
)

logger = logging.getLogger(__name__)


class ModelManager:
    """
    Singleton class to manage AI models
    Loads models once at startup and shares them across all video streams
    """
    
    _instance: Optional['ModelManager'] = None
    _initialized: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # Only initialize once
        if ModelManager._initialized:
            return
        
        logger.info("=" * 70)
        logger.info("Initializing AI Model Manager (Singleton)")
        logger.info("=" * 70)
        
        self.person_detector: Optional[PersonDetector] = None
        self.anomaly_detector: Optional[AnomalyDetector] = None
        self.pose_model_path: str = POSE_MODEL_PATH
        self.device: str = DEVICE
        
        ModelManager._initialized = True
    
    def load_models(self):
        """
        Load all AI models at startup
        This should be called once during application startup
        """
        if self.person_detector is not None and self.anomaly_detector is not None:
            logger.info("✓ Models already loaded")
            return
        
        logger.info("Loading AI models...")
        
        # Load Person Detector (YOLOv8)
        logger.info(f"Loading person detector: {YOLO_MODEL_PATH}")
        self.person_detector = PersonDetector(YOLO_MODEL_PATH, device=DEVICE)
        logger.info("✓ Person detector loaded")
        
        # Load Anomaly Detector (STG-NF)
        logger.info(f"Loading anomaly detector: {ANOMALY_MODEL_PATH}")
        self.anomaly_detector = AnomalyDetector(
            checkpoint_path=ANOMALY_MODEL_PATH,
            threshold=ANOMALY_THRESHOLD,
            device=DEVICE
        )
        logger.info("✓ Anomaly detector loaded")
        
        # Note: Pose model is loaded per-stream by FrameBufferManager
        # as it maintains per-person buffers
        logger.info(f"Pose model path configured: {POSE_MODEL_PATH}")
        
        logger.info("=" * 70)
        logger.info("✓ All AI models loaded successfully")
        logger.info(f"Device: {DEVICE}")
        logger.info("=" * 70)
    
    def get_person_detector(self) -> PersonDetector:
        """Get the shared person detector instance"""
        if self.person_detector is None:
            raise RuntimeError("Models not loaded. Call load_models() first.")
        return self.person_detector
    
    def get_anomaly_detector(self) -> AnomalyDetector:
        """Get the shared anomaly detector instance"""
        if self.anomaly_detector is None:
            raise RuntimeError("Models not loaded. Call load_models() first.")
        return self.anomaly_detector
    
    def get_pose_model_config(self) -> dict:
        """Get pose model configuration for FrameBufferManager"""
        return {
            'model_path': self.pose_model_path,
            'buffer_size': SEQUENCE_LENGTH,
            'device': self.device
        }
    
    def cleanup(self):
        """Clean up models"""
        logger.info("Cleaning up AI models...")
        
        if self.person_detector:
            del self.person_detector
            self.person_detector = None
        
        if self.anomaly_detector:
            del self.anomaly_detector
            self.anomaly_detector = None
        
        logger.info("✓ AI models cleaned up")


# Global function to get the singleton instance
def get_model_manager() -> ModelManager:
    """Get the global ModelManager instance"""
    return ModelManager()
