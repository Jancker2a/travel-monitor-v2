from sqlalchemy import (
    Column,
    String,
    Float,
    DateTime,
    Boolean,
    ForeignKey,
    func,
)
from app.database import Base


class WatchlistItem(Base):
    __tablename__ = "watchlists"

    watch_id = Column(String(32), primary_key=True)
    user_chat_id = Column(String(64), nullable=False, index=True)
    cohort_hash = Column(String(32), ForeignKey("offer_cohorts.cohort_hash", ondelete="CASCADE"), nullable=False, index=True)
    target_price_pln = Column(Float, nullable=True)
    notify_any_drop = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_notified_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Watchlist {self.watch_id}: User {self.user_chat_id} -> Cohort {self.cohort_hash[:8]}>"

