from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.schemas.monitor import (
    FlyUrlParseRequest,
    FlyUrlParseResponse,
    UserMonitorCreate,
    UserMonitorUpdate,
    UserMonitorResponse,
)
from app.services.auth_service import get_current_user
from app.services.fly_url_parser import FlyUrlParser
from app.services.user_monitor_service import UserMonitorService

router = APIRouter(prefix="/api/v2/monitors", tags=["User Search Monitors"])


@router.post("/parse-url", response_model=FlyUrlParseResponse)
async def parse_fly_url(
    req: FlyUrlParseRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Parses arbitrary Fly.pl search URL into structured monitor parameters with human-readable preview.
    Requires user authentication.
    """
    return FlyUrlParser.parse(req.url)


@router.get("", response_model=List[UserMonitorResponse])
async def list_monitors(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns list of active monitors belonging to the authenticated user."""
    return await UserMonitorService.list_user_monitors(db, current_user.id)


@router.post("", response_model=UserMonitorResponse, status_code=status.HTTP_201_CREATED)
async def create_monitor(
    req: UserMonitorCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Creates a new user search monitor."""
    return await UserMonitorService.create_monitor(db, current_user.id, req)


@router.get("/{monitor_id}", response_model=UserMonitorResponse)
async def get_monitor(
    monitor_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Gets details of a single user monitor with ownership check."""
    m = await UserMonitorService.get_user_monitor(db, current_user.id, monitor_id)
    return UserMonitorService._to_response(m)


@router.put("/{monitor_id}", response_model=UserMonitorResponse)
async def update_monitor(
    monitor_id: str,
    req: UserMonitorUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Updates settings of an existing user monitor."""
    return await UserMonitorService.update_monitor(db, current_user.id, monitor_id, req)


@router.delete("/{monitor_id}")
async def delete_monitor(
    monitor_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deletes user monitor."""
    await UserMonitorService.delete_monitor(db, current_user.id, monitor_id)
    return {"ok": True, "message": "Мониторинг удалён"}


@router.post("/{monitor_id}/toggle", response_model=UserMonitorResponse)
async def toggle_monitor(
    monitor_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggles active/paused state of a user monitor."""
    return await UserMonitorService.toggle_monitor(db, current_user.id, monitor_id)


@router.post("/{monitor_id}/run-now")
async def run_monitor_now(
    monitor_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Triggers immediate live scrape for a user monitor."""
    return await UserMonitorService.run_monitor_now(db, current_user.id, monitor_id)

