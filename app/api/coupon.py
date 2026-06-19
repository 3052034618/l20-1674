import logging

import redis.asyncio as redis
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import CouponException, ERROR_MESSAGES
from app.db import get_db, get_redis
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


@router.post("/issue", response_model=IssueCouponResponse, summary="发券请求")
async def issue_coupon(
    request: IssueCouponRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> IssueCouponResponse:
    try:
        service = CouponService(db, redis_client)
        coupon_info = await service.issue_coupon(request)
        return IssueCouponResponse(
            success=True,
            code=200,
            message="发放成功",
            user_message="恭喜您，券包领取成功！",
            data=coupon_info,
        )
    except CouponException as e:
        logger.warning(f"Coupon issue failed: {e.message}, user_id={request.user_id}")
        return IssueCouponResponse(
            success=False,
            code=e.code,
            message=e.message,
            user_message=e.user_message,
            data=None,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in issue_coupon: {str(e)}")
        return IssueCouponResponse(
            success=False,
            code=500,
            message=str(e),
            user_message=ERROR_MESSAGES["system_error"],
            data=None,
        )


@router.post("/validate", response_model=ValidateCouponResponse, summary="资格校验")
async def validate_coupon(
    request: ValidateCouponRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> ValidateCouponResponse:
    try:
        service = CouponService(db, redis_client)
        result = await service.validate_eligibility(request)
        return ValidateCouponResponse(
            success=True,
            code=200,
            message="校验通过",
            user_message="您可以领取该券包",
            data=result,
        )
    except CouponException as e:
        logger.warning(f"Coupon validate failed: {e.message}, user_id={request.user_id}")
        return ValidateCouponResponse(
            success=False,
            code=e.code,
            message=e.message,
            user_message=e.user_message,
            data=None,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in validate_coupon: {str(e)}")
        return ValidateCouponResponse(
            success=False,
            code=500,
            message=str(e),
            user_message=ERROR_MESSAGES["system_error"],
            data=None,
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
