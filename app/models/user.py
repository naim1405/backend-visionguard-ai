"""
User Model
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, String, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base


class UserRole(str, PyEnum):
    """User role enumeration"""
    OWNER = "OWNER"
    MANAGER = "MANAGER"


class User(Base):
    """
    User model - represents both OWNER and MANAGER users
    
    Relationships:
    - OWNER: can own multiple shops (shops relationship)
    - MANAGER: can be assigned to multiple shops (managed_shops relationship)
    """
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    # For OWNER: shops they own
    owned_shops = relationship(
        "Shop",
        back_populates="owner",
        foreign_keys="Shop.owner_id",
        cascade="all, delete-orphan"
    )
    
    # For MANAGER: shops they manage (through shop_managers junction table)
    managed_shops = relationship(
        "ShopManager",
        back_populates="manager",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"
