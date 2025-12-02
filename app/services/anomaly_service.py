"""
Anomaly Service
Handles saving anomaly detections to database and storing frames
"""

import os
import uuid
import cv2
import numpy as np
import logging
from datetime import datetime
from typing import Dict, Optional
from sqlalchemy.orm import Session

from app.models.anomaly import Anomaly, AnomalyStatus, AnomalySeverity
from app.config import BASE_DIR

# Configure logging
logger = logging.getLogger(__name__)

# Directory for storing anomaly frames
ANOMALY_FRAMES_DIR = os.path.join(BASE_DIR, "anomaly_frames")

# Create directory if it doesn't exist
os.makedirs(ANOMALY_FRAMES_DIR, exist_ok=True)
logger.info(f"Anomaly frames directory: {ANOMALY_FRAMES_DIR}")


class AnomalyService:
    """Service for managing anomaly records"""
    
    @staticmethod
    def save_frame(frame: np.ndarray, shop_id: str, timestamp: datetime) -> str:
        """
        Save frame to disk and return the file path
        
        Args:
            frame: OpenCV frame (numpy array)
            shop_id: Shop ID for organizing files
            timestamp: Timestamp of detection
            
        Returns:
            Relative path to saved frame (for storing in database)
        """
        try:
            # Create shop-specific directory
            shop_dir = os.path.join(ANOMALY_FRAMES_DIR, str(shop_id))
            os.makedirs(shop_dir, exist_ok=True)
            
            # Generate unique filename with timestamp
            filename = f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.jpg"
            filepath = os.path.join(shop_dir, filename)
            
            # Save frame as JPEG
            cv2.imwrite(filepath, frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            
            # Return relative path from anomaly_frames directory
            relative_path = os.path.join(str(shop_id), filename)
            
            logger.info(f"Saved anomaly frame: {relative_path}")
            return relative_path
            
        except Exception as e:
            logger.error(f"Error saving anomaly frame: {e}", exc_info=True)
            return None
    
    @staticmethod
    def determine_severity(confidence: str, score: float) -> AnomalySeverity:
        """
        Determine severity based on confidence and score
        
        Args:
            confidence: Confidence level ("High", "Medium", "Low")
            score: Anomaly score from model
            
        Returns:
            AnomalySeverity enum value
        """
        if confidence == "High":
            return AnomalySeverity.HIGH
        elif confidence == "Medium":
            return AnomalySeverity.MEDIUM
        else:
            return AnomalySeverity.LOW
    
    @staticmethod
    def create_anomaly(
        db: Session,
        shop_id: uuid.UUID,
        location: str,
        description: str,
        frame: np.ndarray,
        detection_result: Dict,
        anomaly_type: str = "suspicious_behavior"
    ) -> Optional[Anomaly]:
        """
        Create and save an anomaly record to database
        
        Args:
            db: Database session
            shop_id: Shop UUID
            location: Location/camera identifier
            description: Description of the anomaly
            frame: OpenCV frame (numpy array)
            detection_result: Detection result dictionary from anomaly detector
            anomaly_type: Type of anomaly
            
        Returns:
            Created Anomaly object or None if failed
        """
        try:
            timestamp = datetime.utcnow()
            
            # Save frame to disk
            image_path = AnomalyService.save_frame(frame, shop_id, timestamp)
            
            # Determine severity from confidence
            confidence = detection_result.get('confidence', 'Low')
            score = detection_result.get('score', 0.0)
            severity = AnomalyService.determine_severity(confidence, score)
            
            # Create anomaly record
            anomaly = Anomaly(
                shop_id=shop_id,
                timestamp=timestamp,
                location=location,
                severity=severity,
                status=AnomalyStatus.PENDING,
                description=description,
                image_url=image_path,
                anomaly_type=anomaly_type,
                confidence_score=abs(float(score)),
                extra_data={
                    'person_id': detection_result.get('person_id'),
                    'start_frame': detection_result.get('start_frame'),
                    'end_frame': detection_result.get('end_frame'),
                    'frame_number': detection_result.get('frame_number'),
                    'bbox': detection_result.get('bbox'),
                    'classification': detection_result.get('classification'),
                    'stream_id': detection_result.get('stream_id'),
                }
            )
            
            db.add(anomaly)
            db.commit()
            db.refresh(anomaly)
            
            logger.info(
                f"Created anomaly record: {anomaly.id} "
                f"(shop={shop_id}, severity={severity.value}, "
                f"type={anomaly_type})"
            )
            
            return anomaly
            
        except Exception as e:
            logger.error(f"Error creating anomaly record: {e}", exc_info=True)
            db.rollback()
            return None
    
    @staticmethod
    def get_anomalies(
        db: Session,
        shop_id: Optional[uuid.UUID] = None,
        status: Optional[AnomalyStatus] = None,
        severity: Optional[AnomalySeverity] = None,
        limit: int = 100,
        offset: int = 0
    ) -> list[Anomaly]:
        """
        Get anomalies with optional filters
        
        Args:
            db: Database session
            shop_id: Filter by shop ID
            status: Filter by status
            severity: Filter by severity
            limit: Maximum number of results
            offset: Offset for pagination
            
        Returns:
            List of Anomaly objects
        """
        query = db.query(Anomaly)
        
        if shop_id:
            query = query.filter(Anomaly.shop_id == shop_id)
        if status:
            query = query.filter(Anomaly.status == status)
        if severity:
            query = query.filter(Anomaly.severity == severity)
        
        query = query.order_by(Anomaly.timestamp.desc())
        query = query.limit(limit).offset(offset)
        
        return query.all()
    
    @staticmethod
    def update_anomaly_status(
        db: Session,
        anomaly_id: uuid.UUID,
        status: AnomalyStatus,
        resolved_by: Optional[uuid.UUID] = None,
        notes: Optional[str] = None
    ) -> Optional[Anomaly]:
        """
        Update anomaly status
        
        Args:
            db: Database session
            anomaly_id: Anomaly UUID
            status: New status
            resolved_by: User ID who resolved it
            notes: Additional notes
            
        Returns:
            Updated Anomaly object or None if not found
        """
        try:
            anomaly = db.query(Anomaly).filter(Anomaly.id == anomaly_id).first()
            
            if not anomaly:
                logger.warning(f"Anomaly not found: {anomaly_id}")
                return None
            
            anomaly.status = status
            
            if status in [AnomalyStatus.RESOLVED, AnomalyStatus.FALSE_POSITIVE]:
                anomaly.resolved_at = datetime.utcnow()
                if resolved_by:
                    anomaly.resolved_by = resolved_by
            
            if notes:
                anomaly.notes = notes
            
            db.commit()
            db.refresh(anomaly)
            
            logger.info(f"Updated anomaly {anomaly_id} status to {status.value}")
            return anomaly
            
        except Exception as e:
            logger.error(f"Error updating anomaly status: {e}", exc_info=True)
            db.rollback()
            return None
    
    @staticmethod
    def get_frame_url(image_path: str) -> str:
        """
        Convert database image path to URL that frontend can use
        
        Args:
            image_path: Relative path from database
            
        Returns:
            URL path for serving the image
        """
        if not image_path:
            return None
        # Return URL that will be served by the API endpoint
        return f"/api/anomalies/frames/{image_path}"
