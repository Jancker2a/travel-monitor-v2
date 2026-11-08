from sqlalchemy import Column, String, Integer, Float, JSON, DateTime, func
from sqlalchemy.orm import relationship
from app.database import Base


class Hotel(Base):
    __tablename__ = "hotels"

    hotel_id = Column(String(128), primary_key=True, index=True)
    display_name = Column(String(256), nullable=False, index=True)
    country = Column(String(64), nullable=False, index=True)
    region = Column(String(128), nullable=True, index=True)
    stars = Column(Integer, default=4)
    ta_rating = Column(Float, nullable=True)
    ta_reviews = Column(Integer, default=0)
    specs = Column(JSON, nullable=True)  # beach_line, aquapark, heated_pools, etc.
    reputation = Column(JSON, nullable=True)  # AI dossier, pros, cons
    main_image_url = Column(String(1024), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    cohorts = relationship("OfferCohort", back_populates="hotel", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Hotel {self.hotel_id}: {self.display_name} ({self.stars}★)>"

