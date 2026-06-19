from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, MagicMock

from app.core import (
    CouponAlreadyClaimedError,
    CouponType,
    TriggerScene,
    BehaviorType,
    CouponStatus,
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
    CouponCallbackRequest,
    IssueCouponRequest,
    ValidateCouponRequest,
)
from app.services import CouponService


@pytest.mark.asyncio
async def test_issue_coupon_success(
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
        request_id="test_req_001",
    )

    service = CouponService(db_session, mock_redis)
    result = await service.issue_coupon(request)

    assert result.record_id.startswith("uc_")
    assert result.package_id == test_coupon_package.package_id
    assert result.display_text == test_coupon_package.display_text
    assert len(result.applicable_comics) == 3
    assert result.applicable_comics == ["1001", "1002", "1003"]

    stmt = select(UserCoupon).where(UserCoupon.user_id == test_user.user_id)
    db_result = await db_session.execute(stmt)
    user_coupon = db_result.scalar_one()
    assert user_coupon.status == CouponStatus.UNUSED.value
    assert user_coupon.trigger_scene == TriggerScene.MEMBER_CENTER.value

    sku_stmt = select(CouponPackageSku).where(CouponPackageSku.coupon_code == result.coupon_code)
    sku_result = await db_session.execute(sku_stmt)
    sku = sku_result.scalar_one()
    assert sku.status == 1
    assert sku.user_id == test_user.user_id


@pytest.mark.asyncio
async def test_issue_coupon_idempotent(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_user: User,
    test_coupon_skus: list,
) -> None:
    request_id = "test_req_idempotent_001"
    request = IssueCouponRequest(
        user_id=test_user.user_id,
        activity_id=test_activity.activity_id,
        package_type=CouponType.NEW_READER,
        trigger_scene=TriggerScene.MEMBER_CENTER,
        request_id=request_id,
    )

    service = CouponService(db_session, mock_redis)
    result1 = await service.issue_coupon(request)

    mock_redis.hgetall = AsyncMock(return_value={
        "record_id": result1.record_id,
        "coupon_code": result1.coupon_code,
        "package_id": result1.package_id,
        "package_name": result1.package_name,
        "display_text": result1.display_text,
        "valid_start_time": result1.valid_start_time.isoformat(),
        "valid_end_time": result1.valid_end_time.isoformat(),
        "applicable_comics": ",".join(result1.applicable_comics),
    })

    result2 = await service.issue_coupon(request)

    assert result1.record_id == result2.record_id
    assert result1.coupon_code == result2.coupon_code


@pytest.mark.asyncio
async def test_issue_coupon_already_claimed(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_user: User,
    test_coupon_skus: list,
) -> None:
    user_coupon = UserCoupon(
        record_id="test_claimed_002",
        user_id=test_user.user_id,
        activity_id=test_activity.activity_id,
        package_id=test_coupon_package.package_id,
        sku_id=test_coupon_skus[0].sku_id,
        coupon_code=test_coupon_skus[0].coupon_code,
        status=0,
        trigger_scene=TriggerScene.MEMBER_CENTER.value,
        valid_start_time=datetime.now(),
        valid_end_time=datetime.now() + timedelta(days=30),
        applicable_comics="1001,1002",
        display_text="测试",
    )
    db_session.add(user_coupon)
    await db_session.commit()

    request = IssueCouponRequest(
        user_id=test_user.user_id,
        activity_id=test_activity.activity_id,
        package_type=CouponType.NEW_READER,
        trigger_scene=TriggerScene.MEMBER_CENTER,
    )

    service = CouponService(db_session, mock_redis)
    with pytest.raises(CouponAlreadyClaimedError):
        await service.issue_coupon(request)


@pytest.mark.asyncio
async def test_validate_eligibility_success(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_user: User,
    test_coupon_skus: list,
) -> None:
    request = ValidateCouponRequest(
        user_id=test_user.user_id,
        activity_id=test_activity.activity_id,
        package_type=CouponType.NEW_READER,
        trigger_scene=TriggerScene.MEMBER_CENTER,
    )

    service = CouponService(db_session, mock_redis)
    result = await service.validate_eligibility(request)

    assert result["eligible"] is True
    assert result["package_id"] == test_coupon_package.package_id
    assert result["package_name"] == test_coupon_package.name
    assert result["remaining_stock"] == len(test_coupon_skus)
    assert result["valid_days"] == 30


@pytest.mark.asyncio
async def test_record_behavior_impression(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_user: User,
) -> None:
    request = CouponCallbackRequest(
        user_id=test_user.user_id,
        activity_id=test_activity.activity_id,
        package_id="pkg_001",
        user_coupon_id="",
        behavior_type=BehaviorType.IMPRESSION,
        trigger_scene=TriggerScene.MEMBER_CENTER,
        extra={"position": "banner_top"},
    )

    service = CouponService(db_session, mock_redis)
    await service.record_behavior(request)

    stmt = select(UserBehaviorLog).where(
        UserBehaviorLog.user_id == test_user.user_id
    )
    result = await db_session.execute(stmt)
    log = result.scalar_one()

    assert log.behavior_type == BehaviorType.IMPRESSION.value
    assert log.extra == {"position": "banner_top"}
    assert log.trigger_scene == TriggerScene.MEMBER_CENTER.value


@pytest.mark.asyncio
async def test_record_behavior_click(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_user: User,
) -> None:
    request = CouponCallbackRequest(
        user_id=test_user.user_id,
        activity_id=test_activity.activity_id,
        package_id="pkg_001",
        user_coupon_id="uc_001",
        behavior_type=BehaviorType.CLICK,
        trigger_scene=TriggerScene.TASK_CENTER,
        extra={"source": "push"},
    )

    service = CouponService(db_session, mock_redis)
    await service.record_behavior(request)

    stmt = select(UserBehaviorLog).where(
        UserBehaviorLog.behavior_type == BehaviorType.CLICK.value
    )
    result = await db_session.execute(stmt)
    log = result.scalar_one()

    assert log.user_coupon_id == "uc_001"
    assert log.extra == {"source": "push"}


@pytest.mark.asyncio
async def test_record_behavior_use(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_user: User,
    test_coupon_skus: list,
) -> None:
    user_coupon = UserCoupon(
        record_id="test_use_001",
        user_id=test_user.user_id,
        activity_id=test_activity.activity_id,
        package_id=test_coupon_package.package_id,
        sku_id=test_coupon_skus[0].sku_id,
        coupon_code=test_coupon_skus[0].coupon_code,
        status=0,
        trigger_scene=TriggerScene.MEMBER_CENTER.value,
        valid_start_time=datetime.now(),
        valid_end_time=datetime.now() + timedelta(days=30),
        applicable_comics="1001",
        display_text="测试",
    )
    db_session.add(user_coupon)
    await db_session.commit()

    request = CouponCallbackRequest(
        user_id=test_user.user_id,
        activity_id=test_activity.activity_id,
        package_id=test_coupon_package.package_id,
        user_coupon_id="test_use_001",
        behavior_type=BehaviorType.USE,
        trigger_scene=TriggerScene.OTHER,
        extra={"comic_id": "1001", "chapter_id": "5001"},
    )

    service = CouponService(db_session, mock_redis)
    await service.record_behavior(request)

    stmt = select(UserCoupon).where(UserCoupon.record_id == "test_use_001")
    result = await db_session.execute(stmt)
    updated_coupon = result.scalar_one()

    assert updated_coupon.status == CouponStatus.USED.value
    assert updated_coupon.used_comic_id == "1001"
    assert updated_coupon.used_at is not None

    sku_stmt = select(CouponPackageSku).where(
        CouponPackageSku.sku_id == test_coupon_skus[0].sku_id
    )
    sku_result = await db_session.execute(sku_stmt)
    sku = sku_result.scalar_one()
    assert sku.status == 2


@pytest.mark.asyncio
async def test_issue_coupon_vip_user(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_vip_activity: Activity,
    test_vip_coupon_package: CouponPackage,
    test_vip_user: User,
    test_vip_coupon_skus: list,
) -> None:
    request = IssueCouponRequest(
        user_id=test_vip_user.user_id,
        activity_id=test_vip_activity.activity_id,
        package_type=CouponType.MEMBER_EXCLUSIVE,
        trigger_scene=TriggerScene.MEMBER_CENTER,
    )

    service = CouponService(db_session, mock_redis)
    result = await service.issue_coupon(request)

    assert result.package_id == test_vip_coupon_package.package_id
    assert len(result.applicable_comics) == 2
    assert result.valid_end_time > result.valid_start_time

    delta = result.valid_end_time - result.valid_start_time
    assert delta.days == 15
