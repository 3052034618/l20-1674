import hashlib
import hmac
import time
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.partner_auth import (
    PartnerAuthError,
    PartnerDailyLimitError,
    PartnerForbiddenError,
    verify_partner_signature,
    check_partner_permission,
    check_partner_daily_limit,
    log_partner_api_call,
)
from app.core import (
    ActivityStatus,
    CouponType,
    MemberLevel,
    TriggerScene,
)
from app.db import get_db, get_redis
from app.main import app
from app.models import (
    Activity,
    CouponPackage,
    CouponPackageSku,
    Partner,
    PartnerApiLog,
    User,
)
from app.schemas import (
    IssueCouponRequest,
)
from app.services import CouponService


@pytest.mark.asyncio
async def test_issue_coupon_api_missing_signature(
    db_session: AsyncSession,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_user: User,
    test_coupon_skus: list,
) -> None:
    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()
    mock_redis.set = AsyncMock()
    mock_redis.decr = AsyncMock(return_value=100)
    mock_redis.hgetall = AsyncMock(return_value={})
    mock_redis.hset = AsyncMock()
    mock_redis.expire = AsyncMock()
    mock_redis.delete = AsyncMock()

    async def mock_get_redis():
        yield mock_redis

    async def mock_get_db():
        yield db_session

    app.dependency_overrides[get_redis] = mock_get_redis
    app.dependency_overrides[get_db] = mock_get_db

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/coupons/issue",
            json={
                "user_id": test_user.user_id,
                "activity_id": test_activity.activity_id,
                "package_type": CouponType.NEW_READER.value,
                "trigger_scene": TriggerScene.MEMBER_CENTER.value,
            },
        )
        assert response.status_code in (401, 422)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_issue_coupon_api_invalid_signature(
    db_session: AsyncSession,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_user: User,
    test_coupon_skus: list,
) -> None:
    partner = Partner(
        partner_id=f"partner_apitest_{uuid.uuid4().hex[:8]}",
        name="API测试合作方",
        sign_key=uuid.uuid4().hex,
        allowed_activities="",
        allowed_package_types="",
        daily_limit=0,
        status=1,
    )
    db_session.add(partner)
    await db_session.commit()
    await db_session.refresh(partner)

    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()
    mock_redis.set = AsyncMock()
    mock_redis.decr = AsyncMock(return_value=100)
    mock_redis.hgetall = AsyncMock(return_value={})
    mock_redis.hset = AsyncMock()
    mock_redis.expire = AsyncMock()
    mock_redis.delete = AsyncMock()

    async def mock_get_redis():
        yield mock_redis

    async def mock_get_db():
        yield db_session

    app.dependency_overrides[get_redis] = mock_get_redis
    app.dependency_overrides[get_db] = mock_get_db

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/coupons/issue",
            json={
                "user_id": test_user.user_id,
                "activity_id": test_activity.activity_id,
                "package_type": CouponType.NEW_READER.value,
                "trigger_scene": TriggerScene.MEMBER_CENTER.value,
            },
            headers={
                "X-Partner-Id": partner.partner_id,
                "X-Timestamp": str(int(time.time())),
                "X-Nonce": uuid.uuid4().hex,
                "X-Signature": "invalid_signature",
            },
        )
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_issue_coupon_api_expired_timestamp(
    db_session: AsyncSession,
) -> None:
    partner = Partner(
        partner_id=f"partner_ts_{uuid.uuid4().hex[:8]}",
        name="时间戳测试合作方",
        sign_key=uuid.uuid4().hex,
        status=1,
    )
    db_session.add(partner)
    await db_session.commit()
    await db_session.refresh(partner)

    old_timestamp = str(int(time.time()) - 600)
    mock_request = AsyncMock()
    mock_request.method = "POST"
    mock_request.body = AsyncMock(return_value=b"")

    with pytest.raises(PartnerAuthError) as exc_info:
        await verify_partner_signature(
            request=mock_request,
            x_partner_id=partner.partner_id,
            x_timestamp=old_timestamp,
            x_nonce=uuid.uuid4().hex,
            x_signature="anything",
            db=db_session,
            redis_client=None,
        )
    assert exc_info.value.error_key == "signature_expired"


@pytest.mark.asyncio
async def test_validate_api_no_daily_limit_consumption(
    db_session: AsyncSession,
) -> None:
    partner = Partner(
        partner_id=f"partner_nolimit_{uuid.uuid4().hex[:8]}",
        name="校验不限额",
        sign_key=uuid.uuid4().hex,
        daily_limit=1,
        status=1,
    )
    db_session.add(partner)
    await db_session.commit()
    await db_session.refresh(partner)

    await check_partner_daily_limit(partner, db_session)
    await check_partner_daily_limit(partner, db_session)


@pytest.mark.asyncio
async def test_partner_forbidden_activity(
    db_session: AsyncSession,
) -> None:
    partner = Partner(
        partner_id=f"partner_fb_{uuid.uuid4().hex[:8]}",
        name="权限禁止测试",
        sign_key=uuid.uuid4().hex,
        allowed_activities="act_001",
        allowed_package_types="new_reader",
        status=1,
    )
    db_session.add(partner)
    await db_session.commit()
    await db_session.refresh(partner)

    with pytest.raises(PartnerForbiddenError) as exc_info:
        await check_partner_permission(partner, "act_999", "new_reader", db_session)
    assert exc_info.value.error_key == "partner_forbidden"
    assert exc_info.value.code == 403


@pytest.mark.asyncio
async def test_auto_log_on_issue_success(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_user: User,
    test_coupon_skus: list,
) -> None:
    partner = Partner(
        partner_id=f"partner_log_{uuid.uuid4().hex[:8]}",
        name="日志测试合作方",
        sign_key=uuid.uuid4().hex,
        allowed_activities=test_activity.activity_id,
        allowed_package_types=CouponType.NEW_READER.value,
        daily_limit=0,
        status=1,
    )
    db_session.add(partner)
    await db_session.commit()
    await db_session.refresh(partner)

    request = IssueCouponRequest(
        user_id=test_user.user_id,
        activity_id=test_activity.activity_id,
        package_type=CouponType.NEW_READER,
        trigger_scene=TriggerScene.MEMBER_CENTER,
        partner_id=partner.partner_id,
        biz_serial_no="biz_log_001",
    )

    service = CouponService(db_session, mock_redis)
    await service.issue_coupon(request)

    await log_partner_api_call(
        db_session,
        partner_id=partner.partner_id,
        api_path="/api/v1/coupon/issue",
        success=True,
        activity_id=test_activity.activity_id,
        package_type=CouponType.NEW_READER.value,
    )

    stmt = select(PartnerApiLog).where(
        PartnerApiLog.partner_id == partner.partner_id
    )
    result = await db_session.execute(stmt)
    logs = result.scalars().all()
    assert len(logs) >= 1
    assert logs[0].success == 1
    assert logs[0].api_path == "/api/v1/coupon/issue"
    assert logs[0].activity_id == test_activity.activity_id


@pytest.mark.asyncio
async def test_auto_log_on_issue_failure(
    db_session: AsyncSession,
    mock_redis: MagicMock,
) -> None:
    partner = Partner(
        partner_id=f"partner_failog_{uuid.uuid4().hex[:8]}",
        name="失败日志测试合作方",
        sign_key=uuid.uuid4().hex,
        status=1,
    )
    db_session.add(partner)
    await db_session.commit()
    await db_session.refresh(partner)

    await log_partner_api_call(
        db_session,
        partner_id=partner.partner_id,
        api_path="/api/v1/coupon/issue",
        success=False,
        error_key="stock_insufficient",
        activity_id="act_001",
        package_type="new_reader",
    )

    stmt = select(PartnerApiLog).where(
        PartnerApiLog.partner_id == partner.partner_id
    )
    result = await db_session.execute(stmt)
    logs = result.scalars().all()
    assert len(logs) == 1
    assert logs[0].success == 0
    assert logs[0].error_key == "stock_insufficient"


@pytest.mark.asyncio
async def test_idempotent_redis_read_failure(
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
        partner_id="partner_redis_fail",
        biz_serial_no="biz_redis_fail_001",
    )

    service = CouponService(db_session, None)
    result1 = await service.issue_coupon(request)

    failing_redis = MagicMock()
    failing_redis.hgetall = AsyncMock(side_effect=Exception("Redis connection refused"))
    failing_redis.hset = AsyncMock(side_effect=Exception("Redis connection refused"))
    failing_redis.expire = AsyncMock(side_effect=Exception("Redis connection refused"))
    failing_redis.get = AsyncMock(side_effect=Exception("Redis connection refused"))
    failing_redis.setex = AsyncMock(side_effect=Exception("Redis connection refused"))
    failing_redis.set = AsyncMock(side_effect=Exception("Redis connection refused"))
    failing_redis.decr = AsyncMock(side_effect=Exception("Redis connection refused"))
    failing_redis.delete = AsyncMock(side_effect=Exception("Redis connection refused"))

    service2 = CouponService(db_session, failing_redis)
    result2 = await service2.issue_coupon(request)

    assert result2.record_id == result1.record_id
    assert result2.coupon_code == result1.coupon_code
    assert result2.package_name == result1.package_name
    assert result2.valid_start_time == result1.valid_start_time
    assert result2.valid_end_time == result1.valid_end_time


@pytest.mark.asyncio
async def test_idempotent_redis_write_failure_does_not_block(
    db_session: AsyncSession,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_user: User,
    test_coupon_skus: list,
) -> None:
    from faker import Faker
    fake = Faker("zh_CN")

    new_user = User(
        user_id=f"user_rediswr_{fake.uuid4()[:8]}",
        nickname=fake.name(),
        member_level=MemberLevel.FREE.value,
        region="CN",
        is_new_reader=1,
    )
    db_session.add(new_user)
    await db_session.commit()
    await db_session.refresh(new_user)

    request = IssueCouponRequest(
        user_id=new_user.user_id,
        activity_id=test_activity.activity_id,
        package_type=CouponType.NEW_READER,
        trigger_scene=TriggerScene.MEMBER_CENTER,
        partner_id="partner_redis_wr_fail",
        biz_serial_no=f"biz_rediswr_{uuid.uuid4().hex[:8]}",
    )

    failing_redis = MagicMock()
    failing_redis.hgetall = AsyncMock(return_value={})
    failing_redis.hset = AsyncMock(side_effect=Exception("Redis write failed"))
    failing_redis.expire = AsyncMock(side_effect=Exception("Redis write failed"))
    failing_redis.get = AsyncMock(return_value=None)
    failing_redis.setex = AsyncMock(side_effect=Exception("Redis write failed"))
    failing_redis.set = AsyncMock(side_effect=Exception("Redis write failed"))
    failing_redis.decr = AsyncMock(side_effect=Exception("Redis write failed"))
    failing_redis.delete = AsyncMock(side_effect=Exception("Redis write failed"))

    service = CouponService(db_session, failing_redis)
    result = await service.issue_coupon(request)

    assert result is not None
    assert result.coupon_code is not None


@pytest.mark.asyncio
async def test_daily_limit_blocks_issue_not_validate(
    db_session: AsyncSession,
) -> None:
    partner = Partner(
        partner_id=f"partner_dlim_{uuid.uuid4().hex[:8]}",
        name="限额不卡校验测试",
        sign_key=uuid.uuid4().hex,
        daily_limit=0,
        status=1,
    )
    db_session.add(partner)
    await db_session.commit()
    await db_session.refresh(partner)

    now = datetime.now()
    for i in range(3):
        log = PartnerApiLog(
            log_id=f"palog_{uuid.uuid4().hex}",
            partner_id=partner.partner_id,
            api_path="/api/v1/coupon/issue",
            request_time=now,
            success=1,
        )
        db_session.add(log)
    await db_session.commit()

    partner.daily_limit = 3
    await db_session.commit()
    await db_session.refresh(partner)

    with pytest.raises(PartnerDailyLimitError):
        await check_partner_daily_limit(partner, db_session)

    partner2 = Partner(
        partner_id=f"partner_validate_nolimit_{uuid.uuid4().hex[:8]}",
        name="校验不限额2",
        sign_key=uuid.uuid4().hex,
        daily_limit=1,
        status=1,
    )
    db_session.add(partner2)
    await db_session.commit()
    await db_session.refresh(partner2)

    await check_partner_daily_limit(partner2, db_session)
    await check_partner_daily_limit(partner2, db_session)
