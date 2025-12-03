"""
Shop Management Routes
CRUD endpoints for shops with manager assignment logic
"""

import logging
import secrets
import string
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, UserRole, Shop, ShopManager
from app.core.dependencies import get_current_user, require_owner, verify_shop_access
from app.core.auth import hash_password

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/shops", tags=["Shop Management"])


# ============================================================================
# Pydantic Models for Request/Response
# ============================================================================


class CreateShopRequest(BaseModel):
    """Request model for creating a shop"""
    name: str = Field(..., min_length=2, max_length=255, description="Shop name")
    address: Optional[str] = Field(None, description="Shop address")
    cameras: List[str] = Field(
        default_factory=list,
        description="List of camera URLs (RTSP, HTTP, etc.)"
    )
    assigned_manager_emails: List[EmailStr] = Field(
        default_factory=list,
        description="List of manager emails to assign to this shop"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Downtown Store",
                "address": "123 Main St, City, State 12345",
                "cameras": ["rtsp://camera1.example.com/stream", "rtsp://camera2.example.com/stream"],
                "assigned_manager_emails": ["manager1@example.com", "manager2@example.com"]
            }
        }
    )


class UpdateShopRequest(BaseModel):
    """Request model for updating a shop"""
    name: Optional[str] = Field(None, min_length=2, max_length=255, description="Shop name")
    address: Optional[str] = Field(None, description="Shop address")
    cameras: Optional[List[str]] = Field(
        None,
        description="List of camera URLs (replaces existing cameras)"
    )
    assigned_manager_emails: Optional[List[EmailStr]] = Field(
        None,
        description="List of manager emails (replaces existing assignments)"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Downtown Store - Updated",
                "address": "456 New St, City, State 12345",
                "cameras": ["rtsp://camera1.example.com/stream", "rtsp://camera3.example.com/stream"],
                "assigned_manager_emails": ["manager1@example.com", "manager3@example.com"]
            }
        }
    )


class ManagerInfo(BaseModel):
    """Manager information in shop response"""
    id: str
    name: str
    email: str


class ShopResponse(BaseModel):
    """Response model for shop information"""
    id: str
    owner_id: str
    name: str
    address: Optional[str]
    cameras: List[str]
    telegram_chat_id: Optional[str]
    managers: List[ManagerInfo]
    created_at: str
    updated_at: str
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "owner_id": "987fcdeb-51a2-43d1-b789-123456789abc",
                "name": "Downtown Store",
                "address": "123 Main St, City, State 12345",
                "cameras": ["rtsp://camera1.example.com/stream", "rtsp://camera2.example.com/stream"],
                "telegram_chat_id": "123456789",
                "managers": [
                    {
                        "id": "abc12345-6789-def0-1234-567890abcdef",
                        "name": "Jane Manager",
                        "email": "manager1@example.com"
                    }
                ],
                "created_at": "2025-12-02T10:30:00",
                "updated_at": "2025-12-02T10:30:00"
            }
        }
    )


# ============================================================================
# Helper Functions
# ============================================================================


def generate_temporary_password(length: int = 12) -> str:
    """Generate a secure temporary password"""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def assign_managers_to_shop(
    shop: Shop,
    manager_emails: List[str],
    db: Session
) -> List[User]:
    """
    Assign managers to a shop by email
    Creates manager accounts if they don't exist
    
    Args:
        shop: Shop object
        manager_emails: List of manager email addresses
        db: Database session
        
    Returns:
        List of assigned manager User objects
    """
    assigned_managers = []
    
    for email in manager_emails:
        # Check if user exists
        manager = db.query(User).filter(User.email == email).first()
        
        if not manager:
            # Create new manager with temporary password
            temp_password = generate_temporary_password()
            manager = User(
                name=email.split('@')[0].title(),  # Use email prefix as name
                email=email,
                password_hash=hash_password(temp_password),
                role=UserRole.MANAGER
            )
            db.add(manager)
            db.flush()  # Get the manager ID without committing
            
            logger.info(f"Created new manager account: {email} (ID: {manager.id})")
            # In production, send email with temporary password
            logger.info(f"Temporary password for {email}: {temp_password}")
        
        elif manager.role != UserRole.MANAGER:
            # Skip if user exists but is not a manager
            logger.warning(f"User {email} exists but is not a MANAGER (role: {manager.role})")
            continue
        
        # Check if manager is already assigned to ANY shop
        existing_assignment = db.query(ShopManager).filter(
            ShopManager.manager_id == manager.id
        ).first()
        
        if existing_assignment:
            # Manager can only be assigned to one shop
            logger.warning(f"Manager {email} is already assigned to another shop")
            continue
        
        # Check if assignment already exists for this shop
        shop_assignment = db.query(ShopManager).filter(
            ShopManager.shop_id == shop.id,
            ShopManager.manager_id == manager.id
        ).first()
        
        if not shop_assignment:
            # Create new assignment
            assignment = ShopManager(
                shop_id=shop.id,
                manager_id=manager.id
            )
            db.add(assignment)
            logger.info(f"Assigned manager {email} to shop {shop.name}")
        
        assigned_managers.append(manager)
    
    return assigned_managers


def build_shop_response(shop: Shop, db: Session) -> ShopResponse:
    """Build shop response with manager information"""
    # Get all managers for this shop
    shop_managers = db.query(ShopManager).filter(ShopManager.shop_id == shop.id).all()
    manager_ids = [sm.manager_id for sm in shop_managers]
    managers = db.query(User).filter(User.id.in_(manager_ids)).all() if manager_ids else []
    
    return ShopResponse(
        id=str(shop.id),
        owner_id=str(shop.owner_id),
        name=shop.name,
        address=shop.address,
        cameras=shop.cameras or [],
        telegram_chat_id=shop.telegram_chat_id,
        managers=[
            ManagerInfo(
                id=str(m.id),
                name=m.name,
                email=m.email
            ) for m in managers
        ],
        created_at=shop.created_at.isoformat(),
        updated_at=shop.updated_at.isoformat()
    )


# ============================================================================
# Shop CRUD Endpoints
# ============================================================================


@router.post(
    "",
    response_model=ShopResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new shop (OWNER only)",
    description="Create a new shop and optionally assign managers by email"
)
async def create_shop(
    request: CreateShopRequest,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db)
):
    """
    Create a new shop
    
    - **name**: Shop name (required)
    - **address**: Shop address (optional)
    - **cameras**: List of camera URLs (optional)
    - **assigned_manager_emails**: List of manager emails to assign
    
    If a manager email doesn't exist:
    - A new MANAGER account will be created automatically
    - A temporary password will be generated
    - The manager should be notified to set their password
    """
    # Create shop
    new_shop = Shop(
        owner_id=current_user.id,
        name=request.name,
        address=request.address,
        cameras=request.cameras
    )
    
    db.add(new_shop)
    db.flush()  # Get shop ID without committing
    
    # Assign managers
    if request.assigned_manager_emails:
        assign_managers_to_shop(new_shop, request.assigned_manager_emails, db)
    
    db.commit()
    db.refresh(new_shop)
    
    logger.info(f"Shop created: {new_shop.name} (ID: {new_shop.id}) by owner {current_user.email}")
    
    return build_shop_response(new_shop, db)


@router.get(
    "",
    response_model=List[ShopResponse],
    summary="Get all shops accessible to current user",
    description="OWNERs see their shops, MANAGERs see assigned shops"
)
async def get_shops(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all shops accessible to the current user
    
    - OWNER: Returns all shops owned by the owner
    - MANAGER: Returns all shops assigned to the manager
    """
    if current_user.role == UserRole.OWNER:
        # Get all shops owned by this owner
        shops = db.query(Shop).filter(Shop.owner_id == current_user.id).all()
    else:  # MANAGER
        # Get all shops assigned to this manager
        shop_assignments = db.query(ShopManager).filter(
            ShopManager.manager_id == current_user.id
        ).all()
        shop_ids = [sa.shop_id for sa in shop_assignments]
        shops = db.query(Shop).filter(Shop.id.in_(shop_ids)).all() if shop_ids else []
    
    return [build_shop_response(shop, db) for shop in shops]


@router.get(
    "/{shop_id}",
    response_model=ShopResponse,
    summary="Get shop details",
    description="Get details of a specific shop (requires access)"
)
async def get_shop(
    shop_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get shop details
    
    User must have access to the shop:
    - OWNER: must own the shop
    - MANAGER: must be assigned to the shop
    """
    shop = verify_shop_access(shop_id, current_user, db)
    return build_shop_response(shop, db)


@router.put(
    "/{shop_id}",
    response_model=ShopResponse,
    summary="Update shop (OWNER only)",
    description="Update shop details and/or manager assignments"
)
async def update_shop(
    shop_id: UUID,
    request: UpdateShopRequest,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db)
):
    """
    Update shop information
    
    Only the shop owner can update shop details.
    
    - **name**: New shop name (optional)
    - **address**: New shop address (optional)
    - **cameras**: New list of camera URLs (replaces existing, optional)
    - **assigned_manager_emails**: New list of manager emails (replaces existing)
    """
    # Verify ownership
    shop = verify_shop_access(shop_id, current_user, db)
    
    # Update basic fields
    if request.name is not None:
        shop.name = request.name
    if request.address is not None:
        shop.address = request.address
    if request.cameras is not None:
        shop.cameras = request.cameras
    
    # Update manager assignments if provided
    if request.assigned_manager_emails is not None:
        # Remove existing assignments
        db.query(ShopManager).filter(ShopManager.shop_id == shop_id).delete()
        
        # Add new assignments
        if request.assigned_manager_emails:
            assign_managers_to_shop(shop, request.assigned_manager_emails, db)
    
    db.commit()
    db.refresh(shop)
    
    logger.info(f"Shop updated: {shop.name} (ID: {shop.id}) by owner {current_user.email}")
    
    return build_shop_response(shop, db)


@router.delete(
    "/{shop_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete shop (OWNER only)",
    description="Delete a shop and all associated data"
)
async def delete_shop(
    shop_id: UUID,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db)
):
    """
    Delete a shop
    
    Only the shop owner can delete a shop.
    This will also delete all manager assignments for this shop.
    """
    # Verify ownership
    shop = verify_shop_access(shop_id, current_user, db)
    
    shop_name = shop.name
    db.delete(shop)
    db.commit()
    
    logger.info(f"Shop deleted: {shop_name} (ID: {shop_id}) by owner {current_user.email}")
    
    return None


@router.get(
    "/{shop_id}/managers",
    response_model=List[ManagerInfo],
    summary="Get shop managers",
    description="Get list of managers assigned to a shop"
)
async def get_shop_managers(
    shop_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all managers assigned to a shop
    
    User must have access to the shop.
    """
    shop = verify_shop_access(shop_id, current_user, db)
    
    # Get managers
    shop_managers = db.query(ShopManager).filter(ShopManager.shop_id == shop_id).all()
    manager_ids = [sm.manager_id for sm in shop_managers]
    managers = db.query(User).filter(User.id.in_(manager_ids)).all() if manager_ids else []
    
    return [
        ManagerInfo(
            id=str(m.id),
            name=m.name,
            email=m.email
        ) for m in managers
    ]


@router.post(
    "/check-manager-email",
    response_model=dict,
    summary="Check if email has manager account",
    description="Verify if an email is registered with MANAGER role"
)
async def check_manager_email(
    request: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check if an email exists with MANAGER role
    
    Returns:
    - exists: boolean indicating if the email exists as a manager
    - email: the email that was checked
    """
    email = request.get('email')
    
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is required"
        )
    
    # Check if user exists with MANAGER role
    manager = db.query(User).filter(
        User.email == email,
        User.role == UserRole.MANAGER
    ).first()
    
    return {
        "exists": manager is not None,
        "email": email
    }
