"""
Shop Models
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Index, UniqueConstraint, Text
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from app.db.base import Base


class Shop(Base):
    """
    Shop model - represents shops owned by OWNER users
    
    Relationships:
    - Belongs to one OWNER (owner relationship)
    - Can have multiple MANAGERs assigned (managers relationship)
    """
    __tablename__ = "shops"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    address = Column(Text, nullable=True)
    cameras = Column(ARRAY(String), nullable=True, default=list)
    telegram_chat_id = Column(String(255), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    owner = relationship("User", back_populates="owned_shops", foreign_keys=[owner_id])
    managers = relationship(
        "ShopManager",
        back_populates="shop",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Shop(id={self.id}, name={self.name}, owner_id={self.owner_id})>"


class ShopManager(Base):
    """
    ShopManager junction table - many-to-many relationship between shops and managers
    
    Links:
    - A Shop to multiple Manager users
    - A Manager user to multiple Shops
    """
    __tablename__ = "shop_managers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True)
    manager_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    shop = relationship("Shop", back_populates="managers")
    manager = relationship("User", back_populates="managed_shops")

    # Constraints
    __table_args__ = (
        # Composite unique constraint: a manager can only be assigned to a shop once
        UniqueConstraint("shop_id", "manager_id", name="uq_shop_manager"),
        # Composite index for efficient queries
        Index("ix_shop_manager_lookup", "shop_id", "manager_id"),
    )

    def __repr__(self):
        return f"<ShopManager(shop_id={self.shop_id}, manager_id={self.manager_id})>"
