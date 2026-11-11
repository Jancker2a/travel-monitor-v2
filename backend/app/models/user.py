import uuid
from sqlalchemy import Column, String, Boolean, DateTime, func
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    """Registered application user with credentials and personal monitor settings."""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(128), nullable=True)
    role = Column(String(32), default="USER", nullable=False)  # USER, PRO, ADMIN
    telegram_chat_id = Column(String(64), nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    monitors = relationship("UserMonitor", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"
