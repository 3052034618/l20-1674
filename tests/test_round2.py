import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import (
    ActivityStatus,
    BehaviorType,
    CouponType,
    MemberLevel,
    TriggerScene,
)
from app.models import (
    Activity,
    CouponPackage,
    CouponPackageSku,
    User,
    UserBehaviorLog,
    UserCoupon,
)
from app.schemas import (
    BehaviorStatsRequest,
    IssueCouponRequest,
    UpdateActivityStatusRequest,
)
from app.services import AdminService, CouponService, ValidationService


@pytest.mark.asyncio
async def test_idempotent_db_fallback_no_redis(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_user: User,
    test_coupon_skus: list,
) -> None:
    request = IssueCouponRequest(
        user_id=test_user.user_id,
        activity_id=test_activity.activity_id,
        package_type=CouponType.NEW_READER,
        trigger_scene=TriggerScene.MEMBER_CENTER,
        partner_id="test_partner",
        biz_serial_no="biz_no_redis_001",
    )

    service = CouponService(db_session, mock_redis)
    result1 = await service.issue_coupon(request)

    mock_redis.hgetall = AsyncMock(return_value={})
    mock_redis.get = AsyncMock(return_value=None)

    result2 = await service.issue_coupon(request)

    assert result1.record_id == result2.record_id
    assert result1.coupon_code == result2.coupon_code
    assert result1.valid_start_time == result2.valid_start_time
    assert result1.valid_end_time == result2.valid_end_time


@pytest.mark.asyncio
async def test_idempotent_db_fallback_redis_down(
    db_session: AsyncSession,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_user: User,
    test_coupon_skus: list,
) -> None:
    request = IssueCouponRequest(
        user_id=test_user.user_id,
        activity_id=test_activity.activity_id,
        package_type=CouponType.NEW_READER,
        trigger_scene=TriggerScene.MEMBER_CENTER,
        partner_id="partner_redis_down",
        biz_serial_no="biz_redis_down_001",
    )

    service_with_redis = CouponService(db_session, None)
    result1 = await service_with_redis.issue_coupon(request)

    service_no_redis = CouponService(db_session, None)
    result2 = await service_no_redis.issue_coupon(request)

    assert result1.record_id == result2.record_id
    assert result1.coupon_code == result2.coupon_code
    assert result1.package_name == result2.package_name


@pytest.mark.asyncio
async def test_activity_status_online(
    db_session: AsyncSession,
    mock_redis: MagicMock,
) -> None:
    now = datetime.now()
    activity = Activity(
        activity_id=f"act_status_{uuid.uuid4().hex[:8]}",
        name="状态测试活动",
        description="",
        status=ActivityStatus.DRAFT.value,
        start_time=now,
        end_time=now + timedelta(days=30),
        allowed_regions="",
        min_member_level=MemberLevel.FREE.value,
        require_new_reader=0,
    )
    db_session.add(activity)
    await db_session.commit()
    await db_session.refresh(activity)

    request = UpdateActivityStatusRequest(
        activity_id=activity.activity_id,
        action="online",
    )
    service = AdminService(db_session, mock_redis)
    result = await service.update_activity_status(request)

    assert result["status"] == ActivityStatus.ONGOING.value
    assert result["status_label"] == "进行中"


@pytest.mark.asyncio
async def test_activity_status_pause_and_resume(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
) -> None:
    service = AdminService(db_session, mock_redis)

    pause_request = UpdateActivityStatusRequest(
        activity_id=test_activity.activity_id,
        action="pause",
    )
    result = await service.update_activity_status(pause_request)
    assert result["status"] == ActivityStatus.PAUSED.value

    resume_request = UpdateActivityStatusRequest(
        activity_id=test_activity.activity_id,
        action="resume",
    )
    result = await service.update_activity_status(resume_request)
    assert result["status"] == ActivityStatus.ONGOING.value


@pytest.mark.asyncio
async def test_activity_status_end(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
) -> None:
    request = UpdateActivityStatusRequest(
        activity_id=test_activity.activity_id,
        action="end",
    )
    service = AdminService(db_session, mock_redis)
    result = await service.update_activity_status(request)

    assert result["status"] == ActivityStatus.ENDED.value


@pytest.mark.asyncio
async def test_activity_status_invalid_transition(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
) -> None:
    test_activity.status = ActivityStatus.ENDED.value
    await db_session.commit()

    request = UpdateActivityStatusRequest(
        activity_id=test_activity.activity_id,
        action="online",
    )
    service = AdminService(db_session, mock_redis)

    from app.core import CouponActivityError
    with pytest.raises(CouponActivityError):
        await service.update_activity_status(request)


@pytest.mark.asyncio
async def test_paused_activity_blocks_issue(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_user: User,
    test_coupon_skus: list,
) -> None:
    status_request = UpdateActivityStatusRequest(
        activity_id=test_activity.activity_id,
        action="pause",
    )
    admin_service = AdminService(db_session, mock_redis)
    await admin_service.update_activity_status(status_request)

    from app.core import CouponActivityError
    request = IssueCouponRequest(
        user_id=test_user.user_id,
        activity_id=test_activity.activity_id,
        package_type=CouponType.NEW_READER,
        trigger_scene=TriggerScene.MEMBER_CENTER,
    )
    service = CouponService(db_session, mock_redis)
    with pytest.raises(CouponActivityError):
        await service.issue_coupon(request)


@pytest.mark.asyncio
async def test_stock_reconcile(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_coupon_skus: list,
) -> None:
    test_coupon_package.total_quantity = 999
    await db_session.commit()

    service = AdminService(db_session, mock_redis)
    result = await service.get_stock_reconcile(test_activity.activity_id)

    assert len(result["packages"]) >= 1
    pkg = result["packages"][0]
    assert pkg["config_quantity"] == 999
    assert pkg["sku_total"] == len(test_coupon_skus)
    assert pkg["config_vs_sku_diff"] == 999 - len(test_coupon_skus)
    assert pkg["has_discrepancy"] is True


@pytest.mark.asyncio
async def test_stock_reconcile_no_discrepancy(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_coupon_skus: list,
) -> None:
    test_coupon_package.total_quantity = len(test_coupon_skus)
    test_coupon_package.claimed_quantity = 0
    await db_session.commit()

    service = AdminService(db_session, mock_redis)
    result = await service.get_stock_reconcile(test_activity.activity_id)

    pkg = result["packages"][0]
    assert pkg["config_vs_sku_diff"] == 0
    assert pkg["issued_vs_sku_issued_diff"] == 0
    assert pkg["has_discrepancy"] is False


@pytest.mark.asyncio
async def test_stock_recalculate(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_coupon_skus: list,
) -> None:
    test_coupon_package.total_quantity = 999
    test_coupon_package.claimed_quantity = 50
    await db_session.commit()

    service = AdminService(db_session, mock_redis)
    result = await service.recalculate_stock(test_activity.activity_id)

    pkg = result["recalculated_packages"][0]
    assert pkg["total_quantity"]["before"] == 999
    assert pkg["total_quantity"]["after"] == len(test_coupon_skus)
    assert pkg["issued_quantity"]["before"] == 50
    assert pkg["issued_quantity"]["after"] == 0
    assert pkg["was_correct"] is False

    await db_session.refresh(test_coupon_package)
    assert test_coupon_package.total_quantity == len(test_coupon_skus)
    assert test_coupon_package.claimed_quantity == 0


@pytest.mark.asyncio
async def test_behavior_stats_with_rates(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_user: User,
) -> None:
    log_data = [
        (BehaviorType.IMPRESSION, TriggerScene.MEMBER_CENTER),
        (BehaviorType.IMPRESSION, TriggerScene.MEMBER_CENTER),
        (BehaviorType.IMPRESSION, TriggerScene.MEMBER_CENTER),
        (BehaviorType.CLICK, TriggerScene.MEMBER_CENTER),
        (BehaviorType.USE, TriggerScene.MEMBER_CENTER),
        (BehaviorType.IMPRESSION, TriggerScene.TASK_CENTER),
        (BehaviorType.CLICK, TriggerScene.TASK_CENTER),
    ]

    for behavior_type, trigger_scene in log_data:
        log = UserBehaviorLog(
            log_id=f"log_{uuid.uuid4().hex}",
            user_id=test_user.user_id,
            activity_id=test_activity.activity_id,
            package_id=test_coupon_package.package_id,
            behavior_type=behavior_type.value,
            trigger_scene=trigger_scene.value,
            extra={},
        )
        db_session.add(log)
    await db_session.commit()

    request = BehaviorStatsRequest(
        activity_id=test_activity.activity_id,
    )

    service = AdminService(db_session, mock_redis)
    result = await service.get_behavior_stats(request)

    assert result["total"]["impression"] == 4
    assert result["total"]["click"] == 2
    assert result["total"]["use"] == 1
    assert result["total"]["claim_rate"] == 50.0
    assert result["total"]["use_rate"] == 50.0

    scene_stats = {s["trigger_scene"]: s for s in result["by_scene"]}
    member_center = scene_stats[TriggerScene.MEMBER_CENTER.value]
    assert member_center["claim_rate"] == 33.33
    assert member_center["use_rate"] == 100.0

    task_center = scene_stats[TriggerScene.TASK_CENTER.value]
    assert task_center["claim_rate"] == 100.0
    assert task_center["use_rate"] == 0.0


@pytest.mark.asyncio
async def test_behavior_stats_daily_trend(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_user: User,
) -> None:
    for behavior_type in [BehaviorType.IMPRESSION, BehaviorType.CLICK, BehaviorType.USE]:
        log = UserBehaviorLog(
            log_id=f"log_{uuid.uuid4().hex}",
            user_id=test_user.user_id,
            activity_id=test_activity.activity_id,
            package_id=test_coupon_package.package_id,
            behavior_type=behavior_type.value,
            trigger_scene=TriggerScene.MEMBER_CENTER.value,
            extra={},
        )
        db_session.add(log)
    await db_session.commit()

    request = BehaviorStatsRequest(
        activity_id=test_activity.activity_id,
    )

    service = AdminService(db_session, mock_redis)
    result = await service.get_behavior_stats(request)

    assert len(result["daily_trend"]) >= 1
    today = result["daily_trend"][-1]
    assert "date" in today
    assert today["impression"] >= 1
    assert today["click"] >= 1
    assert today["use"] >= 1
    assert "claim_rate" in today
    assert "use_rate" in today
