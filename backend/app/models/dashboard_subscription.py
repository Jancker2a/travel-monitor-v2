import uuid
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship
from app.database import Base


class DashboardAlertSubscription(Base):
    """
    User subscription to telegram alerts for any specific dashboard or monitor.
    Can be a curated filter (e.g. 'turkey_7_10', 'egypt_autumn_2026_7_10')
    or a custom UserMonitor.
    """
    __tablename__ = "dashboard_alert_subscriptions"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    monitor_id = Column(String(64), nullable=False, index=True)
    monitor_title = Column(String(128), nullable=False)

    # Status & Mode
    is_active = Column(Boolean, default=True, nullable=False)
    notify_mode = Column(String(32), default="INSTANT", nullable=False)  # INSTANT, DIGEST_ONLY

    # Granular Alert Thresholds
    min_drop_pct = Column(Float, default=5.0, nullable=False)  # alert on >= X% drop
    min_drop_pln = Column(Float, nullable=True)  # alert on >= X PLN drop
    min_deal_score = Column(Integer, default=80, nullable=False)  # e.g. 75, 80, 85, 90
    max_budget_pln = Column(Float, nullable=True)  # ceiling price: no offers above X PLN
    only_historic_low = Column(Boolean, default=False, nullable=False)
    min_ta_rating = Column(Float, nullable=True)  # e.g. 4.0, 4.5
    preferred_airports = Column(String(128), nullable=True)  # comma separated: "WAW,KTW"

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "monitor_id", name="uq_user_monitor"),
    )

    user = relationship("User", back_populates="dashboard_subscriptions")

    def __repr__(self) -> str:
        return f"<DashboardAlertSubscription {self.monitor_id} (User {self.user_id}) - Active: {self.is_active}>"
