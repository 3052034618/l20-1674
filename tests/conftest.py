import asyncio
from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from faker import Faker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core import ActivityStatus, CouponType, MemberLevel
from app.db.session import Base
from app.models import (
    Activity,
    CouponPackage,
    CouponPackageSku,
    User,
)

fake = Faker("zh_CN")

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None, None]:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
def mock_redis() -> MagicMock:
    mock = MagicMock()
    mock.get = AsyncMock(return_value=None)
    mock.setex = AsyncMock()
    mock.set = AsyncMock()
    mock.decr = AsyncMock(return_value=100)
    mock.expire = AsyncMock()
    mock.hgetall = AsyncMock(return_value={})
    mock.hset = AsyncMock()
    mock.delete = AsyncMock()
    return mock


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    user = User(
        user_id=f"user_{fake.uuid4()[:8]}",
        nickname=fake.name(),
        member_level=MemberLevel.FREE.value,
        region="CN",
        is_new_reader=1,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_vip_user(db_session: AsyncSession) -> User:
    user = User(
        user_id=f"vip_{fake.uuid4()[:8]}",
        nickname=fake.name(),
        member_level=MemberLevel.GOLD.value,
        region="CN",
        is_new_reader=0,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_activity(db_session: AsyncSession) -> Activity:
    now = datetime.now()
    activity = Activity(
        activity_id=f"act_{fake.uuid4()[:8]}",
        name="新读者福利活动",
        description="新读者专享券包",
        status=ActivityStatus.ONGOING.value,
        start_time=now - timedelta(days=1),
        end_time=now + timedelta(days=30),
        allowed_regions="",
        min_member_level=MemberLevel.FREE.value,
        require_new_reader=1,
    )
    db_session.add(activity)
    await db_session.commit()
    await db_session.refresh(activity)
    return activity


@pytest_asyncio.fixture
async def test_vip_activity(db_session: AsyncSession) -> Activity:
    now = datetime.now()
    activity = Activity(
        activity_id=f"vip_{fake.uuid4()[:8]}",
        name="会员专享活动",
        description="黄金会员专享",
        status=ActivityStatus.ONGOING.value,
        start_time=now - timedelta(days=1),
        end_time=now + timedelta(days=30),
        allowed_regions="CN",
        min_member_level=MemberLevel.GOLD.value,
        require_new_reader=0,
    )
    db_session.add(activity)
    await db_session.commit()
    await db_session.refresh(activity)
    return activity


@pytest_asyncio.fixture
async def test_coupon_package(
    db_session: AsyncSession, test_activity: Activity) -> CouponPackage:
    package = CouponPackage(
        package_id=f"pkg_{fake.uuid4()[:8]}",
        activity_id=test_activity.activity_id,
        name="新读者礼包",
        type=CouponType.NEW_READER.value,
        display_text="恭喜获得100阅点漫画券包",
        valid_days=30,
        applicable_comics="1001,1002,1003",
        comic_categories="热血,恋爱",
        discount_value=1000,
        discount_type="fixed",
        total_quantity=100,
        claimed_quantity=0,
    )
    db_session.add(package)
    await db_session.commit()
    await db_session.refresh(package)
    return package


@pytest_asyncio.fixture
async def test_vip_coupon_package(
    db_session: AsyncSession, test_vip_activity: Activity) -> CouponPackage:
    package = CouponPackage(
        package_id=f"vip_pkg_{fake.uuid4()[:8]}",
        activity_id=test_vip_activity.activity_id,
        name="黄金会员礼包",
        type=CouponType.MEMBER_EXCLUSIVE.value,
        display_text="黄金会员专享500阅点",
        valid_days=15,
        applicable_comics="2001,2002",
        comic_categories="全部",
        discount_value=5000,
        discount_type="fixed",
        total_quantity=50,
        claimed_quantity=0,
    )
    db_session.add(package)
    await db_session.commit()
    await db_session.refresh(package)
    return package


@pytest_asyncio.fixture
async def test_coupon_skus(
    db_session: AsyncSession, test_coupon_package: CouponPackage) -> list[CouponPackageSku]:
    skus = []
    now = datetime.now()
    for i in range(10):
        sku = CouponPackageSku(
            sku_id=f"sku_{fake.uuid4()[:8]}",
            package_id=test_coupon_package.package_id,
            coupon_code=f"CODE{fake.uuid4()[:12].upper()}",
            status=0,
            expire_time=now + timedelta(days=60),
        )
        skus.append(sku)
        db_session.add(sku)
    await db_session.commit()
    return skus


@pytest_asyncio.fixture
async def test_vip_coupon_skus(
    db_session: AsyncSession, test_vip_coupon_package: CouponPackage) -> list[CouponPackageSku]:
    skus = []
    now = datetime.now()
    for i in range(5):
        sku = CouponPackageSku(
            sku_id=f"vip_sku_{fake.uuid4()[:8]}",
            package_id=test_vip_coupon_package.package_id,
            coupon_code=f"VIP{fake.uuid4()[:12].upper()}",
            status=0,
            expire_time=now + timedelta(days=60),
        )
        skus.append(sku)
        db_session.add(sku)
    await db_session.commit()
    return skus


@pytest_asyncio.fixture
async def setup_test_data(
    db_session: AsyncSession,
    test_user: User,
    test_vip_user: User,
    test_activity: Activity,
    test_vip_activity: Activity,
    test_coupon_package: CouponPackage,
    test_vip_coupon_package: CouponPackage,
    test_coupon_skus: list[CouponPackageSku],
    test_vip_coupon_skus: list[CouponPackageSku],
) -> dict[str, Any]:
    return {
        "user": test_user,
        "vip_user": test_vip_user,
        "activity": test_activity,
        "vip_activity": test_vip_activity,
        "package": test_coupon_package,
        "vip_package": test_vip_coupon_package,
        "skus": test_coupon_skus,
        "vip_skus": test_vip_coupon_skus,
    }
