import uuid
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    func,
)
from sqlalchemy.orm import relationship
from app.database import Base


class UserMonitor(Base):
    """
    Personal search monitor configured by a specific user.
    Can be created from interactive UI search or from raw Fly.pl URL.
    """
    __tablename__ = "user_monitors"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    title = Column(String(128), nullable=False)
    source_type = Column(String(32), default="CUSTOM_FILTER", nullable=False)  # CUSTOM_FILTER, FLY_URL
    fly_source_url = Column(Text, nullable=True)
    filter_params_json = Column(Text, nullable=False)  # JSON-encoded dict of search parameters
    
    # Execution & Notification settings
    check_interval_hours = Column(Integer, default=3, nullable=False)  # 1, 3, 6, 12, 24
    min_drop_pct = Column(Float, default=5.0, nullable=False)
    max_budget_pln = Column(Float, nullable=True)
    notify_telegram = Column(Boolean, default=True, nullable=False)
    notify_email = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Status & Last scrape snapshot
    status = Column(String(32), default="IDLE", nullable=False)  # IDLE, RUNNING, SUCCESS, ERROR
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    last_offers_count = Column(Integer, default=0, nullable=False)
    last_min_price_pln = Column(Float, nullable=True)
    last_error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="monitors")

    def __repr__(self) -> str:
        return f"<UserMonitor {self.id}: '{self.title}' (User {self.user_id})>"
