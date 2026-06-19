from datetime import datetime
from typing import Any

import redis.asyncio as redis
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import (
    ActivityStatus,
    CouponActivityError,
    CouponAlreadyClaimedError,
    CouponEligibilityError,
    CouponStockError,
    CouponUserError,
)
from app.models import Activity, CouponPackage, User, UserCoupon
from app.schemas import IssueCouponRequest, ValidateCouponRequest


class ValidationService:
    def __init__(self, db: AsyncSession, redis_client: redis.Redis | None = None):
        self.db = db
        self.redis = redis_client

    async def validate_all(self, request: IssueCouponRequest | ValidateCouponRequest) -> dict[str, Any]:
        user, activity, coupon_package = await self._get_base_data(
            request.user_id, request.activity_id, request.package_type.value
        )

        self._validate_activity_status(activity)
        self._validate_activity_time(activity)
        self._validate_user_eligibility(user, activity)
        await self._validate_not_claimed(request.user_id, activity.activity_id, coupon_package.package_id)
        await self._validate_stock(coupon_package)

        return {
            "user": user,
            "activity": activity,
            "coupon_package": coupon_package,
        }

    async def _get_base_data(
        self, user_id: str, activity_id: str, package_type: str
    ) -> tuple[User, Activity, CouponPackage]:
        user_stmt = select(User).where(User.user_id == user_id)
        user_result = await self.db.execute(user_stmt)
        user = user_result.scalar_one_or_none()
        if not user:
            raise CouponUserError(
                message=f"User {user_id} not found",
                error_key="user_not_found",
            )

        activity_stmt = select(Activity).where(Activity.activity_id == activity_id)
        activity_result = await self.db.execute(activity_stmt)
        activity = activity_result.scalar_one_or_none()
        if not activity:
            raise CouponActivityError(
                message=f"Activity {activity_id} not found",
                error_key="activity_not_found",
            )

        package_stmt = select(CouponPackage).where(
            and_(
                CouponPackage.activity_id == activity_id,
                CouponPackage.type == package_type,
            )
        )
        package_result = await self.db.execute(package_stmt)
        coupon_package = package_result.scalar_one_or_none()
        if not coupon_package:
            raise CouponActivityError(
                message=f"Coupon package not found for activity {activity_id} and type {package_type}",
                error_key="coupon_not_found",
            )

        return user, activity, coupon_package

    def _validate_activity_status(self, activity: Activity) -> None:
        if activity.status == ActivityStatus.DRAFT.value:
            raise CouponActivityError(
                message=f"Activity {activity.activity_id} is in draft status",
                error_key="activity_not_started",
            )
        if activity.status == ActivityStatus.PAUSED.value:
            raise CouponActivityError(
                message=f"Activity {activity.activity_id} is paused",
                error_key="activity_paused",
            )
        if activity.status == ActivityStatus.ENDED.value:
            raise CouponActivityError(
                message=f"Activity {activity.activity_id} has ended",
                error_key="activity_ended",
            )

    def _validate_activity_time(self, activity: Activity) -> None:
        now = datetime.now()
        if now < activity.start_time:
            raise CouponActivityError(
                message=f"Activity {activity.activity_id} not started yet",
                error_key="activity_not_started",
            )
        if now > activity.end_time:
            raise CouponActivityError(
                message=f"Activity {activity.activity_id} has ended",
                error_key="activity_ended",
            )

    def _validate_user_eligibility(self, user: User, activity: Activity) -> None:
        if activity.require_new_reader and not user.is_new_reader:
            raise CouponEligibilityError(
                message=f"User {user.user_id} is not a new reader",
                error_key="not_eligible_new_reader",
            )

        if user.member_level < activity.min_member_level:
            raise CouponEligibilityError(
                message=f"User {user.user_id} member level {user.member_level} "
                f"below required {activity.min_member_level}",
                error_key="not_eligible_member_level",
            )

        if activity.allowed_regions:
            allowed_regions = [r.strip() for r in activity.allowed_regions.split(",") if r.strip()]
            if allowed_regions and user.region not in allowed_regions:
                raise CouponEligibilityError(
                    message=f"User {user.user_id} region {user.region} not in allowed regions",
                    error_key="region_restricted",
                )

    async def _validate_not_claimed(self, user_id: str, activity_id: str, package_id: str) -> None:
        cache_key = f"coupon:claimed:{user_id}:{activity_id}:{package_id}"
        if self.redis:
            cached = await self.redis.get(cache_key)
            if cached:
                raise CouponAlreadyClaimedError(
                    message=f"User {user_id} has already claimed coupon for "
                    f"activity {activity_id} and package {package_id}"
                )

        stmt = select(UserCoupon).where(
            and_(
                UserCoupon.user_id == user_id,
                UserCoupon.activity_id == activity_id,
                UserCoupon.package_id == package_id,
                UserCoupon.status.in_([0, 1]),
            )
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            if self.redis:
                await self.redis.setex(cache_key, 86400, "1")
            raise CouponAlreadyClaimedError(
                message=f"User {user_id} has already claimed coupon for "
                f"activity {activity_id} and package {package_id}"
            )

    async def _validate_stock(self, coupon_package: CouponPackage) -> None:
        stock_key = f"coupon:stock:{coupon_package.package_id}"
        remaining = None

        if self.redis:
            remaining_str = await self.redis.get(stock_key)
            if remaining_str is not None:
                remaining = int(remaining_str)

        if remaining is None:
            remaining = coupon_package.total_quantity - coupon_package.claimed_quantity
            if self.redis:
                await self.redis.setex(stock_key, 300, str(remaining))

        if remaining <= 0:
            raise CouponStockError(
                message=f"Insufficient stock for package {coupon_package.package_id}"
            )
