import hashlib
import hmac
import time
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import (
    ActivityStatus,
    CouponType,
    CouponStatus,
    MemberLevel,
    TriggerScene,
)
from app.models import (
    Activity,
    CouponPackage,
    CouponPackageSku,
    Partner,
    PartnerApiLog,
    User,
    UserCoupon,
)
from app.schemas import (
    CreatePartnerRequest,
    IssueCouponRequest,
    PartnerReportRequest,
    UpdatePartnerRequest,
)
from app.services import AdminService, CouponService


@pytest.mark.asyncio
async def test_create_partner(
    db_session: AsyncSession,
    mock_redis: MagicMock,
) -> None:
    request = CreatePartnerRequest(
        partner_id=f"partner_{uuid.uuid4().hex[:8]}",
        name="会员中心",
        allowed_activities="act_001,act_002",
        allowed_package_types="new_reader",
        daily_limit=1000,
    )
    service = AdminService(db_session, mock_redis)
    result = await service.create_partner(request)

    assert result["partner_id"] == request.partner_id
    assert result["name"] == "会员中心"
    assert result["sign_key"]
    assert len(result["sign_key"]) == 32
    assert result["daily_limit"] == 1000
    assert result["status"] == 1


@pytest.mark.asyncio
async def test_update_partner(
    db_session: AsyncSession,
    mock_redis: MagicMock,
) -> None:
    partner = Partner(
        partner_id=f"partner_upd_{uuid.uuid4().hex[:8]}",
        name="原始名称",
        sign_key=uuid.uuid4().hex,
        allowed_activities="act_001",
        allowed_package_types="new_reader",
        daily_limit=500,
        status=1,
    )
    db_session.add(partner)
    await db_session.commit()
    await db_session.refresh(partner)

    request = UpdatePartnerRequest(
        partner_id=partner.partner_id,
        name="更新名称",
        daily_limit=2000,
    )
    service = AdminService(db_session, mock_redis)
    result = await service.update_partner(request)

    assert result["name"] == "更新名称"
    assert result["daily_limit"] == 2000


@pytest.mark.asyncio
async def test_list_partners(
    db_session: AsyncSession,
    mock_redis: MagicMock,
) -> None:
    for i in range(3):
        partner = Partner(
            partner_id=f"partner_list_{i}_{uuid.uuid4().hex[:8]}",
            name=f"合作方{i}",
            sign_key=uuid.uuid4().hex,
            status=1,
        )
        db_session.add(partner)
    await db_session.commit()

    service = AdminService(db_session, mock_redis)
    result = await service.list_partners()

    assert len(result) >= 3
    assert result[0]["status_label"] in ("启用", "禁用")


@pytest.mark.asyncio
async def test_reset_partner_sign_key(
    db_session: AsyncSession,
    mock_redis: MagicMock,
) -> None:
    partner = Partner(
        partner_id=f"partner_key_{uuid.uuid4().hex[:8]}",
        name="测试合作方",
        sign_key="old_key_value",
        status=1,
    )
    db_session.add(partner)
    await db_session.commit()
    await db_session.refresh(partner)

    service = AdminService(db_session, mock_redis)
    result = await service.reset_partner_sign_key(partner.partner_id)

    assert result["sign_key"] != "old_key_value"
    assert len(result["sign_key"]) == 32


@pytest.mark.asyncio
async def test_partner_signature_verification(
    db_session: AsyncSession,
) -> None:
    sign_key = uuid.uuid4().hex
    partner = Partner(
        partner_id=f"partner_sig_{uuid.uuid4().hex[:8]}",
        name="签名测试合作方",
        sign_key=sign_key,
        status=1,
    )
    db_session.add(partner)
    await db_session.commit()
    await db_session.refresh(partner)

    from app.api.partner_auth import verify_partner_signature

    timestamp = str(int(time.time()))
    nonce = uuid.uuid4().hex

    sign_base = f"{partner.partner_id}\n{timestamp}\n{nonce}\n"
    sig = hmac.new(
        sign_key.encode("utf-8"),
        sign_base.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    from unittest.mock import AsyncMock
    mock_request = AsyncMock()
    mock_request.method = "POST"
    mock_request.body = AsyncMock(return_value=b"")

    from fastapi import Depends
    result = await verify_partner_signature(
        request=mock_request,
        x_partner_id=partner.partner_id,
        x_timestamp=timestamp,
        x_nonce=nonce,
        x_signature=sig,
        db=db_session,
        redis_client=None,
    )

    assert result.partner_id == partner.partner_id


@pytest.mark.asyncio
async def test_partner_signature_invalid(
    db_session: AsyncSession,
) -> None:
    partner = Partner(
        partner_id=f"partner_invsig_{uuid.uuid4().hex[:8]}",
        name="签名测试合作方",
        sign_key=uuid.uuid4().hex,
        status=1,
    )
    db_session.add(partner)
    await db_session.commit()

    from app.api.partner_auth import verify_partner_signature, PartnerAuthError

    mock_request = AsyncMock()
    mock_request.method = "POST"
    mock_request.body = AsyncMock(return_value=b"")

    with pytest.raises(PartnerAuthError):
        await verify_partner_signature(
            request=mock_request,
            x_partner_id=partner.partner_id,
            x_timestamp=str(int(time.time())),
            x_nonce=uuid.uuid4().hex,
            x_signature="invalid_signature",
            db=db_session,
            redis_client=None,
        )


@pytest.mark.asyncio
async def test_partner_report(
    db_session: AsyncSession,
    mock_redis: MagicMock,
) -> None:
    partner = Partner(
        partner_id=f"partner_rpt_{uuid.uuid4().hex[:8]}",
        name="报表测试合作方",
        sign_key=uuid.uuid4().hex,
        status=1,
    )
    db_session.add(partner)
    await db_session.commit()
    await db_session.refresh(partner)

    now = datetime.now()
    logs = [
        PartnerApiLog(
            log_id=f"palog_{uuid.uuid4().hex}",
            partner_id=partner.partner_id,
            api_path="/api/v1/coupon/issue",
            request_time=now,
            success=1,
            error_key="",
            is_idempotent_hit=0,
            activity_id="act_001",
            package_type="new_reader",
        ),
        PartnerApiLog(
            log_id=f"palog_{uuid.uuid4().hex}",
            partner_id=partner.partner_id,
            api_path="/api/v1/coupon/issue",
            request_time=now,
            success=1,
            error_key="",
            is_idempotent_hit=1,
            activity_id="act_001",
            package_type="new_reader",
        ),
        PartnerApiLog(
            log_id=f"palog_{uuid.uuid4().hex}",
            partner_id=partner.partner_id,
            api_path="/api/v1/coupon/issue",
            request_time=now,
            success=0,
            error_key="activity_ended",
            is_idempotent_hit=0,
            activity_id="act_002",
            package_type="new_reader",
        ),
    ]
    for log in logs:
        db_session.add(log)
    await db_session.commit()

    request = PartnerReportRequest(partner_id=partner.partner_id)
    service = AdminService(db_session, mock_redis)
    result = await service.get_partner_report(request)

    assert result["summary"]["total_requests"] == 3
    assert result["summary"]["success_count"] == 2
    assert result["summary"]["fail_count"] == 1
    assert result["summary"]["issue_count"] == 2
    assert result["summary"]["idempotent_hit_count"] == 1

    assert len(result["daily"]) >= 1
    day = result["daily"][0]
    assert "error_distribution" in day
    assert day["error_distribution"].get("activity_ended") == 1


@pytest.mark.asyncio
async def test_idempotent_cache_uses_package_name(
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
        partner_id="test_partner_pkg",
        biz_serial_no="biz_pkg_name_001",
    )

    service = CouponService(db_session, mock_redis)
    result1 = await service.issue_coupon(request)

    assert result1.package_name == test_coupon_package.name
    assert result1.package_name != test_coupon_package.display_text

    mock_redis.hgetall = AsyncMock(return_value={})
    mock_redis.get = AsyncMock(return_value=None)

    result2 = await service.issue_coupon(request)
    assert result2.package_name == test_coupon_package.name
    assert result2.package_name == result1.package_name
    assert result2.coupon_code == result1.coupon_code
    assert result2.valid_start_time == result1.valid_start_time
    assert result2.valid_end_time == result1.valid_end_time


@pytest.mark.asyncio
async def test_stock_reconcile_issued_includes_used(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_coupon_skus: list,
) -> None:
    test_coupon_skus[0].status = 1
    test_coupon_skus[1].status = 2
    test_coupon_package.total_quantity = len(test_coupon_skus)
    test_coupon_package.claimed_quantity = 2
    await db_session.commit()

    service = AdminService(db_session, mock_redis)
    result = await service.get_stock_reconcile(test_activity.activity_id)

    pkg = result["packages"][0]
    assert pkg["sku_issued"] == 2
    assert pkg["sku_claimed_unused"] == 1
    assert pkg["sku_used"] == 1
    assert pkg["available"] == len(test_coupon_skus) - 2
    assert pkg["sku_issued"] == pkg["sku_claimed_unused"] + pkg["sku_used"]
    assert pkg["issued_vs_sku_issued_diff"] == 0


@pytest.mark.asyncio
async def test_stock_recalculate_issued_includes_used(
    db_session: AsyncSession,
    mock_redis: MagicMock,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_coupon_skus: list,
) -> None:
    test_coupon_skus[0].status = 1
    test_coupon_skus[1].status = 2
    test_coupon_package.total_quantity = 999
    test_coupon_package.claimed_quantity = 1
    await db_session.commit()

    service = AdminService(db_session, mock_redis)
    result = await service.recalculate_stock(test_activity.activity_id)

    pkg = result["recalculated_packages"][0]
    assert pkg["issued_quantity"]["after"] == 2
    assert pkg["issued_quantity"]["before"] == 1

    await db_session.refresh(test_coupon_package)
    assert test_coupon_package.claimed_quantity == 2


@pytest.mark.asyncio
async def test_partner_permission_check(
    db_session: AsyncSession,
) -> None:
    from app.api.partner_auth import check_partner_permission, PartnerAuthError

    partner = Partner(
        partner_id=f"partner_perm_{uuid.uuid4().hex[:8]}",
        name="权限测试",
        sign_key=uuid.uuid4().hex,
        allowed_activities="act_001,act_002",
        allowed_package_types="new_reader",
        status=1,
    )
    db_session.add(partner)
    await db_session.commit()
    await db_session.refresh(partner)

    await check_partner_permission(partner, "act_001", "new_reader", db_session)

    with pytest.raises(PartnerAuthError):
        await check_partner_permission(partner, "act_999", "new_reader", db_session)

    with pytest.raises(PartnerAuthError):
        await check_partner_permission(partner, "act_001", "vip_exclusive", db_session)


@pytest.mark.asyncio
async def test_partner_daily_limit(
    db_session: AsyncSession,
) -> None:
    from app.api.partner_auth import check_partner_daily_limit, PartnerAuthError

    partner = Partner(
        partner_id=f"partner_limit_{uuid.uuid4().hex[:8]}",
        name="限额测试",
        sign_key=uuid.uuid4().hex,
        daily_limit=2,
        status=1,
    )
    db_session.add(partner)
    await db_session.commit()
    await db_session.refresh(partner)

    now = datetime.now()
    for i in range(2):
        log = PartnerApiLog(
            log_id=f"palog_{uuid.uuid4().hex}",
            partner_id=partner.partner_id,
            api_path="/api/v1/coupon/issue",
            request_time=now,
            success=1,
        )
        db_session.add(log)
    await db_session.commit()

    with pytest.raises(PartnerAuthError):
        await check_partner_daily_limit(partner, db_session)
