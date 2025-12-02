"""
Authentication Dependencies and Middleware
FastAPI dependencies for JWT authentication and role-based authorization
"""

from typing import Optional
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from uuid import UUID

from app.db import get_db
from app.models import User, UserRole, Shop, ShopManager
from app.core.auth import verify_token

# HTTP Bearer token scheme
security = HTTPBearer()


# ============================================================================
# Authentication Dependencies
# ============================================================================


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get current authenticated user from JWT token
    
    Args:
        credentials: Bearer token from Authorization header
        db: Database session
        
    Returns:
        User object if token is valid
        
    Raises:
        HTTPException: 401 if token is invalid or user not found
        
    Usage:
        @app.get("/protected")
        def protected_route(current_user: User = Depends(get_current_user)):
            return {"user_id": current_user.id}
    """
    token = credentials.credentials
    
    # Verify token
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract user ID from token
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Fetch user from database
    try:
        user = db.query(User).filter(User.id == UUID(user_id)).first()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def get_current_user_ws(
    token: Optional[str] = None,
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get current user from WebSocket token (query parameter)
    
    Args:
        token: JWT token from query parameter
        db: Database session
        
    Returns:
        User object if token is valid
        
    Raises:
        HTTPException: 401 if token is invalid or user not found
        
    Usage in WebSocket:
        @app.websocket("/ws")
        async def websocket_endpoint(
            websocket: WebSocket,
            current_user: User = Depends(get_current_user_ws)
        ):
            # Use current_user
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token not provided",
        )
    
    # Verify token
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    
    # Extract user ID from token
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    
    # Fetch user from database
    try:
        user = db.query(User).filter(User.id == UUID(user_id)).first()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
        )
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    return user


# ============================================================================
# Authorization Dependencies (Role-Based)
# ============================================================================


def require_role(required_role: UserRole):
    """
    Factory function to create role-based authorization dependency
    
    Args:
        required_role: Required user role (OWNER or MANAGER)
        
    Returns:
        Dependency function that checks user role
        
    Usage:
        @app.get("/owner-only")
        def owner_only(current_user: User = Depends(require_role(UserRole.OWNER))):
            return {"message": "Owner access granted"}
    """
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {required_role.value}"
            )
        return current_user
    
    return role_checker


# Convenience dependencies for specific roles
require_owner = require_role(UserRole.OWNER)
require_manager = require_role(UserRole.MANAGER)


# ============================================================================
# Shop Access Authorization
# ============================================================================


def verify_shop_access(shop_id: UUID, current_user: User, db: Session) -> Shop:
    """
    Verify that current user has access to a specific shop
    
    Rules:
    - OWNER: must own the shop
    - MANAGER: must be assigned to the shop
    
    Args:
        shop_id: Shop UUID
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Shop object if access is granted
        
    Raises:
        HTTPException: 403 if access denied, 404 if shop not found
    """
    # Fetch shop
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shop not found"
        )
    
    # Check access based on role
    if current_user.role == UserRole.OWNER:
        # Owner must own the shop
        if shop.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You don't own this shop."
            )
    elif current_user.role == UserRole.MANAGER:
        # Manager must be assigned to the shop
        assignment = db.query(ShopManager).filter(
            ShopManager.shop_id == shop_id,
            ShopManager.manager_id == current_user.id
        ).first()
        
        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You are not assigned to this shop."
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied."
        )
    
    return shop


async def get_accessible_shop(
    shop_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Shop:
    """
    Dependency to get a shop that the current user has access to
    
    Usage:
        @app.get("/shops/{shop_id}")
        def get_shop(shop: Shop = Depends(get_accessible_shop)):
            return shop
    """
    return verify_shop_access(shop_id, current_user, db)
