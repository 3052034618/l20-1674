from fastapi import APIRouter

from .coupon import router as coupon_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(coupon_router, prefix="/coupons", tags=["券包发放"])

__all__ = ["api_router"]
