import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services.dashboard_alert_service import DashboardAlertService
from app.schemas.dashboard_subscription import (
    DashboardSubscriptionResponse,
    DashboardSubscriptionUpdateRequest,
    DashboardSubscriptionTestResponse,
)

logger = logging.getLogger("travel_monitor_2.routers.dashboard_subscriptions")

router = APIRouter(prefix="/api/v2/monitors/alerts", tags=["Dashboard Alert Subscriptions"])


@router.get("", response_model=List[DashboardSubscriptionResponse])
@router.get("/", response_model=List[DashboardSubscriptionResponse])
async def list_user_subscriptions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lists all active dashboard alert subscriptions for the authenticated user."""
    subs = await DashboardAlertService.list_user_subscriptions(db, current_user.id)
    return [DashboardSubscriptionResponse.model_validate(s) for s in subs]


@router.get("/{monitor_id}", response_model=DashboardSubscriptionResponse)
async def get_monitor_subscription(
    monitor_id: str,
    title: Optional[str] = Query(None, description="Default title if creating placeholder"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns alert settings for a specific dashboard/monitor for the authenticated user."""
    sub = await DashboardAlertService.get_subscription(db, current_user.id, monitor_id, title)
    return DashboardSubscriptionResponse.model_validate(sub)


@router.put("/{monitor_id}", response_model=DashboardSubscriptionResponse)
async def save_monitor_subscription(
    monitor_id: str,
    req: DashboardSubscriptionUpdateRequest,
    title: Optional[str] = Query(None, description="Monitor title"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Saves or updates alert thresholds for a specific dashboard/monitor."""
    sub = await DashboardAlertService.save_subscription(
        db,
        user_id=current_user.id,
        monitor_id=monitor_id,
        monitor_title=req.monitor_title or title or f"Мониторинг {monitor_id}",
        data=req,
    )
    return DashboardSubscriptionResponse.model_validate(sub)


@router.post("/{monitor_id}/test", response_model=DashboardSubscriptionTestResponse)
async def test_monitor_alert(
    monitor_id: str,
    title: Optional[str] = Query(None, description="Monitor title"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Sends a test Telegram alert for this monitor using actual live database data."""
    return await DashboardAlertService.send_test_dashboard_alert(
        db,
        user=current_user,
        monitor_id=monitor_id,
        monitor_title=title,
    )
