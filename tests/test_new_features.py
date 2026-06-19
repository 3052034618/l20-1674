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
    CreateActivityRequest,
    CreateCouponPackageRequest,
    GenerateCouponCodesRequest,
    ImportCouponCodesRequest,
    IssueCouponRequest,
)
from app.services import AdminService, CouponService, ValidationService


@pytest.mark.asyncio
async def test_last_coupon_issue_success(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_user: User,
    test_coupon_skus: list,
) -> None:
    test_coupon_package.total_quantity = 1
    test_coupon_package.claimed_quantity = 0
    await db_session.commit()

    stmt = select(CouponPackageSku).where(
        CouponPackageSku.package_id == test_coupon_package.package_id,
        CouponPackageSku.status == 0,
    )
    result = await db_session.execute(stmt)
    skus = result.scalars().all()
    for sku in skus[1:]:
        sku.status = 1
        await db_session.commit()

    request = IssueCouponRequest(
        user_id=test_user.user_id,
        activity_id=test_activity.activity_id,
        package_type=CouponType.NEW_READER,
        trigger_scene=TriggerScene.MEMBER_CENTER,
    )

    service = CouponService(db_session, mock_redis)
    result = await service.issue_coupon(request)

    assert result.record_id.startswith("uc_")
    assert result.package_id == test_coupon_package.package_id

    stmt = select(CouponPackageSku).where(
        CouponPackageSku.package_id == test_coupon_package.package_id,
        CouponPackageSku.status == 0,
    )
    result = await db_session.execute(stmt)
    remaining = result.scalars().all()
    assert len(remaining) == 0


@pytest.mark.asyncio
async def test_stock_mismatch_sku_less_than_config(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_user: User,
    test_coupon_skus: list,
) -> None:
    test_coupon_package.total_quantity = 100
    test_coupon_package.claimed_quantity = 0
    await db_session.commit()

    stmt = select(CouponPackageSku).where(
        CouponPackageSku.package_id == test_coupon_package.package_id,
        CouponPackageSku.status == 0,
    )
    result = await db_session.execute(stmt)
    skus = result.scalars().all()
    for sku in skus[2:]:
        sku.status = 1
        await db_session.commit()

    from app.models import User
    from app.core import MemberLevel
    from faker import Faker
    fake = Faker("zh_CN")

    users = []
    for i in range(3):
        user = User(
            user_id=f"user_stock_test_{i}_{fake.uuid4()[:8]}",
            nickname=fake.name(),
            member_level=MemberLevel.FREE.value,
            region="CN",
            is_new_reader=1,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        users.append(user)

    validation_service = ValidationService(db_session, mock_redis)

    for i in range(2):
        request = IssueCouponRequest(
            user_id=users[i].user_id,
            activity_id=test_activity.activity_id,
            package_type=CouponType.NEW_READER,
            trigger_scene=TriggerScene.MEMBER_CENTER,
        )
        result = await validation_service.validate_all(request)
        assert result is not None
        coupon_service = CouponService(db_session, mock_redis)
        await coupon_service.issue_coupon(request)

    from app.core import CouponStockError

    request3 = IssueCouponRequest(
        user_id=users[2].user_id,
        activity_id=test_activity.activity_id,
        package_type=CouponType.NEW_READER,
        trigger_scene=TriggerScene.MEMBER_CENTER,
    )
    with pytest.raises(CouponStockError):
        await validation_service.validate_all(request3)


@pytest.mark.asyncio
async def test_validate_eligibility_real_stock(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_user: User,
    test_coupon_skus: list,
) -> None:
    test_coupon_package.total_quantity = 1000
    test_coupon_package.claimed_quantity = 0
    await db_session.commit()

    service = CouponService(db_session, mock_redis)
    request = IssueCouponRequest(
        user_id=test_user.user_id,
        activity_id=test_activity.activity_id,
        package_type=CouponType.NEW_READER,
        trigger_scene=TriggerScene.MEMBER_CENTER,
    )
    result = await service.validate_eligibility(request)

    assert result["remaining_stock"] == len(test_coupon_skus)
    assert result["remaining_stock"] != 1000


@pytest.mark.asyncio
async def test_create_activity(
    db_session: AsyncSession,
    mock_redis: MagicMock,
) -> None:
    now = datetime.now()
    request = CreateActivityRequest(
        activity_id="test_activity_001",
        name="测试活动",
        description="这是一个测试活动",
        status=ActivityStatus.ONGOING,
        start_time=now,
        end_time=now + timedelta(days=30),
        allowed_regions="CN,US",
        min_member_level=MemberLevel.SILVER,
        require_new_reader=True,
    )

    service = AdminService(db_session, mock_redis)
    result = await service.create_activity(request)

    assert result["activity_id"] == "test_activity_001"
    assert result["name"] == "测试活动"
    assert result["allowed_regions"] == "CN,US"
    assert result["min_member_level"] == MemberLevel.SILVER.value
    assert result["require_new_reader"] is True


@pytest.mark.asyncio
async def test_create_coupon_package(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
) -> None:
    request = CreateCouponPackageRequest(
        package_id="test_package_001",
        activity_id=test_activity.activity_id,
        name="测试券包",
        type=CouponType.REGULAR,
        display_text="测试展示文案",
        valid_days=15,
        applicable_comics="1001,1002",
        discount_value=500,
        discount_type="fixed",
    )

    service = AdminService(db_session, mock_redis)
    result = await service.create_coupon_package(request)

    assert result["package_id"] == "test_package_001"
    assert result["activity_id"] == test_activity.activity_id
    assert result["type"] == CouponType.REGULAR.value
    assert result["valid_days"] == 15
    assert result["total_quantity"] == 0


@pytest.mark.asyncio
async def test_generate_coupon_codes(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_coupon_package: CouponPackage,
) -> None:
    request = GenerateCouponCodesRequest(
        package_id=test_coupon_package.package_id,
        quantity=5,
        expire_days=60,
        prefix="TEST",
    )

    service = AdminService(db_session, mock_redis)
    result = await service.generate_coupon_codes(request)

    assert result["generated_count"] == 5
    assert len(result["sample_codes"]) == 5
    for code in result["sample_codes"]:
        assert code.startswith("TEST")


@pytest.mark.asyncio
async def test_import_coupon_codes(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_coupon_package: CouponPackage,
) -> None:
    codes = ["IMPORT001", "IMPORT002", "IMPORT003"]
    request = ImportCouponCodesRequest(
        package_id=test_coupon_package.package_id,
        coupon_codes=codes,
        expire_days=30,
    )

    service = AdminService(db_session, mock_redis)
    result = await service.import_coupon_codes(request)

    assert result["imported_count"] == 3
    assert result["duplicate_count"] == 0


@pytest.mark.asyncio
async def test_import_duplicate_coupon_codes(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_coupon_package: CouponPackage,
) -> None:
    codes = ["DUP001", "DUP002"]
    request1 = ImportCouponCodesRequest(
        package_id=test_coupon_package.package_id,
        coupon_codes=codes,
        expire_days=30,
    )
    service = AdminService(db_session, mock_redis)
    await service.import_coupon_codes(request1)

    request2 = ImportCouponCodesRequest(
        package_id=test_coupon_package.package_id,
        coupon_codes=["DUP001", "NEW001"],
        expire_days=30,
    )
    result = await service.import_coupon_codes(request2)

    assert result["imported_count"] == 1
    assert result["duplicate_count"] == 1


@pytest.mark.asyncio
async def test_get_package_stats(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_coupon_package: CouponPackage,
    test_coupon_skus: list,
) -> None:
    test_coupon_skus[0].status = 1
    test_coupon_skus[1].status = 2
    await db_session.commit()

    service = AdminService(db_session, mock_redis)
    result = await service.get_package_stats(test_coupon_package.package_id)

    assert result["total_quantity"] == test_coupon_package.total_quantity
    assert result["available"] == len(test_coupon_skus) - 2
    assert result["claimed_unused"] == 1
    assert result["issued"] == 2
    assert result["used"] == 1


@pytest.mark.asyncio
async def test_list_activities(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_vip_activity: Activity,
) -> None:
    service = AdminService(db_session, mock_redis)
    result = await service.list_activities()

    assert len(result) >= 2
    activity_ids = [a["activity_id"] for a in result]
    assert test_activity.activity_id in activity_ids
    assert test_vip_activity.activity_id in activity_ids


@pytest.mark.asyncio
async def test_list_packages(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_vip_activity: Activity,
    test_vip_coupon_package: CouponPackage,
) -> None:
    service = AdminService(db_session, mock_redis)

    all_packages = await service.list_packages()
    assert len(all_packages) >= 2

    activity_packages = await service.list_packages(activity_id=test_activity.activity_id)
    assert len(activity_packages) == 1
    assert activity_packages[0]["package_id"] == test_coupon_package.package_id


@pytest.mark.asyncio
async def test_issue_coupon_with_external_ids(
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
        external_user_id="ext_user_12345",
        partner_id="member_center",
        biz_serial_no="biz_001",
    )

    service = CouponService(db_session, mock_redis)
    result = await service.issue_coupon(request)

    assert result.record_id.startswith("uc_")

    stmt = select(UserCoupon).where(UserCoupon.record_id == result.record_id)
    db_result = await db_session.execute(stmt)
    user_coupon = db_result.scalar_one()

    assert user_coupon.external_user_id == "ext_user_12345"
    assert user_coupon.partner_id == "member_center"
    assert user_coupon.biz_serial_no == "biz_001"


@pytest.mark.asyncio
async def test_issue_coupon_idempotent_by_biz_serial(
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
        partner_id="member_center",
        biz_serial_no="biz_idempotent_001",
    )

    service = CouponService(db_session, mock_redis)
    result1 = await service.issue_coupon(request)

    cached_data = {
        "record_id": result1.record_id,
        "coupon_code": result1.coupon_code,
        "package_id": result1.package_id,
        "package_name": result1.package_name,
        "display_text": result1.display_text,
        "valid_start_time": result1.valid_start_time.isoformat(),
        "valid_end_time": result1.valid_end_time.isoformat(),
        "applicable_comics": ",".join(result1.applicable_comics),
    }
    mock_redis.hgetall = AsyncMock(return_value=cached_data)

    result2 = await service.issue_coupon(request)

    assert result1.record_id == result2.record_id
    assert result1.coupon_code == result2.coupon_code


@pytest.mark.asyncio
async def test_issue_coupon_different_partners_same_serial(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_user: User,
    test_coupon_skus: list,
) -> None:
    request1 = IssueCouponRequest(
        user_id=test_user.user_id,
        activity_id=test_activity.activity_id,
        package_type=CouponType.NEW_READER,
        trigger_scene=TriggerScene.MEMBER_CENTER,
        partner_id="partner_a",
        biz_serial_no="same_serial_001",
    )

    request2 = IssueCouponRequest(
        user_id=test_user.user_id,
        activity_id=test_activity.activity_id,
        package_type=CouponType.NEW_READER,
        trigger_scene=TriggerScene.MEMBER_CENTER,
        partner_id="partner_b",
        biz_serial_no="same_serial_001",
    )

    service = CouponService(db_session, mock_redis)
    result1 = await service.issue_coupon(request1)

    mock_redis.hgetall = AsyncMock(return_value={})

    from app.core import CouponAlreadyClaimedError

    with pytest.raises(CouponAlreadyClaimedError):
        await service.issue_coupon(request2)


@pytest.mark.asyncio
async def test_behavior_stats(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_user: User,
) -> None:
    import uuid

    log_data = [
        (BehaviorType.IMPRESSION, TriggerScene.MEMBER_CENTER),
        (BehaviorType.IMPRESSION, TriggerScene.MEMBER_CENTER),
        (BehaviorType.CLICK, TriggerScene.MEMBER_CENTER),
        (BehaviorType.USE, TriggerScene.MEMBER_CENTER),
        (BehaviorType.IMPRESSION, TriggerScene.TASK_CENTER),
        (BehaviorType.CLICK, TriggerScene.TASK_CENTER),
    ]

    for behavior_type, trigger_scene in log_data:
        log_id = f"log_{uuid.uuid4().hex}"
        log = UserBehaviorLog(
            log_id=log_id,
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

    assert result["total"]["impression"] == 3
    assert result["total"]["click"] == 2
    assert result["total"]["use"] == 1
    assert len(result["by_scene"]) == 2

    scene_stats = {s["trigger_scene"]: s for s in result["by_scene"]}
    assert scene_stats[TriggerScene.MEMBER_CENTER.value]["impression_count"] == 2
    assert scene_stats[TriggerScene.MEMBER_CENTER.value]["click_count"] == 1
    assert scene_stats[TriggerScene.MEMBER_CENTER.value]["use_count"] == 1
    assert scene_stats[TriggerScene.TASK_CENTER.value]["impression_count"] == 1
    assert scene_stats[TriggerScene.TASK_CENTER.value]["click_count"] == 1


@pytest.mark.asyncio
async def test_behavior_stats_with_package_type(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_user: User,
) -> None:
    import uuid

    for i in range(3):
        log_id = f"log_{uuid.uuid4().hex}"
        log = UserBehaviorLog(
            log_id=log_id,
            user_id=test_user.user_id,
            activity_id=test_activity.activity_id,
            package_id=test_coupon_package.package_id,
            behavior_type=BehaviorType.IMPRESSION.value,
            trigger_scene=TriggerScene.MEMBER_CENTER.value,
            extra={},
        )
        db_session.add(log)
    await db_session.commit()

    request = BehaviorStatsRequest(
        activity_id=test_activity.activity_id,
        package_type=CouponType.NEW_READER,
    )

    service = AdminService(db_session, mock_redis)
    result = await service.get_behavior_stats(request)

    assert result["total"]["impression"] == 3
    assert result["package_type"] == CouponType.NEW_READER.value
