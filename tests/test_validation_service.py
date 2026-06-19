from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, MagicMock

from app.core import (
    ActivityStatus,
    CouponAlreadyClaimedError,
    CouponActivityError,
    CouponEligibilityError,
    CouponStockError,
    CouponType,
    MemberLevel,
    TriggerScene,
)
from app.models import Activity, CouponPackage, User, UserCoupon
from app.schemas import IssueCouponRequest, ValidateCouponRequest
from app.services.validation_service import ValidationService


@pytest.mark.asyncio
async def test_validate_activity_status_draft(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_user: User,
) -> None:
    test_activity.status = ActivityStatus.DRAFT.value
    await db_session.commit()

    request = IssueCouponRequest(
        user_id=test_user.user_id,
        activity_id=test_activity.activity_id,
        package_type=CouponType.NEW_READER,
        trigger_scene=TriggerScene.MEMBER_CENTER,
    )

    service = ValidationService(db_session, mock_redis)
    with pytest.raises(CouponActivityError) as exc_info:
        await service.validate_all(request)
    assert exc_info.value.user_message == "活动未开始"


@pytest.mark.asyncio
async def test_validate_activity_status_paused(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_user: User,
) -> None:
    test_activity.status = ActivityStatus.PAUSED.value
    await db_session.commit()

    request = IssueCouponRequest(
        user_id=test_user.user_id,
        activity_id=test_activity.activity_id,
        package_type=CouponType.NEW_READER,
        trigger_scene=TriggerScene.MEMBER_CENTER,
    )

    service = ValidationService(db_session, mock_redis)
    with pytest.raises(CouponActivityError) as exc_info:
        await service.validate_all(request)
    assert exc_info.value.user_message == "活动暂停中"


@pytest.mark.asyncio
async def test_validate_activity_status_ended(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_user: User,
) -> None:
    test_activity.status = ActivityStatus.ENDED.value
    await db_session.commit()

    request = IssueCouponRequest(
        user_id=test_user.user_id,
        activity_id=test_activity.activity_id,
        package_type=CouponType.NEW_READER,
        trigger_scene=TriggerScene.MEMBER_CENTER,
    )

    service = ValidationService(db_session, mock_redis)
    with pytest.raises(CouponActivityError) as exc_info:
        await service.validate_all(request)
    assert exc_info.value.user_message == "活动已结束"


@pytest.mark.asyncio
async def test_validate_activity_time_not_started(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_user: User,
) -> None:
    test_activity.start_time = datetime.now() + timedelta(days=1)
    await db_session.commit()

    request = IssueCouponRequest(
        user_id=test_user.user_id,
        activity_id=test_activity.activity_id,
        package_type=CouponType.NEW_READER,
        trigger_scene=TriggerScene.MEMBER_CENTER,
    )

    service = ValidationService(db_session, mock_redis)
    with pytest.raises(CouponActivityError) as exc_info:
        await service.validate_all(request)
    assert exc_info.value.user_message == "活动未开始"


@pytest.mark.asyncio
async def test_validate_activity_time_already_ended(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_user: User,
) -> None:
    test_activity.end_time = datetime.now() - timedelta(days=1)
    await db_session.commit()

    request = IssueCouponRequest(
        user_id=test_user.user_id,
        activity_id=test_activity.activity_id,
        package_type=CouponType.NEW_READER,
        trigger_scene=TriggerScene.MEMBER_CENTER,
    )

    service = ValidationService(db_session, mock_redis)
    with pytest.raises(CouponActivityError) as exc_info:
        await service.validate_all(request)
    assert exc_info.value.user_message == "活动已结束"


@pytest.mark.asyncio
async def test_validate_user_not_new_reader(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_vip_user: User,
) -> None:
    test_activity.require_new_reader = 1
    await db_session.commit()

    request = IssueCouponRequest(
        user_id=test_vip_user.user_id,
        activity_id=test_activity.activity_id,
        package_type=CouponType.NEW_READER,
        trigger_scene=TriggerScene.MEMBER_CENTER,
    )

    service = ValidationService(db_session, mock_redis)
    with pytest.raises(CouponEligibilityError) as exc_info:
        await service.validate_all(request)
    assert exc_info.value.user_message == "仅限新读者"


@pytest.mark.asyncio
async def test_validate_user_member_level_insufficient(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_vip_activity: Activity,
    test_vip_coupon_package: CouponPackage,
    test_user: User,
) -> None:
    test_vip_activity.min_member_level = MemberLevel.GOLD.value
    await db_session.commit()

    request = IssueCouponRequest(
        user_id=test_user.user_id,
        activity_id=test_vip_activity.activity_id,
        package_type=CouponType.MEMBER_EXCLUSIVE,
        trigger_scene=TriggerScene.MEMBER_CENTER,
    )

    service = ValidationService(db_session, mock_redis)
    with pytest.raises(CouponEligibilityError) as exc_info:
        await service.validate_all(request)
    assert exc_info.value.user_message == "会员等级不足"


@pytest.mark.asyncio
async def test_validate_user_region_restricted(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_vip_activity: Activity,
    test_vip_coupon_package: CouponPackage,
    test_vip_user: User,
) -> None:
    test_vip_activity.allowed_regions = "US,UK"
    test_vip_user.region = "CN"
    await db_session.commit()

    request = IssueCouponRequest(
        user_id=test_vip_user.user_id,
        activity_id=test_vip_activity.activity_id,
        package_type=CouponType.MEMBER_EXCLUSIVE,
        trigger_scene=TriggerScene.MEMBER_CENTER,
    )

    service = ValidationService(db_session, mock_redis)
    with pytest.raises(CouponEligibilityError) as exc_info:
        await service.validate_all(request)
    assert exc_info.value.user_message == "当前地区不支持领取"


@pytest.mark.asyncio
async def test_validate_already_claimed(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_user: User,
    test_coupon_skus: list,
) -> None:
    user_coupon = UserCoupon(
        record_id="test_claimed_001",
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

    service = ValidationService(db_session, mock_redis)
    with pytest.raises(CouponAlreadyClaimedError) as exc_info:
        await service.validate_all(request)
    assert exc_info.value.user_message == "已领过"


@pytest.mark.asyncio
async def test_validate_stock_insufficient(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_user: User,
) -> None:
    test_coupon_package.total_quantity = 10
    test_coupon_package.claimed_quantity = 10
    await db_session.commit()

    async def mock_get(key: str) -> str | None:
        if key.startswith("coupon:stock:"):
            return "0"
        return None
    mock_redis.get = AsyncMock(side_effect=mock_get)

    request = IssueCouponRequest(
        user_id=test_user.user_id,
        activity_id=test_activity.activity_id,
        package_type=CouponType.NEW_READER,
        trigger_scene=TriggerScene.MEMBER_CENTER,
    )

    service = ValidationService(db_session, mock_redis)
    with pytest.raises(CouponStockError) as exc_info:
        await service.validate_all(request)
    assert exc_info.value.user_message == "券包已被抢光"


@pytest.mark.asyncio
async def test_validate_all_success(
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
    )

    service = ValidationService(db_session, mock_redis)
    result = await service.validate_all(request)

    assert result["user"].user_id == test_user.user_id
    assert result["activity"].activity_id == test_activity.activity_id
    assert result["coupon_package"].package_id == test_coupon_package.package_id


@pytest.mark.asyncio
async def test_validate_with_validate_request(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_vip_activity: Activity,
    test_vip_coupon_package: CouponPackage,
    test_vip_user: User,
    test_vip_coupon_skus: list,
) -> None:
    request = ValidateCouponRequest(
        user_id=test_vip_user.user_id,
        activity_id=test_vip_activity.activity_id,
        package_type=CouponType.MEMBER_EXCLUSIVE,
        trigger_scene=TriggerScene.TASK_CENTER,
    )

    service = ValidationService(db_session, mock_redis)
    result = await service.validate_all(request)

    assert result["user"].user_id == test_vip_user.user_id
    assert result["activity"].activity_id == test_vip_activity.activity_id
    assert result["coupon_package"].package_id == test_vip_coupon_package.package_id
