"""
Authentication Routes
Endpoints for user registration, login, and token management
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from sqlalchemy.orm import Session
from datetime import timedelta

from app.db import get_db
from app.models import User, UserRole
from app.core.auth import hash_password, verify_password, create_access_token, create_refresh_token
from app.core.dependencies import get_current_user

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/auth", tags=["Authentication"])


# ============================================================================
# Pydantic Models for Request/Response
# ============================================================================


class RegisterOwnerRequest(BaseModel):
    """Request model for owner registration"""
    name: str = Field(..., min_length=2, max_length=255, description="User's full name")
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, max_length=100, description="User's password (min 8 characters)")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "John Doe",
                "email": "john.doe@example.com",
                "password": "securePassword123"
            }
        }
    )


class RegisterManagerRequest(BaseModel):
    """Request model for manager registration"""
    name: str = Field(..., min_length=2, max_length=255, description="Manager's full name")
    email: EmailStr = Field(..., description="Manager's email address")
    password: str = Field(..., min_length=8, max_length=100, description="Manager's password (min 8 characters)")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Jane Smith",
                "email": "jane.smith@example.com",
                "password": "securePassword123"
            }
        }
    )


class LoginRequest(BaseModel):
    """Request model for login"""
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "john.doe@example.com",
                "password": "securePassword123"
            }
        }
    )


class TokenResponse(BaseModel):
    """Response model for successful authentication"""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    user: dict = Field(..., description="User information")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "user": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "name": "John Doe",
                    "email": "john.doe@example.com",
                    "role": "OWNER"
                }
            }
        }
    )


class UserResponse(BaseModel):
    """Response model for user information"""
    id: str = Field(..., description="User ID")
    name: str = Field(..., description="User's name")
    email: str = Field(..., description="User's email")
    role: str = Field(..., description="User's role")
    created_at: str = Field(..., description="Account creation timestamp")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "John Doe",
                "email": "john.doe@example.com",
                "role": "OWNER",
                "created_at": "2025-12-02T10:30:00"
            }
        }
    )


class RefreshTokenRequest(BaseModel):
    """Request model for token refresh"""
    refresh_token: str = Field(..., description="Refresh token")


# ============================================================================
# Authentication Endpoints
# ============================================================================


@router.post(
    "/register-owner",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new owner account",
    description="Create a new owner account with email and password. Returns JWT tokens."
)
async def register_owner(
    request: RegisterOwnerRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new OWNER user
    
    - **name**: User's full name
    - **email**: Valid email address (must be unique)
    - **password**: Strong password (minimum 8 characters)
    
    Returns access and refresh tokens upon successful registration.
    """
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = hash_password(request.password)
    new_user = User(
        name=request.name,
        email=request.email,
        password_hash=hashed_password,
        role=UserRole.OWNER
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    logger.info(f"New owner registered: {new_user.email} (ID: {new_user.id})")
    
    # Generate tokens
    token_data = {
        "sub": str(new_user.id),
        "email": new_user.email,
        "role": new_user.role.value
    }
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user={
            "id": str(new_user.id),
            "name": new_user.name,
            "email": new_user.email,
            "role": new_user.role.value
        }
    )


@router.post(
    "/register-manager",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new manager account",
    description="Create a new manager account with email and password. Returns JWT tokens."
)
async def register_manager(
    request: RegisterManagerRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new MANAGER user
    
    Note: Typically managers are created automatically when shops are created,
    but this endpoint allows manual manager registration.
    """
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = hash_password(request.password)
    new_user = User(
        name=request.name,
        email=request.email,
        password_hash=hashed_password,
        role=UserRole.MANAGER
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    logger.info(f"New manager registered: {new_user.email} (ID: {new_user.id})")
    
    # Generate tokens
    token_data = {
        "sub": str(new_user.id),
        "email": new_user.email,
        "role": new_user.role.value
    }
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user={
            "id": str(new_user.id),
            "name": new_user.name,
            "email": new_user.email,
            "role": new_user.role.value
        }
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login with email and password",
    description="Authenticate user and receive JWT tokens"
)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Login with email and password
    
    - **email**: User's email address
    - **password**: User's password
    
    Returns access and refresh tokens upon successful authentication.
    """
    # Find user by email
    user = db.query(User).filter(User.email == request.email).first()
    
    # Verify user exists and password is correct
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logger.info(f"User logged in: {user.email} (ID: {user.id})")
    
    # Generate tokens
    token_data = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.value
    }
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user={
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "role": user.role.value
        }
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user information",
    description="Get information about the currently authenticated user"
)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user's information
    
    Requires valid JWT token in Authorization header
    """
    return UserResponse(
        id=str(current_user.id),
        name=current_user.name,
        email=current_user.email,
        role=current_user.role.value,
        created_at=current_user.created_at.isoformat()
    )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Logout user",
    description="Logout current user (client should discard tokens)"
)
async def logout(current_user: User = Depends(get_current_user)):
    """
    Logout user
    
    Note: JWT tokens are stateless, so logout is handled on the client side
    by discarding the tokens. This endpoint is provided for consistency
    and can be extended to implement token blacklisting if needed.
    """
    logger.info(f"User logged out: {current_user.email} (ID: {current_user.id})")
    return {"message": "Successfully logged out"}
