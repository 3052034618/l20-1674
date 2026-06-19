import logging

import redis.asyncio as redis
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.partner_auth import (
    PartnerAuthError,
    PartnerDailyLimitError,
    PartnerForbiddenError,
    check_partner_daily_limit,
    check_partner_permission,
    log_partner_api_call,
    verify_partner_signature,
)
from app.core import CouponException, ERROR_MESSAGES
from app.db import get_db, get_redis
from app.models import Partner
from app.schemas import (
    CouponCallbackRequest,
    CouponCallbackResponse,
    IssueCouponRequest,
    IssueCouponResponse,
    ValidateCouponRequest,
    ValidateCouponResponse,
)
from app.services import CouponService

logger = logging.getLogger(__name__)

router = APIRouter()


def _extract_error_key(exc: CouponException) -> str:
    if hasattr(exc, "error_key"):
        return exc.error_key
    exc_cls = type(exc).__name__
    mapping = {
        "CouponAlreadyClaimedError": "already_claimed",
        "CouponStockError": "stock_insufficient",
        "CouponEligibilityError": "not_eligible",
        "CouponActivityError": "activity_error",
        "CouponUserError": "user_error",
    }
    return mapping.get(exc_cls, "unknown")


@router.post("/issue", response_model=IssueCouponResponse, summary="发券请求")
async def issue_coupon(
    request: Request,
    body: IssueCouponRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
    partner: Partner = Depends(verify_partner_signature),
) -> IssueCouponResponse:
    api_path = "/api/v1/coupon/issue"
    activity_id = body.activity_id
    package_type = body.package_type.value if body.package_type else ""
    is_idempotent_hit = False

    try:
        await check_partner_permission(partner, activity_id, package_type, db)
        await check_partner_daily_limit(partner, db)

        service = CouponService(db, redis_client)
        coupon_info = await service.issue_coupon(body)

        if partner.partner_id and body.biz_serial_no:
            idempotent_key = f"coupon:idempotent:biz:{partner.partner_id}:{body.biz_serial_no}"
            if redis_client:
                cached = await redis_client.hgetall(idempotent_key)
                if cached and cached.get("record_id") != coupon_info.record_id:
                    is_idempotent_hit = True

        await log_partner_api_call(
            db, partner.partner_id, api_path,
            success=True,
            is_idempotent_hit=is_idempotent_hit,
            activity_id=activity_id,
            package_type=package_type,
        )

        return IssueCouponResponse(
            success=True,
            code=200,
            message="发放成功",
            user_message="恭喜您，券包领取成功！",
            data=coupon_info,
        )
    except (PartnerAuthError, PartnerForbiddenError, PartnerDailyLimitError) as e:
        await log_partner_api_call(
            db, partner.partner_id, api_path,
            success=False, error_key=e.error_key,
            activity_id=activity_id, package_type=package_type,
        )
        return IssueCouponResponse(
            success=False, code=e.code,
            message=e.message, user_message=e.user_message, data=None,
        )
    except CouponException as e:
        await log_partner_api_call(
            db, partner.partner_id, api_path,
            success=False, error_key=_extract_error_key(e),
            activity_id=activity_id, package_type=package_type,
        )
        return IssueCouponResponse(
            success=False, code=e.code,
            message=e.message, user_message=e.user_message, data=None,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in issue_coupon: {str(e)}")
        await log_partner_api_call(
            db, partner.partner_id, api_path,
            success=False, error_key="system_error",
            activity_id=activity_id, package_type=package_type,
        )
        return IssueCouponResponse(
            success=False, code=500,
            message=str(e), user_message=ERROR_MESSAGES["system_error"], data=None,
        )


@router.post("/validate", response_model=ValidateCouponResponse, summary="资格校验")
async def validate_coupon(
    request: Request,
    body: ValidateCouponRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
    partner: Partner = Depends(verify_partner_signature),
) -> ValidateCouponResponse:
    api_path = "/api/v1/coupon/validate"
    activity_id = body.activity_id
    package_type = body.package_type.value if body.package_type else ""

    try:
        await check_partner_permission(partner, activity_id, package_type, db)

        service = CouponService(db, redis_client)
        result = await service.validate_eligibility(body)

        await log_partner_api_call(
            db, partner.partner_id, api_path,
            success=True,
            activity_id=activity_id, package_type=package_type,
        )

        return ValidateCouponResponse(
            success=True,
            code=200,
            message="校验通过",
            user_message="您可以领取该券包",
            data=result,
        )
    except (PartnerAuthError, PartnerForbiddenError) as e:
        await log_partner_api_call(
            db, partner.partner_id, api_path,
            success=False, error_key=e.error_key,
            activity_id=activity_id, package_type=package_type,
        )
        return ValidateCouponResponse(
            success=False, code=e.code,
            message=e.message, user_message=e.user_message, data=None,
        )
    except CouponException as e:
        await log_partner_api_call(
            db, partner.partner_id, api_path,
            success=False, error_key=_extract_error_key(e),
            activity_id=activity_id, package_type=package_type,
        )
        return ValidateCouponResponse(
            success=False, code=e.code,
            message=e.message, user_message=e.user_message, data=None,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in validate_coupon: {str(e)}")
        await log_partner_api_call(
            db, partner.partner_id, api_path,
            success=False, error_key="system_error",
            activity_id=activity_id, package_type=package_type,
        )
        return ValidateCouponResponse(
            success=False, code=500,
            message=str(e), user_message=ERROR_MESSAGES["system_error"], data=None,
        )


@router.post("/callback", response_model=CouponCallbackResponse, summary="结果回传")
async def callback_coupon(
    request: CouponCallbackRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> CouponCallbackResponse:
    try:
        service = CouponService(db, redis_client)
        await service.record_behavior(request)
        return CouponCallbackResponse(
            success=True,
            code=200,
            message="记录成功",
            user_message="",
            data=None,
        )
    except CouponException as e:
        logger.warning(f"Coupon callback failed: {e.message}, user_id={request.user_id}")
        return CouponCallbackResponse(
            success=False,
            code=e.code,
            message=e.message,
            user_message=e.user_message,
            data=None,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in callback_coupon: {str(e)}")
        return CouponCallbackResponse(
            success=False,
            code=500,
            message=str(e),
            user_message=ERROR_MESSAGES["system_error"],
            data=None,
        )
