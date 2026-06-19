from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.partner_auth import verify_partner_signature
from app.core import (
    ActivityStatus,
    CouponType,
    TriggerScene,
    BehaviorType,
)
from app.db import get_db, get_redis
from app.main import app
from app.models import (
    Activity,
    CouponPackage,
    CouponPackageSku,
    Partner,
    User,
    UserCoupon,
)


@pytest.fixture
def client():
    return TestClient(app)


def create_mock_redis():
    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()
    mock_redis.set = AsyncMock()
    mock_redis.decr = AsyncMock(return_value=100)
    mock_redis.hgetall = AsyncMock(return_value={})
    mock_redis.hset = AsyncMock()
    mock_redis.expire = AsyncMock()
    mock_redis.delete = AsyncMock()
    return mock_redis


def create_mock_partner():
    partner = Partner(
        partner_id="test_partner",
        name="测试合作方",
        sign_key="test_key",
        allowed_activities="",
        allowed_package_types="",
        daily_limit=0,
        status=1,
    )
    partner.id = 0
    return partner


def override_dependencies(db_session: AsyncSession, mock_redis: MagicMock | None = None):
    if mock_redis is None:
        mock_redis = create_mock_redis()

    mock_partner = create_mock_partner()

    async def mock_get_redis():
        yield mock_redis

    async def mock_get_db():
        yield db_session

    async def mock_verify_partner():
        return mock_partner

    app.dependency_overrides[get_redis] = mock_get_redis
    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[verify_partner_signature] = mock_verify_partner


@pytest.mark.asyncio
async def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "1.0.0"


@pytest.mark.asyncio
async def test_issue_coupon_api_success(
    client: TestClient,
    db_session: AsyncSession,
    test_user: User,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_coupon_skus: list,
):
    mock_redis = create_mock_redis()
    override_dependencies(db_session, mock_redis)

    try:
        response = client.post(
            "/api/v1/coupons/issue",
            json={
                "user_id": test_user.user_id,
                "activity_id": test_activity.activity_id,
                "package_type": CouponType.NEW_READER.value,
                "trigger_scene": TriggerScene.MEMBER_CENTER.value,
                "request_id": "api_test_001",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["code"] == 200
        assert data["user_message"] == "恭喜您，券包领取成功！"
        assert data["data"] is not None
        assert data["data"]["package_id"] == test_coupon_package.package_id
        assert data["data"]["display_text"] == test_coupon_package.display_text
        assert len(data["data"]["applicable_comics"]) == 3
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_issue_coupon_api_already_claimed(
    client: TestClient,
    db_session: AsyncSession,
    test_user: User,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_coupon_skus: list,
):
    user_coupon = UserCoupon(
        record_id="api_test_claimed_001",
        user_id=test_user.user_id,
        activity_id=test_activity.activity_id,
        package_id=test_coupon_package.package_id,
        sku_id=test_coupon_skus[0].sku_id,
        coupon_code=test_coupon_skus[0].coupon_code,
        status=0,
        trigger_scene=TriggerScene.MEMBER_CENTER.value,
        valid_start_time=datetime.now(),
        valid_end_time=datetime.now() + timedelta(days=30),
        applicable_comics="1001,1002",
        display_text="测试",
    )
    db_session.add(user_coupon)
    await db_session.commit()

    override_dependencies(db_session)

    try:
        response = client.post(
            "/api/v1/coupons/issue",
            json={
                "user_id": test_user.user_id,
                "activity_id": test_activity.activity_id,
                "package_type": CouponType.NEW_READER.value,
                "trigger_scene": TriggerScene.MEMBER_CENTER.value,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["code"] == 409
        assert data["user_message"] == "已领过"
        assert data["data"] is None
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_issue_coupon_api_not_eligible_new_reader(
    client: TestClient,
    db_session: AsyncSession,
    test_vip_user: User,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_coupon_skus: list,
):
    test_activity.require_new_reader = 1
    await db_session.commit()

    override_dependencies(db_session)

    try:
        response = client.post(
            "/api/v1/coupons/issue",
            json={
                "user_id": test_vip_user.user_id,
                "activity_id": test_activity.activity_id,
                "package_type": CouponType.NEW_READER.value,
                "trigger_scene": TriggerScene.MEMBER_CENTER.value,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["code"] == 403
        assert data["user_message"] == "仅限新读者"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_validate_coupon_api_success(
    client: TestClient,
    db_session: AsyncSession,
    test_user: User,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
    test_coupon_skus: list,
):
    override_dependencies(db_session)

    try:
        response = client.post(
            "/api/v1/coupons/validate",
            json={
                "user_id": test_user.user_id,
                "activity_id": test_activity.activity_id,
                "package_type": CouponType.NEW_READER.value,
                "trigger_scene": TriggerScene.MEMBER_CENTER.value,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["code"] == 200
        assert data["user_message"] == "您可以领取该券包"
        assert data["data"]["eligible"] is True
        assert data["data"]["remaining_stock"] == len(test_coupon_skus)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_validate_coupon_api_member_level_insufficient(
    client: TestClient,
    db_session: AsyncSession,
    test_user: User,
    test_vip_activity: Activity,
    test_vip_coupon_package: CouponPackage,
):
    override_dependencies(db_session)

    try:
        response = client.post(
            "/api/v1/coupons/validate",
            json={
                "user_id": test_user.user_id,
                "activity_id": test_vip_activity.activity_id,
                "package_type": CouponType.MEMBER_EXCLUSIVE.value,
                "trigger_scene": TriggerScene.MEMBER_CENTER.value,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["code"] == 403
        assert data["user_message"] == "会员等级不足"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_callback_coupon_api_impression(
    client: TestClient,
    db_session: AsyncSession,
    test_user: User,
    test_activity: Activity,
):
    override_dependencies(db_session)

    try:
        response = client.post(
            "/api/v1/coupons/callback",
            json={
                "user_id": test_user.user_id,
                "activity_id": test_activity.activity_id,
                "package_id": "pkg_001",
                "user_coupon_id": "",
                "behavior_type": BehaviorType.IMPRESSION.value,
                "trigger_scene": TriggerScene.MEMBER_CENTER.value,
                "extra": {"position": "banner_top"},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["code"] == 200
        assert data["message"] == "记录成功"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_callback_coupon_api_click(
    client: TestClient,
    db_session: AsyncSession,
    test_user: User,
    test_activity: Activity,
):
    override_dependencies(db_session)

    try:
        response = client.post(
            "/api/v1/coupons/callback",
            json={
                "user_id": test_user.user_id,
                "activity_id": test_activity.activity_id,
                "package_id": "pkg_001",
                "user_coupon_id": "uc_api_test_001",
                "behavior_type": BehaviorType.CLICK.value,
                "trigger_scene": TriggerScene.TASK_CENTER.value,
                "extra": {"source": "push_notification"},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["code"] == 200
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_issue_coupon_api_activity_ended(
    client: TestClient,
    db_session: AsyncSession,
    test_user: User,
    test_activity: Activity,
    test_coupon_package: CouponPackage,
):
    test_activity.status = ActivityStatus.ENDED.value
    await db_session.commit()

    override_dependencies(db_session)

    try:
        response = client.post(
            "/api/v1/coupons/issue",
            json={
                "user_id": test_user.user_id,
                "activity_id": test_activity.activity_id,
                "package_type": CouponType.NEW_READER.value,
                "trigger_scene": TriggerScene.MEMBER_CENTER.value,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["code"] == 412
        assert data["user_message"] == "活动已结束"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_validate_coupon_api_region_restricted(
    client: TestClient,
    db_session: AsyncSession,
    test_vip_user: User,
    test_vip_activity: Activity,
    test_vip_coupon_package: CouponPackage,
):
    test_vip_activity.allowed_regions = "US,UK"
    test_vip_user.region = "CN"
    await db_session.commit()

    override_dependencies(db_session)

    try:
        response = client.post(
            "/api/v1/coupons/validate",
            json={
                "user_id": test_vip_user.user_id,
                "activity_id": test_vip_activity.activity_id,
                "package_type": CouponType.MEMBER_EXCLUSIVE.value,
                "trigger_scene": TriggerScene.CO_BRAND.value,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["code"] == 403
        assert data["user_message"] == "当前地区不支持领取"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_issue_coupon_api_invalid_request(
    client: TestClient,
    db_session: AsyncSession,
):
    override_dependencies(db_session)

    try:
        response = client.post(
            "/api/v1/coupons/issue",
            json={
                "user_id": "",
                "activity_id": "act_001",
                "package_type": "invalid_type",
                "trigger_scene": "member_center",
            },
        )

        assert response.status_code == 400 or response.status_code == 422
        data = response.json()
        if "user_message" in data:
            assert data["user_message"] == "请求参数错误"
    finally:
        app.dependency_overrides.clear()
