from pydantic import BaseModel, Field
from typing import List, Optional


class Top10HotelItem(BaseModel):
    name: str
    price: float
    position: int


class TimelinePoint(BaseModel):
    time: str
    avg_price: float
    min_price: float
    max_price: float
    top10_hotels: List[Top10HotelItem] = Field(default_factory=list)


class TimelineStats(BaseModel):
    current_avg_top10: float
    historical_min_avg: float
    historical_max_avg: float
    overall_trend: str
    last_updated: str


class TimelineResponse(BaseModel):
    filter_id: str
    range: str
    points_count: int
    timeline: List[TimelinePoint]
    stats: Optional[TimelineStats] = None
