import uuid
from datetime import datetime, timedelta
from typing import Any

import redis.asyncio as redis
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import CouponException, CouponStockError, CouponStatus
from app.models import (
    Activity,
    CouponPackage,
    CouponPackageSku,
    User,
    UserBehaviorLog,
    UserCoupon,
)
from app.schemas import (
    CouponCallbackRequest,
    CouponInfo,
    IssueCouponRequest,
)
from app.services.validation_service import ValidationService


class CouponService:
    def __init__(self, db: AsyncSession, redis_client: redis.Redis | None = None):
        self.db = db
        self.redis = redis_client
        self.validation_service = ValidationService(db, redis_client)

    async def issue_coupon(self, request: IssueCouponRequest) -> CouponInfo:
        if request.request_id:
            idempotent_result = await self._check_idempotent(request.request_id)
            if idempotent_result:
                return idempotent_result

        async with self.db.begin_nested():
            validation_data = await self.validation_service.validate_all(request)
            user = validation_data["user"]
            activity = validation_data["activity"]
            coupon_package = validation_data["coupon_package"]

            sku = await self._get_and_lock_sku(coupon_package.package_id)
            if not sku:
                raise CouponStockError(message="No available SKU found")

            user_coupon = await self._create_user_coupon(
                user, activity, coupon_package, sku, request.trigger_scene.value)

            await self._update_sku_status(sku, user.user_id, user_coupon)
            await self._decrement_stock(coupon_package)

            await self._cache_claimed_status(user.user_id, activity.activity_id, coupon_package.package_id)

            if request.request_id:
                await self._cache_idempotent_result(request.request_id, user_coupon)

        await self.db.commit()

        return self._build_coupon_info(user_coupon, coupon_package)

    async def validate_eligibility(self, request: Any) -> dict[str, Any]:
        validation_data = await self.validation_service.validate_all(request)
        coupon_package = validation_data["coupon_package"]
        remaining = coupon_package.total_quantity - coupon_package.claimed_quantity

        return {
            "eligible": True,
            "package_id": coupon_package.package_id,
            "package_name": coupon_package.name,
            "display_text": coupon_package.display_text,
            "remaining_stock": remaining,
            "valid_days": coupon_package.valid_days,
        }

    async def record_behavior(self, request: CouponCallbackRequest) -> None:
        log_id = f"log_{uuid.uuid4().hex}"

        behavior_log = UserBehaviorLog(
            log_id=log_id,
            user_id=request.user_id,
            activity_id=request.activity_id,
            package_id=request.package_id,
            user_coupon_id=request.user_coupon_id,
            behavior_type=request.behavior_type.value,
            trigger_scene=request.trigger_scene.value,
            extra=request.extra,
        )

        self.db.add(behavior_log)

        if request.behavior_type.value == "use" and request.user_coupon_id:
            await self._mark_coupon_used(request.user_coupon_id, request.extra)

        await self.db.commit()

    async def _check_idempotent(self, request_id: str) -> CouponInfo | None:
        if not self.redis:
            return None

        cache_key = f"coupon:idempotent:{request_id}"
        cached = await self.redis.hgetall(cache_key)
        if cached:
            try:
                return CouponInfo(
                    record_id=cached["record_id"],
                    coupon_code=cached["coupon_code"],
                    package_id=cached["package_id"],
                    package_name=cached["package_name"],
                    display_text=cached["display_text"],
                    valid_start_time=datetime.fromisoformat(cached["valid_start_time"]),
                    valid_end_time=datetime.fromisoformat(cached["valid_end_time"]),
                    applicable_comics=cached["applicable_comics"].split(",") if cached.get("applicable_comics") else [],
                )
            except (KeyError, ValueError):
                return None
        return None

    async def _cache_idempotent_result(self, request_id: str, user_coupon: UserCoupon) -> None:
        if not self.redis:
            return

        cache_key = f"coupon:idempotent:{request_id}"
        data = {
            "record_id": user_coupon.record_id,
            "coupon_code": user_coupon.coupon_code,
            "package_id": user_coupon.package_id,
            "package_name": user_coupon.display_text,
            "display_text": user_coupon.display_text,
            "valid_start_time": user_coupon.valid_start_time.isoformat(),
            "valid_end_time": user_coupon.valid_end_time.isoformat(),
            "applicable_comics": user_coupon.applicable_comics,
        }
        await self.redis.hset(cache_key, mapping=data)
        await self.redis.expire(cache_key, 86400 * 7)

    async def _get_and_lock_sku(self, package_id: str) -> CouponPackageSku | None:
        stmt = (
            select(CouponPackageSku)
            .where(
                and_(
                    CouponPackageSku.package_id == package_id,
                    CouponPackageSku.status == 0,
                )
            )
            .order_by(CouponPackageSku.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _create_user_coupon(
        self,
        user: User,
        activity: Activity,
        coupon_package: CouponPackage,
        sku: CouponPackageSku,
        trigger_scene: str,
    ) -> UserCoupon:
        now = datetime.now()
        valid_days = coupon_package.valid_days or settings.DEFAULT_COUPON_EXPIRE_DAYS
        valid_end = now + timedelta(days=valid_days)

        record_id = f"uc_{uuid.uuid4().hex}"

        user_coupon = UserCoupon(
            record_id=record_id,
            user_id=user.user_id,
            activity_id=activity.activity_id,
            package_id=coupon_package.package_id,
            sku_id=sku.sku_id,
            coupon_code=sku.coupon_code,
            status=CouponStatus.UNUSED.value,
            trigger_scene=trigger_scene,
            valid_start_time=now,
            valid_end_time=valid_end,
            applicable_comics=coupon_package.applicable_comics,
            display_text=coupon_package.display_text,
        )

        self.db.add(user_coupon)
        await self.db.flush()

        return user_coupon

    async def _update_sku_status(self, sku: CouponPackageSku, user_id: str, user_coupon: UserCoupon) -> None:
        now = datetime.now()
        stmt = (
            update(CouponPackageSku)
            .where(CouponPackageSku.id == sku.id)
            .values(
                status=1,
                user_id=user_id,
                claimed_at=now,
                expire_time=user_coupon.valid_end_time,
            )
        )
        await self.db.execute(stmt)

    async def _decrement_stock(self, coupon_package: CouponPackage) -> None:
        stock_key = f"coupon:stock:{coupon_package.package_id}"

        if self.redis:
            new_stock = await self.redis.decr(stock_key)
            if new_stock < 0:
                await self.redis.set(stock_key, 0)

        stmt = (
            update(CouponPackage)
            .where(CouponPackage.id == coupon_package.id)
            .values(
                claimed_quantity=CouponPackage.claimed_quantity + 1,
            )
        )
        await self.db.execute(stmt)

        result = await self.db.execute(
            select(func.count())
            .select_from(CouponPackageSku)
            .where(
                and_(
                    CouponPackageSku.package_id == coupon_package.package_id,
                    CouponPackageSku.status == 0,
                )
            )
        )
        remaining = result.scalar() or 0
        if remaining == 0:
            raise CouponStockError(message="No more stock available")

    async def _cache_claimed_status(self, user_id: str, activity_id: str, package_id: str) -> None:
        if not self.redis:
            return

        cache_key = f"coupon:claimed:{user_id}:{activity_id}:{package_id}"
        await self.redis.setex(cache_key, 86400, "1")

    def _build_coupon_info(self, user_coupon: UserCoupon, coupon_package: CouponPackage) -> CouponInfo:
        applicable_comics = []
        if user_coupon.applicable_comics:
            applicable_comics = [c.strip() for c in user_coupon.applicable_comics.split(",") if c.strip()]

        return CouponInfo(
            record_id=user_coupon.record_id,
            coupon_code=user_coupon.coupon_code,
            package_id=user_coupon.package_id,
            package_name=coupon_package.name,
            display_text=user_coupon.display_text,
            valid_start_time=user_coupon.valid_start_time,
            valid_end_time=user_coupon.valid_end_time,
            applicable_comics=applicable_comics,
        )

    async def _mark_coupon_used(self, user_coupon_id: str, extra: dict[str, Any]) -> None:
        stmt = (
            select(UserCoupon)
            .where(UserCoupon.record_id == user_coupon_id)
            .with_for_update()
        )
        result = await self.db.execute(stmt)
        user_coupon = result.scalar_one_or_none()

        if user_coupon and user_coupon.status == CouponStatus.UNUSED.value:
            now = datetime.now()
            user_coupon.status = CouponStatus.USED.value
            user_coupon.used_at = now
            user_coupon.used_comic_id = extra.get("comic_id", "")

            sku_stmt = (
                update(CouponPackageSku)
                .where(CouponPackageSku.sku_id == user_coupon.sku_id)
                .values(status=2, used_at=now)
            )
            await self.db.execute(sku_stmt)
