import json
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from fastapi import HTTPException, status
from app.models.user_monitor import UserMonitor
from app.schemas.monitor import UserMonitorCreate, UserMonitorUpdate, UserMonitorResponse
from app.schemas.search import SearchRequest
from app.services.search_service import SearchService

logger = logging.getLogger("travel_monitor_2")


class UserMonitorService:
    @classmethod
    async def create_monitor(
        cls, db: AsyncSession, user_id: str, req: UserMonitorCreate
    ) -> UserMonitorResponse:
        monitor = UserMonitor(
            user_id=user_id,
            title=req.title.strip(),
            source_type=req.source_type,
            fly_source_url=req.fly_source_url,
            filter_params_json=json.dumps(req.filter_params, ensure_ascii=False),
            check_interval_hours=req.check_interval_hours,
            min_drop_pct=req.min_drop_pct,
            max_budget_pln=req.max_budget_pln,
            notify_telegram=req.notify_telegram,
            notify_email=req.notify_email,
            is_active=True,
            status="IDLE",
        )
        db.add(monitor)
        await db.commit()
        await db.refresh(monitor)
        
        logger.info(f"Created UserMonitor '{monitor.title}' (id: {monitor.id}) for user {user_id}")
        return cls._to_response(monitor)

    @classmethod
    async def list_user_monitors(
        cls, db: AsyncSession, user_id: str
    ) -> List[UserMonitorResponse]:
        """Strict multi-tenant isolation: returns monitors belonging exclusively to user_id."""
        stmt = (
            select(UserMonitor)
            .where(UserMonitor.user_id == user_id)
            .order_by(desc(UserMonitor.created_at))
        )
        result = await db.execute(stmt)
        monitors = result.scalars().all()
        return [cls._to_response(m) for m in monitors]

    @classmethod
    async def get_user_monitor(
        cls, db: AsyncSession, user_id: str, monitor_id: str
    ) -> UserMonitor:
        """Finds monitor and enforces ownership security check."""
        stmt = select(UserMonitor).where(
            UserMonitor.id == monitor_id,
            UserMonitor.user_id == user_id,
        )
        res = await db.execute(stmt)
        monitor = res.scalar_one_or_none()
        if not monitor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Мониторинг не найден или доступ к нему запрещён",
            )
        return monitor

    @classmethod
    async def update_monitor(
        cls, db: AsyncSession, user_id: str, monitor_id: str, req: UserMonitorUpdate
    ) -> UserMonitorResponse:
        monitor = await cls.get_user_monitor(db, user_id, monitor_id)
        
        if req.title is not None:
            monitor.title = req.title.strip()
        if req.check_interval_hours is not None:
            monitor.check_interval_hours = req.check_interval_hours
        if req.min_drop_pct is not None:
            monitor.min_drop_pct = req.min_drop_pct
        if req.max_budget_pln is not None:
            monitor.max_budget_pln = req.max_budget_pln
        if req.notify_telegram is not None:
            monitor.notify_telegram = req.notify_telegram
        if req.notify_email is not None:
            monitor.notify_email = req.notify_email
        if req.is_active is not None:
            monitor.is_active = req.is_active
        
        await db.commit()
        await db.refresh(monitor)
        return cls._to_response(monitor)

    @classmethod
    async def delete_monitor(
        cls, db: AsyncSession, user_id: str, monitor_id: str
    ) -> bool:
        monitor = await cls.get_user_monitor(db, user_id, monitor_id)
        await db.delete(monitor)
        await db.commit()
        logger.info(f"Deleted UserMonitor {monitor_id} of user {user_id}")
        return True

    @classmethod
    async def toggle_monitor(
        cls, db: AsyncSession, user_id: str, monitor_id: str
    ) -> UserMonitorResponse:
        monitor = await cls.get_user_monitor(db, user_id, monitor_id)
        monitor.is_active = not monitor.is_active
        await db.commit()
        await db.refresh(monitor)
        return cls._to_response(monitor)

    @classmethod
    async def run_monitor_now(
        cls, db: AsyncSession, user_id: str, monitor_id: str
    ) -> Dict[str, Any]:
        """Performs immediate on-demand live scrape execution for a user monitor."""
        monitor = await cls.get_user_monitor(db, user_id, monitor_id)
        
        params_dict = json.loads(monitor.filter_params_json)
        search_req = SearchRequest(**params_dict)
        
        monitor.status = "RUNNING"
        await db.commit()
        
        try:
            search_resp = await SearchService.execute_search(
                db=db,
                req=search_req,
                force_live=True,
                client_ip=f"user-{user_id[:8]}",
            )
            
            offers = search_resp.hotels or []
            min_price = min([h.current_offer.total_price_pln for h in offers]) if offers else None
            
            monitor.status = "SUCCESS"
            monitor.last_checked_at = datetime.now(timezone.utc)
            monitor.last_offers_count = len(offers)
            monitor.last_min_price_pln = min_price
            monitor.last_error_message = None
            
            await db.commit()
            await db.refresh(monitor)
            
            return {
                "monitor": cls._to_response(monitor),
                "total_found": len(offers),
                "min_price_pln": min_price,
                "is_cached": search_resp.is_cached,
            }
        except Exception as e:
            logger.error(f"Error running monitor {monitor_id}: {e}")
            monitor.status = "ERROR"
            monitor.last_error_message = str(e)[:500]
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка выполнения мониторинга: {str(e)}",
            )

    @staticmethod
    def _to_response(m: UserMonitor) -> UserMonitorResponse:
        try:
            params = json.loads(m.filter_params_json)
        except Exception:
            params = {}
        
        return UserMonitorResponse(
            id=m.id,
            user_id=m.user_id,
            title=m.title,
            source_type=m.source_type,
            fly_source_url=m.fly_source_url,
            filter_params=params,
            check_interval_hours=m.check_interval_hours,
            min_drop_pct=m.min_drop_pct,
            max_budget_pln=m.max_budget_pln,
            notify_telegram=m.notify_telegram,
            notify_email=m.notify_email,
            is_active=m.is_active,
            status=m.status,
            last_checked_at=m.last_checked_at,
            last_offers_count=m.last_offers_count,
            last_min_price_pln=m.last_min_price_pln,
            last_error_message=m.last_error_message,
            created_at=m.created_at,
        )
