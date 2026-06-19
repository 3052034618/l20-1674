import uuid
from datetime import datetime, timedelta
from typing import Any

import redis.asyncio as redis
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import CouponActivityError, CouponException, CouponStatus
from app.models import Activity, CouponPackage, CouponPackageSku, UserBehaviorLog, UserCoupon
from app.schemas.admin import (
    BehaviorStatsRequest,
    CreateActivityRequest,
    CreateCouponPackageRequest,
    GenerateCouponCodesRequest,
    ImportCouponCodesRequest,
)


class AdminService:
    def __init__(self, db: AsyncSession, redis_client: redis.Redis | None = None):
        self.db = db
        self.redis = redis_client

    async def create_activity(self, request: CreateActivityRequest) -> dict[str, Any]:
        existing = await self.db.execute(
            select(Activity).where(Activity.activity_id == request.activity_id)
        )
        if existing.scalar_one_or_none():
            raise CouponActivityError(
                message=f"Activity {request.activity_id} already exists",
                error_key="activity_already_exists",
            )

        activity = Activity(
            activity_id=request.activity_id,
            name=request.name,
            description=request.description,
            status=request.status.value,
            start_time=request.start_time,
            end_time=request.end_time,
            allowed_regions=request.allowed_regions,
            min_member_level=request.min_member_level.value,
            require_new_reader=1 if request.require_new_reader else 0,
        )

        self.db.add(activity)
        await self.db.commit()
        await self.db.refresh(activity)

        return {
            "activity_id": activity.activity_id,
            "name": activity.name,
            "description": activity.description,
            "status": activity.status,
            "start_time": activity.start_time.isoformat(),
            "end_time": activity.end_time.isoformat(),
            "allowed_regions": activity.allowed_regions,
            "min_member_level": activity.min_member_level,
            "require_new_reader": activity.require_new_reader == 1,
        }

    async def create_coupon_package(self, request: CreateCouponPackageRequest) -> dict[str, Any]:
        activity = await self.db.execute(
            select(Activity).where(Activity.activity_id == request.activity_id)
        )
        if not activity.scalar_one_or_none():
            raise CouponActivityError(
                message=f"Activity {request.activity_id} not found",
                error_key="activity_not_found",
            )

        existing = await self.db.execute(
            select(CouponPackage).where(CouponPackage.package_id == request.package_id)
        )
        if existing.scalar_one_or_none():
            raise CouponActivityError(
                message=f"Coupon package {request.package_id} already exists",
                error_key="coupon_package_already_exists",
            )

        existing_type = await self.db.execute(
            select(CouponPackage).where(
                and_(
                    CouponPackage.activity_id == request.activity_id,
                    CouponPackage.type == request.type.value,
                )
            )
        )
        if existing_type.scalar_one_or_none():
            raise CouponActivityError(
                message=f"Coupon type {request.type.value} already exists for activity {request.activity_id}",
                error_key="coupon_type_already_exists",
            )

        package = CouponPackage(
            package_id=request.package_id,
            activity_id=request.activity_id,
            name=request.name,
            type=request.type.value,
            display_text=request.display_text,
            valid_days=request.valid_days,
            applicable_comics=request.applicable_comics,
            comic_categories=request.comic_categories,
            discount_value=request.discount_value,
            discount_type=request.discount_type,
            total_quantity=0,
            claimed_quantity=0,
        )

        self.db.add(package)
        await self.db.commit()
        await self.db.refresh(package)

        return {
            "package_id": package.package_id,
            "activity_id": package.activity_id,
            "name": package.name,
            "type": package.type,
            "display_text": package.display_text,
            "valid_days": package.valid_days,
            "applicable_comics": package.applicable_comics,
            "total_quantity": package.total_quantity,
            "claimed_quantity": package.claimed_quantity,
        }

    async def generate_coupon_codes(self, request: GenerateCouponCodesRequest) -> dict[str, Any]:
        package = await self.db.execute(
            select(CouponPackage).where(CouponPackage.package_id == request.package_id)
        )
        package_obj = package.scalar_one_or_none()
        if not package_obj:
            raise CouponActivityError(
                message=f"Coupon package {request.package_id} not found",
                error_key="coupon_not_found",
            )

        expire_time = datetime.now() + timedelta(days=request.expire_days)
        generated = 0
        codes = []

        for i in range(request.quantity):
            code = self._generate_single_code(request.prefix)
            sku = CouponPackageSku(
                sku_id=f"sku_{uuid.uuid4().hex}",
                package_id=request.package_id,
                coupon_code=code,
                status=0,
                expire_time=expire_time,
            )
            self.db.add(sku)
            codes.append(code)
            generated += 1

        package_obj.total_quantity += generated
        await self.db.commit()

        stock_key = f"coupon:stock:{request.package_id}"
        if self.redis:
            await self.redis.delete(stock_key)

        return {
            "package_id": request.package_id,
            "generated_count": generated,
            "expire_time": expire_time.isoformat(),
            "sample_codes": codes[:5],
        }

    async def import_coupon_codes(self, request: ImportCouponCodesRequest) -> dict[str, Any]:
        package = await self.db.execute(
            select(CouponPackage).where(CouponPackage.package_id == request.package_id)
        )
        package_obj = package.scalar_one_or_none()
        if not package_obj:
            raise CouponActivityError(
                message=f"Coupon package {request.package_id} not found",
                error_key="coupon_not_found",
            )

        expire_time = datetime.now() + timedelta(days=request.expire_days)
        imported = 0
        duplicates = 0
        failed_codes = []

        for code in request.coupon_codes:
            existing = await self.db.execute(
                select(CouponPackageSku).where(CouponPackageSku.coupon_code == code)
            )
            if existing.scalar_one_or_none():
                duplicates += 1
                failed_codes.append(code)
                continue

            try:
                sku = CouponPackageSku(
                    sku_id=f"sku_{uuid.uuid4().hex}",
                    package_id=request.package_id,
                    coupon_code=code,
                    status=0,
                    expire_time=expire_time,
                )
                self.db.add(sku)
                imported += 1
            except Exception:
                failed_codes.append(code)

        package_obj.total_quantity += imported
        await self.db.commit()

        stock_key = f"coupon:stock:{request.package_id}"
        if self.redis:
            await self.redis.delete(stock_key)

        return {
            "package_id": request.package_id,
            "imported_count": imported,
            "duplicate_count": duplicates,
            "failed_count": len(failed_codes),
            "expire_time": expire_time.isoformat(),
            "failed_codes": failed_codes[:10],
        }

    async def get_package_stats(self, package_id: str) -> dict[str, Any]:
        package = await self.db.execute(
            select(CouponPackage).where(CouponPackage.package_id == package_id)
        )
        package_obj = package.scalar_one_or_none()
        if not package_obj:
            raise CouponActivityError(
                message=f"Coupon package {package_id} not found",
                error_key="coupon_not_found",
            )

        available_stmt = select(func.count()).select_from(CouponPackageSku).where(
            and_(
                CouponPackageSku.package_id == package_id,
                CouponPackageSku.status == 0,
            )
        )
        available = (await self.db.execute(available_stmt)).scalar() or 0

        claimed_stmt = select(func.count()).select_from(CouponPackageSku).where(
            and_(
                CouponPackageSku.package_id == package_id,
                CouponPackageSku.status == 1,
            )
        )
        claimed = (await self.db.execute(claimed_stmt)).scalar() or 0

        used_stmt = select(func.count()).select_from(CouponPackageSku).where(
            and_(
                CouponPackageSku.package_id == package_id,
                CouponPackageSku.status == 2,
            )
        )
        used = (await self.db.execute(used_stmt)).scalar() or 0

        return {
            "package_id": package_id,
            "package_name": package_obj.name,
            "total_quantity": package_obj.total_quantity,
            "available": available,
            "claimed": claimed,
            "used": used,
            "claimed_quantity": package_obj.claimed_quantity,
        }

    async def list_activities(self, skip: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        stmt = select(Activity).order_by(Activity.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        activities = result.scalars().all()

        return [
            {
                "activity_id": a.activity_id,
                "name": a.name,
                "description": a.description,
                "status": a.status,
                "start_time": a.start_time.isoformat(),
                "end_time": a.end_time.isoformat(),
                "allowed_regions": a.allowed_regions,
                "min_member_level": a.min_member_level,
                "require_new_reader": a.require_new_reader == 1,
                "created_at": a.created_at.isoformat(),
            }
            for a in activities
        ]

    async def list_packages(self, activity_id: str | None = None, skip: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        stmt = select(CouponPackage)
        if activity_id:
            stmt = stmt.where(CouponPackage.activity_id == activity_id)
        stmt = stmt.order_by(CouponPackage.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        packages = result.scalars().all()

        result_list = []
        for p in packages:
            available_stmt = select(func.count()).select_from(CouponPackageSku).where(
                and_(
                    CouponPackageSku.package_id == p.package_id,
                    CouponPackageSku.status == 0,
                )
            )
            available = (await self.db.execute(available_stmt)).scalar() or 0

            result_list.append({
                "package_id": p.package_id,
                "activity_id": p.activity_id,
                "name": p.name,
                "type": p.type,
                "display_text": p.display_text,
                "valid_days": p.valid_days,
                "total_quantity": p.total_quantity,
                "claimed_quantity": p.claimed_quantity,
                "available": available,
                "created_at": p.created_at.isoformat(),
            })

        return result_list

    async def get_behavior_stats(self, request: BehaviorStatsRequest) -> dict[str, Any]:
        activity = await self.db.execute(
            select(Activity).where(Activity.activity_id == request.activity_id)
        )
        if not activity.scalar_one_or_none():
            raise CouponActivityError(
                message=f"Activity {request.activity_id} not found",
                error_key="activity_not_found",
            )

        package_ids = None
        if request.package_type:
            stmt = select(CouponPackage.package_id).where(
                and_(
                    CouponPackage.activity_id == request.activity_id,
                    CouponPackage.type == request.package_type.value,
                )
            )
            result = await self.db.execute(stmt)
            package_ids = [row[0] for row in result.all()]
            if not package_ids:
                return {
                    "activity_id": request.activity_id,
                    "package_type": request.package_type.value if request.package_type else None,
                    "total": {
                        "impression": 0,
                        "click": 0,
                        "use": 0,
                    },
                    "by_scene": [],
                }

        conditions = [UserBehaviorLog.activity_id == request.activity_id]
        if package_ids:
            conditions.append(UserBehaviorLog.package_id.in_(package_ids))
        if request.start_time:
            conditions.append(UserBehaviorLog.created_at >= request.start_time)
        if request.end_time:
            conditions.append(UserBehaviorLog.created_at <= request.end_time)

        total_stmt = select(
            UserBehaviorLog.behavior_type,
            func.count(UserBehaviorLog.log_id)
        ).where(and_(*conditions)).group_by(UserBehaviorLog.behavior_type)

        total_result = await self.db.execute(total_stmt)
        total_counts = {"impression": 0, "click": 0, "use": 0}
        for row in total_result.all():
            behavior_type, count = row
            if behavior_type in total_counts:
                total_counts[behavior_type] = count

        scene_stmt = select(
            UserBehaviorLog.trigger_scene,
            UserBehaviorLog.behavior_type,
            func.count(UserBehaviorLog.log_id)
        ).where(and_(*conditions)).group_by(
            UserBehaviorLog.trigger_scene,
            UserBehaviorLog.behavior_type
        )

        scene_result = await self.db.execute(scene_stmt)
        scene_data: dict[str, dict[str, int]] = {}
        for row in scene_result.all():
            trigger_scene, behavior_type, count = row
            if trigger_scene not in scene_data:
                scene_data[trigger_scene] = {"impression": 0, "click": 0, "use": 0}
            if behavior_type in scene_data[trigger_scene]:
                scene_data[trigger_scene][behavior_type] = count

        by_scene = []
        for trigger_scene, counts in scene_data.items():
            by_scene.append({
                "trigger_scene": trigger_scene,
                "impression_count": counts["impression"],
                "click_count": counts["click"],
                "use_count": counts["use"],
            })

        return {
            "activity_id": request.activity_id,
            "package_type": request.package_type.value if request.package_type else None,
            "start_time": request.start_time.isoformat() if request.start_time else None,
            "end_time": request.end_time.isoformat() if request.end_time else None,
            "total": total_counts,
            "by_scene": by_scene,
        }

    def _generate_single_code(self, prefix: str = "") -> str:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_part = uuid.uuid4().hex[:12].upper()
        return f"{prefix}{timestamp}{random_part}"
