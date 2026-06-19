from fastapi import APIRouter

from .admin import router as admin_router
from .coupon import router as coupon_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(coupon_router, prefix="/coupons", tags=["券包发放"])
api_router.include_router(admin_router, tags=["管理接口"])

__all__ = ["api_router"]
