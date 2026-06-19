import uuid
from datetime import datetime, timedelta
from typing import Any

import redis.asyncio as redis
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import ActivityStatus, CouponActivityError, CouponException, CouponStatus
from app.models import Activity, CouponPackage, CouponPackageSku, Partner, PartnerApiLog, UserBehaviorLog, UserCoupon
from app.schemas.admin import (
    BehaviorStatsRequest,
    CreateActivityRequest,
    CreateCouponPackageRequest,
    CreatePartnerRequest,
    GenerateCouponCodesRequest,
    ImportCouponCodesRequest,
    PartnerReportRequest,
    UpdateActivityStatusRequest,
    UpdatePartnerRequest,
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
            "claimed_unused": claimed,
            "issued": claimed + used,
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

    async def update_activity_status(self, request: UpdateActivityStatusRequest) -> dict[str, Any]:
        activity_result = await self.db.execute(
            select(Activity).where(Activity.activity_id == request.activity_id)
        )
        activity = activity_result.scalar_one_or_none()
        if not activity:
            raise CouponActivityError(
                message=f"Activity {request.activity_id} not found",
                error_key="activity_not_found",
            )

        action_status_map = {
            "online": (ActivityStatus.ONGOING, [ActivityStatus.DRAFT, ActivityStatus.PAUSED]),
            "pause": (ActivityStatus.PAUSED, [ActivityStatus.ONGOING]),
            "resume": (ActivityStatus.ONGOING, [ActivityStatus.PAUSED]),
            "end": (ActivityStatus.ENDED, [ActivityStatus.ONGOING, ActivityStatus.PAUSED, ActivityStatus.DRAFT]),
        }

        target_status, allowed_from = action_status_map[request.action]
        if activity.status not in [s.value for s in allowed_from]:
            current_label = {0: "草稿", 1: "进行中", 2: "暂停", 3: "已结束"}.get(activity.status, "未知")
            raise CouponActivityError(
                message=f"Cannot {request.action} activity in status {current_label}",
                error_key="invalid_status_transition",
            )

        activity.status = target_status.value
        await self.db.commit()
        await self.db.refresh(activity)

        return {
            "activity_id": activity.activity_id,
            "name": activity.name,
            "status": activity.status,
            "status_label": {0: "草稿", 1: "进行中", 2: "暂停", 3: "已结束"}.get(activity.status, "未知"),
            "start_time": activity.start_time.isoformat(),
            "end_time": activity.end_time.isoformat(),
        }

    async def get_stock_reconcile(self, activity_id: str, package_type: str | None = None) -> dict[str, Any]:
        activity_result = await self.db.execute(
            select(Activity).where(Activity.activity_id == activity_id)
        )
        if not activity_result.scalar_one_or_none():
            raise CouponActivityError(
                message=f"Activity {activity_id} not found",
                error_key="activity_not_found",
            )

        pkg_stmt = select(CouponPackage).where(CouponPackage.activity_id == activity_id)
        if package_type:
            pkg_stmt = pkg_stmt.where(CouponPackage.type == package_type)
        pkg_result = await self.db.execute(pkg_stmt)
        packages = pkg_result.scalars().all()

        reconcile_list = []
        for pkg in packages:
            sku_total = (await self.db.execute(
                select(func.count()).select_from(CouponPackageSku).where(
                    CouponPackageSku.package_id == pkg.package_id
                )
            )).scalar() or 0

            sku_available = (await self.db.execute(
                select(func.count()).select_from(CouponPackageSku).where(
                    and_(CouponPackageSku.package_id == pkg.package_id, CouponPackageSku.status == 0)
                )
            )).scalar() or 0

            sku_issued = (await self.db.execute(
                select(func.count()).select_from(CouponPackageSku).where(
                    and_(CouponPackageSku.package_id == pkg.package_id, CouponPackageSku.status.in_([1, 2]))
                )
            )).scalar() or 0

            sku_claimed_unused = (await self.db.execute(
                select(func.count()).select_from(CouponPackageSku).where(
                    and_(CouponPackageSku.package_id == pkg.package_id, CouponPackageSku.status == 1)
                )
            )).scalar() or 0

            sku_used = (await self.db.execute(
                select(func.count()).select_from(CouponPackageSku).where(
                    and_(CouponPackageSku.package_id == pkg.package_id, CouponPackageSku.status == 2)
                )
            )).scalar() or 0

            sku_expired = (await self.db.execute(
                select(func.count()).select_from(CouponPackageSku).where(
                    and_(CouponPackageSku.package_id == pkg.package_id, CouponPackageSku.status == 3)
                )
            )).scalar() or 0

            config_vs_sku_diff = pkg.total_quantity - sku_total
            issued_vs_sku_issued_diff = pkg.claimed_quantity - sku_issued

            reconcile_list.append({
                "package_id": pkg.package_id,
                "package_name": pkg.name,
                "package_type": pkg.type,
                "config_quantity": pkg.total_quantity,
                "sku_total": sku_total,
                "config_vs_sku_diff": config_vs_sku_diff,
                "available": sku_available,
                "sku_issued": sku_issued,
                "sku_claimed_unused": sku_claimed_unused,
                "claimed_quantity": pkg.claimed_quantity,
                "issued_vs_sku_issued_diff": issued_vs_sku_issued_diff,
                "sku_used": sku_used,
                "sku_expired": sku_expired,
                "has_discrepancy": config_vs_sku_diff != 0 or issued_vs_sku_issued_diff != 0,
            })

        return {
            "activity_id": activity_id,
            "packages": reconcile_list,
        }

    async def recalculate_stock(self, activity_id: str, package_type: str | None = None) -> dict[str, Any]:
        activity_result = await self.db.execute(
            select(Activity).where(Activity.activity_id == activity_id)
        )
        if not activity_result.scalar_one_or_none():
            raise CouponActivityError(
                message=f"Activity {activity_id} not found",
                error_key="activity_not_found",
            )

        pkg_stmt = select(CouponPackage).where(CouponPackage.activity_id == activity_id)
        if package_type:
            pkg_stmt = pkg_stmt.where(CouponPackage.type == package_type)
        pkg_result = await self.db.execute(pkg_stmt)
        packages = pkg_result.scalars().all()

        fixed_list = []
        for pkg in packages:
            sku_total = (await self.db.execute(
                select(func.count()).select_from(CouponPackageSku).where(
                    CouponPackageSku.package_id == pkg.package_id
                )
            )).scalar() or 0

            sku_issued = (await self.db.execute(
                select(func.count()).select_from(CouponPackageSku).where(
                    and_(CouponPackageSku.package_id == pkg.package_id, CouponPackageSku.status.in_([1, 2]))
                )
            )).scalar() or 0

            old_total = pkg.total_quantity
            old_claimed = pkg.claimed_quantity

            await self.db.execute(
                update(CouponPackage)
                .where(CouponPackage.id == pkg.id)
                .values(total_quantity=sku_total, claimed_quantity=sku_issued)
            )

            if self.redis:
                stock_key = f"coupon:stock:{pkg.package_id}"
                sku_available = (await self.db.execute(
                    select(func.count()).select_from(CouponPackageSku).where(
                        and_(CouponPackageSku.package_id == pkg.package_id, CouponPackageSku.status == 0)
                    )
                )).scalar() or 0
                await self.redis.setex(stock_key, 300, str(sku_available))

            fixed_list.append({
                "package_id": pkg.package_id,
                "package_name": pkg.name,
                "total_quantity": {"before": old_total, "after": sku_total},
                "issued_quantity": {"before": old_claimed, "after": sku_issued},
                "was_correct": old_total == sku_total and old_claimed == sku_issued,
            })

        await self.db.commit()

        return {
            "activity_id": activity_id,
            "recalculated_packages": fixed_list,
        }

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
            claim_count = counts["click"]
            use_count = counts["use"]
            impression_count = counts["impression"]
            claim_rate = round(claim_count / impression_count * 100, 2) if impression_count > 0 else 0.0
            use_rate = round(use_count / claim_count * 100, 2) if claim_count > 0 else 0.0
            by_scene.append({
                "trigger_scene": trigger_scene,
                "impression_count": impression_count,
                "click_count": claim_count,
                "use_count": use_count,
                "claim_rate": claim_rate,
                "use_rate": use_rate,
            })

        total_impression = total_counts["impression"]
        total_click = total_counts["click"]
        total_use = total_counts["use"]
        total_claim_rate = round(total_click / total_impression * 100, 2) if total_impression > 0 else 0.0
        total_use_rate = round(total_use / total_click * 100, 2) if total_click > 0 else 0.0

        daily_stmt = select(
            func.date(UserBehaviorLog.created_at).label("log_date"),
            UserBehaviorLog.behavior_type,
            func.count(UserBehaviorLog.log_id)
        ).where(and_(*conditions)).group_by(
            func.date(UserBehaviorLog.created_at),
            UserBehaviorLog.behavior_type
        )
        daily_result = await self.db.execute(daily_stmt)
        daily_data: dict[str, dict[str, int]] = {}
        for row in daily_result.all():
            log_date, behavior_type, count = row
            date_str = str(log_date)
            if date_str not in daily_data:
                daily_data[date_str] = {"impression": 0, "click": 0, "use": 0}
            if behavior_type in daily_data[date_str]:
                daily_data[date_str][behavior_type] = count

        daily_trend = []
        for date_str in sorted(daily_data.keys()):
            d = daily_data[date_str]
            d_impression = d["impression"]
            d_click = d["click"]
            d_use = d["use"]
            d_claim_rate = round(d_click / d_impression * 100, 2) if d_impression > 0 else 0.0
            d_use_rate = round(d_use / d_click * 100, 2) if d_click > 0 else 0.0
            daily_trend.append({
                "date": date_str,
                "impression": d_impression,
                "click": d_click,
                "use": d_use,
                "claim_rate": d_claim_rate,
                "use_rate": d_use_rate,
            })

        return {
            "activity_id": request.activity_id,
            "package_type": request.package_type.value if request.package_type else None,
            "start_time": request.start_time.isoformat() if request.start_time else None,
            "end_time": request.end_time.isoformat() if request.end_time else None,
            "total": {
                "impression": total_impression,
                "click": total_click,
                "use": total_use,
                "claim_rate": total_claim_rate,
                "use_rate": total_use_rate,
            },
            "by_scene": by_scene,
            "daily_trend": daily_trend,
        }

    def _generate_single_code(self, prefix: str = "") -> str:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_part = uuid.uuid4().hex[:12].upper()
        return f"{prefix}{timestamp}{random_part}"

    async def create_partner(self, request: CreatePartnerRequest) -> dict[str, Any]:
        existing = await self.db.execute(
            select(Partner).where(Partner.partner_id == request.partner_id)
        )
        if existing.scalar_one_or_none():
            raise CouponActivityError(
                message=f"Partner {request.partner_id} already exists",
                error_key="partner_already_exists",
            )

        sign_key = uuid.uuid4().hex

        partner = Partner(
            partner_id=request.partner_id,
            name=request.name,
            sign_key=sign_key,
            allowed_activities=request.allowed_activities,
            allowed_package_types=request.allowed_package_types,
            daily_limit=request.daily_limit,
            status=1,
        )

        self.db.add(partner)
        await self.db.commit()
        await self.db.refresh(partner)

        return {
            "partner_id": partner.partner_id,
            "name": partner.name,
            "sign_key": partner.sign_key,
            "allowed_activities": partner.allowed_activities,
            "allowed_package_types": partner.allowed_package_types,
            "daily_limit": partner.daily_limit,
            "status": partner.status,
            "created_at": partner.created_at.isoformat(),
        }

    async def update_partner(self, request: UpdatePartnerRequest) -> dict[str, Any]:
        result = await self.db.execute(
            select(Partner).where(Partner.partner_id == request.partner_id)
        )
        partner = result.scalar_one_or_none()
        if not partner:
            raise CouponActivityError(
                message=f"Partner {request.partner_id} not found",
                error_key="partner_not_found",
            )

        if request.name is not None:
            partner.name = request.name
        if request.allowed_activities is not None:
            partner.allowed_activities = request.allowed_activities
        if request.allowed_package_types is not None:
            partner.allowed_package_types = request.allowed_package_types
        if request.daily_limit is not None:
            partner.daily_limit = request.daily_limit
        if request.status is not None:
            partner.status = request.status

        await self.db.commit()
        await self.db.refresh(partner)

        return {
            "partner_id": partner.partner_id,
            "name": partner.name,
            "sign_key": partner.sign_key,
            "allowed_activities": partner.allowed_activities,
            "allowed_package_types": partner.allowed_package_types,
            "daily_limit": partner.daily_limit,
            "status": partner.status,
        }

    async def list_partners(self, skip: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        stmt = select(Partner).order_by(Partner.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        partners = result.scalars().all()

        return [
            {
                "partner_id": p.partner_id,
                "name": p.name,
                "allowed_activities": p.allowed_activities,
                "allowed_package_types": p.allowed_package_types,
                "daily_limit": p.daily_limit,
                "status": p.status,
                "status_label": "启用" if p.status == 1 else "禁用",
                "created_at": p.created_at.isoformat(),
            }
            for p in partners
        ]

    async def reset_partner_sign_key(self, partner_id: str) -> dict[str, Any]:
        result = await self.db.execute(
            select(Partner).where(Partner.partner_id == partner_id)
        )
        partner = result.scalar_one_or_none()
        if not partner:
            raise CouponActivityError(
                message=f"Partner {partner_id} not found",
                error_key="partner_not_found",
            )

        new_key = uuid.uuid4().hex
        partner.sign_key = new_key
        await self.db.commit()
        await self.db.refresh(partner)

        return {
            "partner_id": partner.partner_id,
            "sign_key": partner.sign_key,
        }

    async def get_partner_report(self, request: PartnerReportRequest) -> dict[str, Any]:
        result = await self.db.execute(
            select(Partner).where(Partner.partner_id == request.partner_id)
        )
        if not result.scalar_one_or_none():
            raise CouponActivityError(
                message=f"Partner {request.partner_id} not found",
                error_key="partner_not_found",
            )

        conditions = [PartnerApiLog.partner_id == request.partner_id]
        if request.start_time:
            conditions.append(PartnerApiLog.request_time >= request.start_time)
        if request.end_time:
            conditions.append(PartnerApiLog.request_time <= request.end_time)

        daily_stmt = select(
            func.date(PartnerApiLog.request_time).label("log_date"),
            PartnerApiLog.success,
            PartnerApiLog.is_idempotent_hit,
            PartnerApiLog.api_path,
            PartnerApiLog.error_key,
            func.count(PartnerApiLog.log_id)
        ).where(and_(*conditions)).group_by(
            func.date(PartnerApiLog.request_time),
            PartnerApiLog.success,
            PartnerApiLog.is_idempotent_hit,
            PartnerApiLog.api_path,
            PartnerApiLog.error_key,
        )

        daily_result = await self.db.execute(daily_stmt)
        raw_data: dict[str, dict[str, Any]] = {}

        for row in daily_result.all():
            log_date, success, is_idempotent_hit, api_path, error_key, count = row
            date_str = str(log_date)
            if date_str not in raw_data:
                raw_data[date_str] = {
                    "total_requests": 0,
                    "success_count": 0,
                    "fail_count": 0,
                    "issue_count": 0,
                    "idempotent_hit_count": 0,
                    "error_distribution": {},
                }
            d = raw_data[date_str]
            d["total_requests"] += count
            if success == 1:
                d["success_count"] += count
                if api_path == "/api/v1/coupon/issue":
                    d["issue_count"] += count
            else:
                d["fail_count"] += count
                ek = error_key or "unknown"
                d["error_distribution"][ek] = d["error_distribution"].get(ek, 0) + count
            if is_idempotent_hit == 1:
                d["idempotent_hit_count"] += count

        daily_list = []
        for date_str in sorted(raw_data.keys()):
            d = raw_data[date_str]
            daily_list.append({
                "date": date_str,
                "total_requests": d["total_requests"],
                "success_count": d["success_count"],
                "fail_count": d["fail_count"],
                "error_distribution": d["error_distribution"],
                "issue_count": d["issue_count"],
                "idempotent_hit_count": d["idempotent_hit_count"],
            })

        total_summary = {
            "total_requests": sum(d["total_requests"] for d in raw_data.values()),
            "success_count": sum(d["success_count"] for d in raw_data.values()),
            "fail_count": sum(d["fail_count"] for d in raw_data.values()),
            "issue_count": sum(d["issue_count"] for d in raw_data.values()),
            "idempotent_hit_count": sum(d["idempotent_hit_count"] for d in raw_data.values()),
        }

        return {
            "partner_id": request.partner_id,
            "start_time": request.start_time.isoformat() if request.start_time else None,
            "end_time": request.end_time.isoformat() if request.end_time else None,
            "summary": total_summary,
            "daily": daily_list,
        }
