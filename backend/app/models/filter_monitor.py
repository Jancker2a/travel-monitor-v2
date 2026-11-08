from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, func
from app.database import Base


class FilterMonitor(Base):
    """
    Curated and user-created filters scheduled for hourly monitoring.
    Preserves all v1 filters and enables users to add arbitrary custom filters.
    """
    __tablename__ = "filter_monitors"

    id = Column(String(64), primary_key=True)  # e.g. 'turkey_7_10', 'eb_turkey_jul27_7_10'
    group_id = Column(String(32), nullable=False, index=True)  # 'turkey', 'egypt', 'greece', 'early_booking', 'arbitrage', 'custom'
    title = Column(String(128), nullable=False)
    subtitle = Column(String(256), nullable=True)
    destination = Column(String(64), nullable=False, index=True)
    target_url = Column(Text, nullable=False)
    
    # Scheduling & status
    is_active = Column(Boolean, default=True, index=True)
    is_hourly = Column(Boolean, default=True)
    last_scraped_at = Column(DateTime(timezone=True), nullable=True)
    last_offers_count = Column(Integer, default=0)
    last_min_price_pln = Column(Float, nullable=True)
    last_status = Column(String(32), default="IDLE")  # 'IDLE', 'RUNNING', 'SUCCESS', 'ERROR'
    
    # Metadata
    created_by = Column(String(64), default="system")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<FilterMonitor {self.id}: {self.title} ({self.last_offers_count} offers)>"
