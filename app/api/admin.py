import logging

import redis.asyncio as redis
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import CouponException, ERROR_MESSAGES
from app.db import get_db, get_redis
from app.schemas.admin import (
    ActivityListResponse,
    BehaviorStatsRequest,
    BehaviorStatsResponse,
    CreateActivityRequest,
    CreateActivityResponse,
    CreateCouponPackageRequest,
    CreateCouponPackageResponse,
    GenerateCouponCodesRequest,
    GenerateCouponCodesResponse,
    ImportCouponCodesRequest,
    ImportCouponCodesResponse,
    PackageListResponse,
    PackageStatsResponse,
)
from app.services.admin_service import AdminService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["管理接口"])


@router.post("/activities", response_model=CreateActivityResponse, summary="创建活动")
async def create_activity(
    request: CreateActivityRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> CreateActivityResponse:
    try:
        service = AdminService(db, redis_client)
        result = await service.create_activity(request)
        return CreateActivityResponse(
            success=True,
            code=200,
            message="活动创建成功",
            user_message="活动创建成功",
            data=result,
        )
    except CouponException as e:
        logger.warning(f"Create activity failed: {e.message}")
        return CreateActivityResponse(
            success=False,
            code=e.code,
            message=e.message,
            user_message=e.user_message,
            data=None,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in create_activity: {str(e)}")
        return CreateActivityResponse(
            success=False,
            code=500,
            message=str(e),
            user_message=ERROR_MESSAGES["system_error"],
            data=None,
        )


@router.get("/activities", response_model=ActivityListResponse, summary="查询活动列表")
async def list_activities(
    skip: int = Query(0, description="分页偏移", ge=0),
    limit: int = Query(100, description="每页数量", ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> ActivityListResponse:
    try:
        service = AdminService(db, redis_client)
        result = await service.list_activities(skip, limit)
        return ActivityListResponse(
            success=True,
            code=200,
            message="查询成功",
            user_message="",
            data=result,
        )
    except CouponException as e:
        logger.warning(f"List activities failed: {e.message}")
        return ActivityListResponse(
            success=False,
            code=e.code,
            message=e.message,
            user_message=e.user_message,
            data=None,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in list_activities: {str(e)}")
        return ActivityListResponse(
            success=False,
            code=500,
            message=str(e),
            user_message=ERROR_MESSAGES["system_error"],
            data=None,
        )


@router.post("/packages", response_model=CreateCouponPackageResponse, summary="创建券包")
async def create_package(
    request: CreateCouponPackageRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> CreateCouponPackageResponse:
    try:
        service = AdminService(db, redis_client)
        result = await service.create_coupon_package(request)
        return CreateCouponPackageResponse(
            success=True,
            code=200,
            message="券包创建成功",
            user_message="券包创建成功",
            data=result,
        )
    except CouponException as e:
        logger.warning(f"Create package failed: {e.message}")
        return CreateCouponPackageResponse(
            success=False,
            code=e.code,
            message=e.message,
            user_message=e.user_message,
            data=None,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in create_package: {str(e)}")
        return CreateCouponPackageResponse(
            success=False,
            code=500,
            message=str(e),
            user_message=ERROR_MESSAGES["system_error"],
            data=None,
        )


@router.get("/packages", response_model=PackageListResponse, summary="查询券包列表")
async def list_packages(
    activity_id: str | None = Query(None, description="活动编号，可选"),
    skip: int = Query(0, description="分页偏移", ge=0),
    limit: int = Query(100, description="每页数量", ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> PackageListResponse:
    try:
        service = AdminService(db, redis_client)
        result = await service.list_packages(activity_id, skip, limit)
        return PackageListResponse(
            success=True,
            code=200,
            message="查询成功",
            user_message="",
            data=result,
        )
    except CouponException as e:
        logger.warning(f"List packages failed: {e.message}")
        return PackageListResponse(
            success=False,
            code=e.code,
            message=e.message,
            user_message=e.user_message,
            data=None,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in list_packages: {str(e)}")
        return PackageListResponse(
            success=False,
            code=500,
            message=str(e),
            user_message=ERROR_MESSAGES["system_error"],
            data=None,
        )


@router.post("/packages/generate-codes", response_model=GenerateCouponCodesResponse, summary="生成券码")
async def generate_codes(
    request: GenerateCouponCodesRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> GenerateCouponCodesResponse:
    try:
        service = AdminService(db, redis_client)
        result = await service.generate_coupon_codes(request)
        return GenerateCouponCodesResponse(
            success=True,
            code=200,
            message=f"成功生成{result['generated_count']}个券码",
            user_message=f"成功生成{result['generated_count']}个券码",
            data=result,
        )
    except CouponException as e:
        logger.warning(f"Generate codes failed: {e.message}")
        return GenerateCouponCodesResponse(
            success=False,
            code=e.code,
            message=e.message,
            user_message=e.user_message,
            data=None,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in generate_codes: {str(e)}")
        return GenerateCouponCodesResponse(
            success=False,
            code=500,
            message=str(e),
            user_message=ERROR_MESSAGES["system_error"],
            data=None,
        )


@router.post("/packages/import-codes", response_model=ImportCouponCodesResponse, summary="导入券码")
async def import_codes(
    request: ImportCouponCodesRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> ImportCouponCodesResponse:
    try:
        service = AdminService(db, redis_client)
        result = await service.import_coupon_codes(request)
        return ImportCouponCodesResponse(
            success=True,
            code=200,
            message=f"成功导入{result['imported_count']}个券码，重复{result['duplicate_count']}个",
            user_message=f"成功导入{result['imported_count']}个券码",
            data=result,
        )
    except CouponException as e:
        logger.warning(f"Import codes failed: {e.message}")
        return ImportCouponCodesResponse(
            success=False,
            code=e.code,
            message=e.message,
            user_message=e.user_message,
            data=None,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in import_codes: {str(e)}")
        return ImportCouponCodesResponse(
            success=False,
            code=500,
            message=str(e),
            user_message=ERROR_MESSAGES["system_error"],
            data=None,
        )


@router.get("/packages/{package_id}/stats", response_model=PackageStatsResponse, summary="查询券包统计")
async def get_package_stats(
    package_id: str,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> PackageStatsResponse:
    try:
        service = AdminService(db, redis_client)
        result = await service.get_package_stats(package_id)
        return PackageStatsResponse(
            success=True,
            code=200,
            message="查询成功",
            user_message="",
            data=result,
        )
    except CouponException as e:
        logger.warning(f"Get package stats failed: {e.message}, package_id={package_id}")
        return PackageStatsResponse(
            success=False,
            code=e.code,
            message=e.message,
            user_message=e.user_message,
            data=None,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in get_package_stats: {str(e)}")
        return PackageStatsResponse(
            success=False,
            code=500,
            message=str(e),
            user_message=ERROR_MESSAGES["system_error"],
            data=None,
        )


@router.post("/behavior-stats", response_model=BehaviorStatsResponse, summary="查询行为统计数据")
async def get_behavior_stats(
    request: BehaviorStatsRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> BehaviorStatsResponse:
    try:
        service = AdminService(db, redis_client)
        result = await service.get_behavior_stats(request)
        return BehaviorStatsResponse(
            success=True,
            code=200,
            message="查询成功",
            user_message="",
            data=result,
        )
    except CouponException as e:
        logger.warning(f"Get behavior stats failed: {e.message}, activity_id={request.activity_id}")
        return BehaviorStatsResponse(
            success=False,
            code=e.code,
            message=e.message,
            user_message=e.user_message,
            data=None,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in get_behavior_stats: {str(e)}")
        return BehaviorStatsResponse(
            success=False,
            code=500,
            message=str(e),
            user_message=ERROR_MESSAGES["system_error"],
            data=None,
        )
