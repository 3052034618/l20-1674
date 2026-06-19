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
    CreatePartnerRequest,
    CreatePartnerResponse,
    GenerateCouponCodesRequest,
    GenerateCouponCodesResponse,
    ImportCouponCodesRequest,
    ImportCouponCodesResponse,
    PackageListResponse,
    PackageStatsResponse,
    PartnerListResponse,
    PartnerReportRequest,
    PartnerReportResponse,
    ResetPartnerSignKeyResponse,
    StockReconcileResponse,
    StockRecalculateResponse,
    UpdateActivityStatusRequest,
    UpdateActivityStatusResponse,
    UpdatePartnerRequest,
    UpdatePartnerResponse,
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


@router.put("/activities/status", response_model=UpdateActivityStatusResponse, summary="更新活动状态")
async def update_activity_status(
    request: UpdateActivityStatusRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> UpdateActivityStatusResponse:
    try:
        service = AdminService(db, redis_client)
        result = await service.update_activity_status(request)
        action_labels = {"online": "上线", "pause": "暂停", "resume": "恢复", "end": "结束"}
        return UpdateActivityStatusResponse(
            success=True,
            code=200,
            message=f"活动{action_labels.get(request.action, request.action)}成功",
            user_message=f"活动{action_labels.get(request.action, request.action)}成功",
            data=result,
        )
    except CouponException as e:
        logger.warning(f"Update activity status failed: {e.message}, activity_id={request.activity_id}")
        return UpdateActivityStatusResponse(
            success=False,
            code=e.code,
            message=e.message,
            user_message=e.user_message,
            data=None,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in update_activity_status: {str(e)}")
        return UpdateActivityStatusResponse(
            success=False,
            code=500,
            message=str(e),
            user_message=ERROR_MESSAGES["system_error"],
            data=None,
        )


@router.get("/stock/reconcile", response_model=StockReconcileResponse, summary="库存对账")
async def stock_reconcile(
    activity_id: str = Query(..., description="活动编号"),
    package_type: str | None = Query(None, description="券包类型，可选"),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> StockReconcileResponse:
    try:
        service = AdminService(db, redis_client)
        result = await service.get_stock_reconcile(activity_id, package_type)
        return StockReconcileResponse(
            success=True,
            code=200,
            message="查询成功",
            user_message="",
            data=result,
        )
    except CouponException as e:
        logger.warning(f"Stock reconcile failed: {e.message}, activity_id={activity_id}")
        return StockReconcileResponse(
            success=False,
            code=e.code,
            message=e.message,
            user_message=e.user_message,
            data=None,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in stock_reconcile: {str(e)}")
        return StockReconcileResponse(
            success=False,
            code=500,
            message=str(e),
            user_message=ERROR_MESSAGES["system_error"],
            data=None,
        )


@router.post("/stock/recalculate", response_model=StockRecalculateResponse, summary="重新计算库存")
async def stock_recalculate(
    activity_id: str = Query(..., description="活动编号"),
    package_type: str | None = Query(None, description="券包类型，可选"),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> StockRecalculateResponse:
    try:
        service = AdminService(db, redis_client)
        result = await service.recalculate_stock(activity_id, package_type)
        return StockRecalculateResponse(
            success=True,
            code=200,
            message="库存重算完成",
            user_message="库存重算完成",
            data=result,
        )
    except CouponException as e:
        logger.warning(f"Stock recalculate failed: {e.message}, activity_id={activity_id}")
        return StockRecalculateResponse(
            success=False,
            code=e.code,
            message=e.message,
            user_message=e.user_message,
            data=None,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in stock_recalculate: {str(e)}")
        return StockRecalculateResponse(
            success=False,
            code=500,
            message=str(e),
            user_message=ERROR_MESSAGES["system_error"],
            data=None,
        )


@router.post("/partners", response_model=CreatePartnerResponse, summary="创建合作方")
async def create_partner(
    request: CreatePartnerRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> CreatePartnerResponse:
    try:
        service = AdminService(db, redis_client)
        result = await service.create_partner(request)
        return CreatePartnerResponse(
            success=True,
            code=200,
            message="合作方创建成功",
            user_message="合作方创建成功",
            data=result,
        )
    except CouponException as e:
        logger.warning(f"Create partner failed: {e.message}")
        return CreatePartnerResponse(
            success=False,
            code=e.code,
            message=e.message,
            user_message=e.user_message,
            data=None,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in create_partner: {str(e)}")
        return CreatePartnerResponse(
            success=False,
            code=500,
            message=str(e),
            user_message=ERROR_MESSAGES["system_error"],
            data=None,
        )


@router.get("/partners", response_model=PartnerListResponse, summary="查询合作方列表")
async def list_partners(
    skip: int = Query(0, description="分页偏移", ge=0),
    limit: int = Query(100, description="每页数量", ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> PartnerListResponse:
    try:
        service = AdminService(db, redis_client)
        result = await service.list_partners(skip, limit)
        return PartnerListResponse(
            success=True,
            code=200,
            message="查询成功",
            user_message="",
            data=result,
        )
    except CouponException as e:
        logger.warning(f"List partners failed: {e.message}")
        return PartnerListResponse(
            success=False,
            code=e.code,
            message=e.message,
            user_message=e.user_message,
            data=None,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in list_partners: {str(e)}")
        return PartnerListResponse(
            success=False,
            code=500,
            message=str(e),
            user_message=ERROR_MESSAGES["system_error"],
            data=None,
        )


@router.put("/partners", response_model=UpdatePartnerResponse, summary="更新合作方")
async def update_partner(
    request: UpdatePartnerRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> UpdatePartnerResponse:
    try:
        service = AdminService(db, redis_client)
        result = await service.update_partner(request)
        return UpdatePartnerResponse(
            success=True,
            code=200,
            message="更新成功",
            user_message="更新成功",
            data=result,
        )
    except CouponException as e:
        logger.warning(f"Update partner failed: {e.message}")
        return UpdatePartnerResponse(
            success=False,
            code=e.code,
            message=e.message,
            user_message=e.user_message,
            data=None,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in update_partner: {str(e)}")
        return UpdatePartnerResponse(
            success=False,
            code=500,
            message=str(e),
            user_message=ERROR_MESSAGES["system_error"],
            data=None,
        )


@router.post("/partners/{partner_id}/reset-key", response_model=ResetPartnerSignKeyResponse, summary="重置合作方签名密钥")
async def reset_partner_sign_key(
    partner_id: str,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> ResetPartnerSignKeyResponse:
    try:
        service = AdminService(db, redis_client)
        result = await service.reset_partner_sign_key(partner_id)
        return ResetPartnerSignKeyResponse(
            success=True,
            code=200,
            message="密钥重置成功",
            user_message="密钥重置成功",
            data=result,
        )
    except CouponException as e:
        logger.warning(f"Reset partner sign key failed: {e.message}, partner_id={partner_id}")
        return ResetPartnerSignKeyResponse(
            success=False,
            code=e.code,
            message=e.message,
            user_message=e.user_message,
            data=None,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in reset_partner_sign_key: {str(e)}")
        return ResetPartnerSignKeyResponse(
            success=False,
            code=500,
            message=str(e),
            user_message=ERROR_MESSAGES["system_error"],
            data=None,
        )


@router.post("/partners/report", response_model=PartnerReportResponse, summary="合作方调用报表")
async def get_partner_report(
    request: PartnerReportRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> PartnerReportResponse:
    try:
        service = AdminService(db, redis_client)
        result = await service.get_partner_report(request)
        return PartnerReportResponse(
            success=True,
            code=200,
            message="查询成功",
            user_message="",
            data=result,
        )
    except CouponException as e:
        logger.warning(f"Get partner report failed: {e.message}, partner_id={request.partner_id}")
        return PartnerReportResponse(
            success=False,
            code=e.code,
            message=e.message,
            user_message=e.user_message,
            data=None,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in get_partner_report: {str(e)}")
        return PartnerReportResponse(
            success=False,
            code=500,
            message=str(e),
            user_message=ERROR_MESSAGES["system_error"],
            data=None,
        )
