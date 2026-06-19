"""
API调用示例
展示如何使用三个核心接口
"""
import asyncio
import json
import time

import httpx

BASE_URL = "http://localhost:8000"


async def example_validate_coupon():
    """资格校验接口示例"""
    print("=" * 60)
    print("示例1: 资格校验接口 - 检查新用户是否可以领取新读者礼包")
    print("=" * 60)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/coupons/validate",
            json={
                "user_id": "test_user_001",
                "activity_id": "act_new_reader_2024",
                "package_type": "new_reader",
                "trigger_scene": "member_center",
            },
        )
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))

        if data["success"]:
            print("\n✓ 校验通过，可以领取")
            print(f"  剩余库存: {data['data']['remaining_stock']}")
            print(f"  券包名称: {data['data']['package_name']}")
        else:
            print(f"\n✗ 校验失败: {data['user_message']}")

    return data


async def example_issue_coupon():
    """发券请求接口示例"""
    print("\n" + "=" * 60)
    print("示例2: 发券请求接口 - 新用户领取新读者礼包")
    print("=" * 60)

    request_id = f"req_{int(time.time() * 1000)}"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/coupons/issue",
            json={
                "user_id": "test_user_001",
                "activity_id": "act_new_reader_2024",
                "package_type": "new_reader",
                "trigger_scene": "member_center",
                "request_id": request_id,
            },
        )
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))

        if data["success"]:
            print("\n✓ 发放成功!")
            print(f"  券码: {data['data']['coupon_code']}")
            print(f"  展示文案: {data['data']['display_text']}")
            print(f"  有效期: {data['data']['valid_start_time']} ~ {data['data']['valid_end_time']}")
            print(f"  适用作品: {data['data']['applicable_comics']}")
            return data["data"]["record_id"]
        else:
            print(f"\n✗ 发放失败: {data['user_message']}")
            return None


async def example_issue_coupon_already_claimed():
    """重复领取测试"""
    print("\n" + "=" * 60)
    print("示例3: 重复领取测试 - 已领过的用户再次领取")
    print("=" * 60)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/coupons/issue",
            json={
                "user_id": "test_user_001",
                "activity_id": "act_new_reader_2024",
                "package_type": "new_reader",
                "trigger_scene": "member_center",
            },
        )
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"\n结果: {data['user_message']}")


async def example_issue_coupon_not_eligible():
    """资格不符测试"""
    print("\n" + "=" * 60)
    print("示例4: 资格不符测试 - 老用户尝试领取新读者礼包")
    print("=" * 60)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/coupons/issue",
            json={
                "user_id": "test_user_002",
                "activity_id": "act_new_reader_2024",
                "package_type": "new_reader",
                "trigger_scene": "member_center",
            },
        )
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"\n结果: {data['user_message']}")


async def example_validate_vip_activity():
    """会员活动测试"""
    print("\n" + "=" * 60)
    print("示例5: 会员活动测试 - 免费会员尝试领取黄金会员礼包")
    print("=" * 60)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/coupons/validate",
            json={
                "user_id": "test_user_001",
                "activity_id": "act_vip_summer_2024",
                "package_type": "member_exclusive",
                "trigger_scene": "member_center",
            },
        )
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"\n结果: {data['user_message']}")


async def example_callback_behavior(record_id: str | None):
    """行为回传接口示例"""
    print("\n" + "=" * 60)
    print("示例6: 行为回传接口 - 记录展示、点击、使用行为")
    print("=" * 60)

    behaviors = [
        ("impression", "展示", {"position": "banner_top", "device": "ios"}),
        ("click", "点击", {"source": "home_page", "button": "claim_btn"}),
    ]

    if record_id:
        behaviors.append(("use", "使用", {"comic_id": "1001", "chapter_id": "5001", "order_id": "ord_12345"}))

    async with httpx.AsyncClient() as client:
        for behavior_type, desc, extra in behaviors:
            response = await client.post(
                f"{BASE_URL}/api/v1/coupons/callback",
                json={
                    "user_id": "test_user_001",
                    "activity_id": "act_new_reader_2024",
                    "package_id": "pkg_new_reader_001",
                    "user_coupon_id": record_id or "",
                    "behavior_type": behavior_type,
                    "trigger_scene": "member_center",
                    "extra": extra,
                },
            )
            data = response.json()
            print(f"{desc}: {'成功' if data['success'] else '失败'} - {json.dumps(data, ensure_ascii=False)}")


async def example_validate_region_restricted():
    """地区限制测试"""
    print("\n" + "=" * 60)
    print("示例7: 地区限制测试 - 海外用户尝试领取仅限国内的活动")
    print("=" * 60)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/coupons/validate",
            json={
                "user_id": "test_user_003",
                "activity_id": "act_vip_summer_2024",
                "package_type": "member_exclusive",
                "trigger_scene": "member_center",
            },
        )
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"\n结果: {data['user_message']}")


async def main():
    print("漫画券包发放服务 API 调用示例")
    print(f"服务地址: {BASE_URL}")
    print("请确保服务已启动: python run.py")
    print("请确保已初始化测试数据: python scripts/init_test_data.py")
    print()

    try:
        async with httpx.AsyncClient() as client:
            health = await client.get(f"{BASE_URL}/health")
            if health.status_code != 200:
                print("❌ 服务未启动，请先启动服务")
                return
            print("✅ 服务连接正常")
    except Exception as e:
        print(f"❌ 无法连接到服务: {e}")
        return

    await example_validate_coupon()
    record_id = await example_issue_coupon()
    await example_issue_coupon_already_claimed()
    await example_issue_coupon_not_eligible()
    await example_validate_vip_activity()
    await example_validate_region_restricted()
    await example_callback_behavior(record_id)

    print("\n" + "=" * 60)
    print("所有示例执行完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
