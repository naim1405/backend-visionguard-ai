"""
Anomaly API Endpoints
Handles anomaly records retrieval and management
"""

import os
import logging
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from datetime import datetime

from app.db import get_db
from app.core.dependencies import get_current_user
from app.models import User, UserRole
from app.models.anomaly import Anomaly, AnomalyStatus, AnomalySeverity
from app.services.anomaly_service import AnomalyService
from app.config import BASE_DIR

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/anomalies", tags=["Anomalies"])


# ============================================================================
# Pydantic Schemas
# ============================================================================


class AnomalyResponse(BaseModel):
    """Anomaly response schema"""
    id: UUID
    shop_id: UUID
    timestamp: datetime
    location: str
    severity: str
    status: str
    description: str
    image_url: Optional[str]
    anomaly_type: Optional[str]
    confidence_score: Optional[float]
    resolved_by: Optional[UUID]
    resolved_at: Optional[datetime]
    notes: Optional[str]
    extra_data: Optional[dict]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
        
    @classmethod
    def from_orm(cls, anomaly: Anomaly):
        """Convert ORM model to response schema with proper URL"""
        data = {
            "id": anomaly.id,
            "shop_id": anomaly.shop_id,
            "timestamp": anomaly.timestamp,
            "location": anomaly.location,
            "severity": anomaly.severity.value,
            "status": anomaly.status.value,
            "description": anomaly.description,
            "image_url": AnomalyService.get_frame_url(anomaly.image_url) if anomaly.image_url else None,
            "anomaly_type": anomaly.anomaly_type,
            "confidence_score": anomaly.confidence_score,
            "resolved_by": anomaly.resolved_by,
            "resolved_at": anomaly.resolved_at,
            "notes": anomaly.notes,
            "extra_data": anomaly.extra_data,
            "created_at": anomaly.created_at,
            "updated_at": anomaly.updated_at,
        }
        return cls(**data)


class AnomalyUpdateRequest(BaseModel):
    """Request schema for updating anomaly"""
    status: str = Field(..., description="New status: pending, acknowledged, resolved, false_positive")
    notes: Optional[str] = Field(None, description="Additional notes about the resolution")


class AnomalyListResponse(BaseModel):
    """Response schema for list of anomalies"""
    total: int
    anomalies: List[AnomalyResponse]


# ============================================================================
# API Endpoints
# ============================================================================


@router.get(
    "",
    response_model=AnomalyListResponse,
    summary="Get Anomalies",
    description="Get list of anomalies with optional filters"
)
async def get_anomalies(
    shop_id: Optional[UUID] = Query(None, description="Filter by shop ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get anomalies with optional filters.
    
    - **shop_id**: Filter by specific shop (optional)
    - **status**: Filter by status (pending, acknowledged, resolved, false_positive)
    - **severity**: Filter by severity (low, medium, high, critical)
    - **limit**: Maximum number of results (default: 100)
    - **offset**: Pagination offset (default: 0)
    
    Returns list of anomalies that the user has access to.
    """
    try:
        # Convert string enums to enum types
        status_enum = None
        if status:
            try:
                status_enum = AnomalyStatus(status.lower())
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
        
        severity_enum = None
        if severity:
            try:
                severity_enum = AnomalySeverity(severity.lower())
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid severity: {severity}")
        
        # If user is MANAGER, filter by their shops only
        if current_user.role == UserRole.MANAGER:
            if shop_id:
                # Verify user has access to this shop
                # TODO: Add shop access verification
                pass
            else:
                # TODO: Get all shops user has access to and filter
                pass
        
        # Get anomalies
        anomalies = AnomalyService.get_anomalies(
            db=db,
            shop_id=shop_id,
            status=status_enum,
            severity=severity_enum,
            limit=limit,
            offset=offset
        )
        
        # Convert to response schema
        response_anomalies = [AnomalyResponse.from_orm(a) for a in anomalies]
        
        # Get total count (for pagination)
        query = db.query(Anomaly)
        if shop_id:
            query = query.filter(Anomaly.shop_id == shop_id)
        if status_enum:
            query = query.filter(Anomaly.status == status_enum)
        if severity_enum:
            query = query.filter(Anomaly.severity == severity_enum)
        total = query.count()
        
        return AnomalyListResponse(
            total=total,
            anomalies=response_anomalies
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting anomalies: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/{anomaly_id}",
    response_model=AnomalyResponse,
    summary="Get Anomaly by ID",
    description="Get specific anomaly by ID"
)
async def get_anomaly(
    anomaly_id: UUID = Path(..., description="Anomaly ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get specific anomaly by ID"""
    try:
        anomaly = db.query(Anomaly).filter(Anomaly.id == anomaly_id).first()
        
        if not anomaly:
            raise HTTPException(status_code=404, detail="Anomaly not found")
        
        # TODO: Verify user has access to this shop
        
        return AnomalyResponse.from_orm(anomaly)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting anomaly: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch(
    "/{anomaly_id}",
    response_model=AnomalyResponse,
    summary="Update Anomaly Status",
    description="Update anomaly status and add notes"
)
async def update_anomaly(
    anomaly_id: UUID = Path(..., description="Anomaly ID"),
    update_data: AnomalyUpdateRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update anomaly status and optionally add notes.
    
    Only users with MANAGER or OWNER role can update anomalies.
    """
    try:
        # Check permissions
        if current_user.role not in [UserRole.OWNER, UserRole.MANAGER]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        
        # Verify anomaly exists
        anomaly = db.query(Anomaly).filter(Anomaly.id == anomaly_id).first()
        if not anomaly:
            raise HTTPException(status_code=404, detail="Anomaly not found")
        
        # TODO: Verify user has access to this shop
        
        # Convert status string to enum
        try:
            status_enum = AnomalyStatus(update_data.status.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {update_data.status}")
        
        # Update anomaly
        updated_anomaly = AnomalyService.update_anomaly_status(
            db=db,
            anomaly_id=anomaly_id,
            status=status_enum,
            resolved_by=current_user.id,
            notes=update_data.notes
        )
        
        if not updated_anomaly:
            raise HTTPException(status_code=500, detail="Failed to update anomaly")
        
        return AnomalyResponse.from_orm(updated_anomaly)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating anomaly: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/frames/{shop_id}/{filename}",
    summary="Get Anomaly Frame Image",
    description="Serve saved anomaly frame image"
)
async def get_anomaly_frame(
    shop_id: UUID = Path(..., description="Shop ID"),
    filename: str = Path(..., description="Frame filename"),
    current_user: User = Depends(get_current_user)
):
    """
    Serve anomaly frame image.
    
    Returns the actual image file for display in frontend.
    """
    try:
        # TODO: Verify user has access to this shop
        
        # Construct file path
        file_path = os.path.join(BASE_DIR, "anomaly_frames", str(shop_id), filename)
        
        # Check if file exists
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Frame image not found")
        
        # Serve file
        return FileResponse(
            file_path,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=86400"}  # Cache for 1 day
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving frame image: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/stats/summary",
    summary="Get Anomaly Statistics",
    description="Get summary statistics for anomalies"
)
async def get_anomaly_stats(
    shop_id: Optional[UUID] = Query(None, description="Filter by shop ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get anomaly statistics including counts by status and severity.
    """
    try:
        from sqlalchemy import func
        
        # Base query
        query = db.query(Anomaly)
        if shop_id:
            query = query.filter(Anomaly.shop_id == shop_id)
        
        # Total count
        total = query.count()
        
        # Count by status
        status_counts = {}
        for status in AnomalyStatus:
            count = query.filter(Anomaly.status == status).count()
            status_counts[status.value] = count
        
        # Count by severity
        severity_counts = {}
        for severity in AnomalySeverity:
            count = query.filter(Anomaly.severity == severity).count()
            severity_counts[severity.value] = count
        
        # Recent anomalies (last 24 hours)
        from datetime import timedelta
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_count = query.filter(Anomaly.timestamp >= yesterday).count()
        
        return {
            "total": total,
            "recent_24h": recent_count,
            "by_status": status_counts,
            "by_severity": severity_counts
        }
        
    except Exception as e:
        logger.error(f"Error getting anomaly stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
