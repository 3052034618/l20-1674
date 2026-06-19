import hashlib
import hmac
import logging
import time
import uuid
from datetime import datetime
from typing import Any

import redis.asyncio as redis
from fastapi import Depends, Header, Query, Request
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import CouponActivityError, ERROR_MESSAGES
from app.db import get_db, get_redis
from app.models import Partner, PartnerApiLog

logger = logging.getLogger(__name__)


class PartnerAuthError(CouponActivityError):
    def __init__(self, message: str, error_key: str = "partner_auth_failed"):
        super().__init__(message=message, error_key=error_key)
        self.code = 401


class PartnerForbiddenError(CouponActivityError):
    def __init__(self, message: str, error_key: str = "partner_forbidden"):
        super().__init__(message=message, error_key=error_key)
        self.code = 403


class PartnerDailyLimitError(CouponActivityError):
    def __init__(self, message: str, error_key: str = "partner_daily_limit_reached"):
        super().__init__(message=message, error_key=error_key)
        self.code = 429


async def verify_partner_signature(
    request: Request,
    x_partner_id: str | None = Header(None, alias="X-Partner-Id", description="合作方标识"),
    x_timestamp: str | None = Header(None, alias="X-Timestamp", description="请求时间戳（秒）"),
    x_nonce: str | None = Header(None, alias="X-Nonce", description="随机字符串"),
    x_signature: str | None = Header(None, alias="X-Signature", description="签名"),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis | None = Depends(get_redis),
) -> Partner:
    if not x_partner_id or not x_timestamp or not x_nonce or not x_signature:
        raise PartnerAuthError(
            message="Missing required signature headers",
            error_key="signature_missing",
        )

    now = time.time()
    try:
        ts = float(x_timestamp)
    except ValueError:
        raise PartnerAuthError(
            message="Invalid timestamp format",
            error_key="signature_invalid",
        )

    if abs(now - ts) > 300:
        raise PartnerAuthError(
            message="Request timestamp expired",
            error_key="signature_expired",
        )

    stmt = select(Partner).where(
        and_(Partner.partner_id == x_partner_id, Partner.status == 1)
    )
    result = await db.execute(stmt)
    partner = result.scalar_one_or_none()

    if not partner:
        raise PartnerAuthError(
            message=f"Partner {x_partner_id} not found or disabled",
            error_key="partner_auth_failed",
        )

    body_bytes = b""
    if request.method in ("POST", "PUT", "PATCH"):
        body_bytes = await request.body()

    sign_base = f"{x_partner_id}\n{x_timestamp}\n{x_nonce}\n"
    message = sign_base.encode("utf-8") + body_bytes
    expected_sig = hmac.new(
        partner.sign_key.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, x_signature):
        raise PartnerAuthError(
            message="Invalid signature",
            error_key="signature_invalid",
        )

    return partner


async def check_partner_permission(
    partner: Partner,
    activity_id: str,
    package_type: str,
    db: AsyncSession,
) -> None:
    if partner.allowed_activities:
        allowed = [a.strip() for a in partner.allowed_activities.split(",") if a.strip()]
        if allowed and activity_id not in allowed:
            raise PartnerForbiddenError(
                message=f"Partner {partner.partner_id} not allowed to access activity {activity_id}",
                error_key="partner_forbidden",
            )

    if partner.allowed_package_types:
        allowed_types = [t.strip() for t in partner.allowed_package_types.split(",") if t.strip()]
        if allowed_types and package_type not in allowed_types:
            raise PartnerForbiddenError(
                message=f"Partner {partner.partner_id} not allowed to use package type {package_type}",
                error_key="partner_forbidden",
            )


async def check_partner_daily_limit(
    partner: Partner,
    db: AsyncSession,
) -> None:
    if partner.daily_limit <= 0:
        return

    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    stmt = select(func.count()).select_from(PartnerApiLog).where(
        and_(
            PartnerApiLog.partner_id == partner.partner_id,
            PartnerApiLog.success == 1,
            PartnerApiLog.api_path == "/api/v1/coupon/issue",
            PartnerApiLog.request_time >= today_start,
        )
    )
    count = (await db.execute(stmt)).scalar() or 0

    if count >= partner.daily_limit:
        raise PartnerDailyLimitError(
            message=f"Partner {partner.partner_id} daily limit {partner.daily_limit} reached",
            error_key="partner_daily_limit_reached",
        )


async def log_partner_api_call(
    db: AsyncSession,
    partner_id: str,
    api_path: str,
    success: bool,
    error_key: str = "",
    is_idempotent_hit: bool = False,
    activity_id: str = "",
    package_type: str = "",
) -> None:
    try:
        log = PartnerApiLog(
            log_id=f"palog_{uuid.uuid4().hex}",
            partner_id=partner_id,
            api_path=api_path,
            request_time=datetime.now(),
            success=1 if success else 0,
            error_key=error_key,
            is_idempotent_hit=1 if is_idempotent_hit else 0,
            activity_id=activity_id,
            package_type=package_type,
        )
        db.add(log)
        await db.commit()
    except Exception:
        logger.exception("Failed to log partner API call")
        try:
            await db.rollback()
        except Exception:
            pass
