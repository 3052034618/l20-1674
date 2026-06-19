import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api import api_router
from app.api.partner_auth import PartnerAuthError, PartnerDailyLimitError, PartnerForbiddenError
from app.config import settings
from app.core import CouponException, ERROR_MESSAGES
from app.db import close_redis, init_redis
from app.db.session import Base, engine


def setup_logging() -> None:
    log_dir = os.path.dirname(settings.LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(settings.LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info(f"Starting {settings.APP_NAME}...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized")

    try:
        await init_redis()
        logger.info("Redis connected")
    except Exception as e:
        logger.warning(f"Redis connection failed, running without cache: {e}")

    yield

    await close_redis()
    logger.info(f"{settings.APP_NAME} shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        description="漫画阅读平台券包发放后端服务",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.APP_DEBUG else None,
        redoc_url="/redoc" if settings.APP_DEBUG else None,
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc):
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "code": 400,
                "message": "请求参数验证失败",
                "user_message": ERROR_MESSAGES["invalid_request"],
                "data": None,
            },
        )

    @app.exception_handler(PartnerAuthError)
    async def partner_auth_exception_handler(request, exc):
        return JSONResponse(
            status_code=exc.code,
            content={
                "success": False,
                "code": exc.code,
                "message": exc.message,
                "user_message": exc.user_message,
                "data": None,
            },
        )

    @app.exception_handler(PartnerForbiddenError)
    async def partner_forbidden_exception_handler(request, exc):
        return JSONResponse(
            status_code=exc.code,
            content={
                "success": False,
                "code": exc.code,
                "message": exc.message,
                "user_message": exc.user_message,
                "data": None,
            },
        )

    @app.exception_handler(PartnerDailyLimitError)
    async def partner_daily_limit_exception_handler(request, exc):
        return JSONResponse(
            status_code=exc.code,
            content={
                "success": False,
                "code": exc.code,
                "message": exc.message,
                "user_message": exc.user_message,
                "data": None,
            },
        )

    @app.exception_handler(CouponException)
    async def coupon_exception_handler(request, exc):
        return JSONResponse(
            status_code=exc.code,
            content={
                "success": False,
                "code": exc.code,
                "message": exc.message,
                "user_message": exc.user_message,
                "data": None,
            },
        )

    @app.get("/health", summary="健康检查")
    async def health_check():
        return {"status": "ok", "app": settings.APP_NAME, "version": "1.0.0"}

    app.include_router(api_router)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.APP_DEBUG,
    )
