import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, func
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    """Registered application user with credentials, digest preferences, and personal monitor settings."""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(128), nullable=True)
    role = Column(String(32), default="USER", nullable=False)  # USER, PRO, ADMIN
    telegram_chat_id = Column(String(64), nullable=True, index=True)
    telegram_notifications_enabled = Column(Boolean, default=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Daily Digest settings
    digest_enabled = Column(Boolean, default=True, nullable=False)
    digest_time = Column(String(8), default="09:00", nullable=False)
    digest_days = Column(String(16), default="ALL", nullable=False)  # ALL, WEEKDAYS, WEEKENDS
    digest_include_watchlist = Column(Boolean, default=True, nullable=False)
    digest_include_top_drops = Column(Boolean, default=True, nullable=False)
    digest_include_hot_deals = Column(Boolean, default=True, nullable=False)
    digest_include_historic_lows = Column(Boolean, default=True, nullable=False)
    digest_min_deal_score = Column(Integer, default=80, nullable=False)
    digest_max_offers = Column(Integer, default=5, nullable=False)
    digest_only_if_changes = Column(Boolean, default=True, nullable=False)

    # Quiet hours settings
    quiet_hours_enabled = Column(Boolean, default=True, nullable=False)
    quiet_hours_start = Column(Integer, default=23, nullable=False)
    quiet_hours_end = Column(Integer, default=8, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    monitors = relationship("UserMonitor", back_populates="user", cascade="all, delete-orphan")
    dashboard_subscriptions = relationship("DashboardAlertSubscription", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"


