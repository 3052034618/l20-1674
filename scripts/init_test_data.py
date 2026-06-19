"""初始化测试数据脚本，用于开发环境快速搭建测试数据"""
import asyncio
import sys
import uuid
from datetime import datetime, timedelta

sys.path.insert(0, ".")

from app.core import ActivityStatus, CouponType, MemberLevel
from app.db.session import AsyncSessionLocal, Base, engine
from app.models import (
    Activity,
    CouponPackage,
    CouponPackageSku,
    User,
)


async def init_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created successfully")


async def create_test_data():
    async with AsyncSessionLocal() as db:
        now = datetime.now()

        user1 = User(
            user_id="test_user_001",
            nickname="新用户小明",
            member_level=MemberLevel.FREE.value,
            region="CN",
            is_new_reader=1,
        )
        user2 = User(
            user_id="test_user_002",
            nickname="黄金会员小红",
            member_level=MemberLevel.GOLD.value,
            region="CN",
            is_new_reader=0,
        )
        user3 = User(
            user_id="test_user_003",
            nickname="海外用户Tom",
            member_level=MemberLevel.SILVER.value,
            region="US",
            is_new_reader=0,
        )
        db.add_all([user1, user2, user3])
        await db.flush()
        print("Created 3 test users")

        activity1 = Activity(
            activity_id="act_new_reader_2024",
            name="新读者专属福利",
            description="新用户注册专享100阅点大礼包",
            status=ActivityStatus.ONGOING.value,
            start_time=now - timedelta(days=1),
            end_time=now + timedelta(days=30),
            allowed_regions="",
            min_member_level=MemberLevel.FREE.value,
            require_new_reader=1,
        )
        activity2 = Activity(
            activity_id="act_vip_summer_2024",
            name="暑期会员专享活动",
            description="黄金及以上会员专享500阅点",
            status=ActivityStatus.ONGOING.value,
            start_time=now - timedelta(days=1),
            end_time=now + timedelta(days=60),
            allowed_regions="CN",
            min_member_level=MemberLevel.GOLD.value,
            require_new_reader=0,
        )
        activity3 = Activity(
            activity_id="act_cobrand_bank_2024",
            name="银行联名活动",
            description="XX银行联名专属活动",
            status=ActivityStatus.ONGOING.value,
            start_time=now - timedelta(days=1),
            end_time=now + timedelta(days=90),
            allowed_regions="CN",
            min_member_level=MemberLevel.FREE.value,
            require_new_reader=0,
        )
        db.add_all([activity1, activity2, activity3])
        await db.flush()
        print("Created 3 test activities")

        pkg1 = CouponPackage(
            package_id="pkg_new_reader_001",
            activity_id=activity1.activity_id,
            name="新读者100阅点礼包",
            type=CouponType.NEW_READER.value,
            display_text="恭喜获得100阅点漫画券包",
            valid_days=30,
            applicable_comics="1001,1002,1003,1004,1005",
            comic_categories="热血,恋爱,悬疑",
            discount_value=1000,
            discount_type="fixed",
            total_quantity=10000,
            claimed_quantity=0,
        )
        pkg2 = CouponPackage(
            package_id="pkg_vip_500_001",
            activity_id=activity2.activity_id,
            name="黄金会员500阅点礼包",
            type=CouponType.MEMBER_EXCLUSIVE.value,
            display_text="黄金会员专享500阅点",
            valid_days=15,
            applicable_comics="2001,2002,2003,2004,2005,2006",
            comic_categories="全部",
            discount_value=5000,
            discount_type="fixed",
            total_quantity=5000,
            claimed_quantity=0,
        )
        pkg3 = CouponPackage(
            package_id="pkg_cobrand_1000_001",
            activity_id=activity3.activity_id,
            name="银行联名1000阅点礼包",
            type=CouponType.CO_BRAND.value,
            display_text="XX银行用户专享1000阅点",
            valid_days=60,
            applicable_comics="3001,3002,3003",
            comic_categories="都市,科幻",
            discount_value=10000,
            discount_type="fixed",
            total_quantity=2000,
            claimed_quantity=0,
        )
        db.add_all([pkg1, pkg2, pkg3])
        await db.flush()
        print("Created 3 test coupon packages")

        skus = []
        for pkg in [pkg1, pkg2, pkg3]:
            for i in range(10):
                sku = CouponPackageSku(
                    sku_id=f"sku_{uuid.uuid4().hex[:12]}",
                    package_id=pkg.package_id,
                    coupon_code=f"{pkg.package_id[:3].upper()}{uuid.uuid4().hex[:12].upper()}",
                    status=0,
                    expire_time=now + timedelta(days=180),
                )
                skus.append(sku)
        db.add_all(skus)
        await db.flush()
        print(f"Created {len(skus)} test coupon SKUs")

        await db.commit()
        print("All test data created successfully!")

        print("\n" + "="*60)
        print("测试数据概览:")
        print("="*60)
        print(f"用户: test_user_001 (新用户, 免费会员, CN)")
        print(f"用户: test_user_002 (黄金会员, CN)")
        print(f"用户: test_user_003 (白银会员, US)")
        print()
        print(f"活动: act_new_reader_2024 (新读者专属, 仅限新用户)")
        print(f"活动: act_vip_summer_2024 (会员专享, 黄金+, CN地区)")
        print(f"活动: act_cobrand_bank_2024 (银行联名, CN地区)")
        print("="*60)


async def main():
    await init_database()
    await create_test_data()


if __name__ == "__main__":
    asyncio.run(main())
