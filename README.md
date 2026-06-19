# 漫画券包发放后端服务

面向漫画阅读平台开放合作开发者的券包发放后端服务，服务对象是做会员中心、任务中心或外部联名活动的内部研发团队。

## 核心能力

### 1. 发券请求接口 (POST /api/v1/coupons/issue)
调用方提交用户标识、活动编号、券包类型和触发场景，服务完成资格校验后发放券包。

**请求参数：**
```json
{
  "user_id": "user_001",
  "activity_id": "act_summer_2024",
  "package_type": "new_reader",
  "trigger_scene": "member_center",
  "request_id": "req_abc123"
}
```

**成功响应：**
```json
{
  "success": true,
  "code": 200,
  "message": "发放成功",
  "user_message": "恭喜您，券包领取成功！",
  "data": {
    "record_id": "uc_abc123def456",
    "coupon_code": "CODEA1B2C3D4",
    "package_id": "pkg_new_reader_001",
    "package_name": "新读者礼包",
    "display_text": "恭喜获得100阅点漫画券包",
    "valid_start_time": "2024-06-20T10:00:00",
    "valid_end_time": "2024-07-20T10:00:00",
    "applicable_comics": ["1001", "1002", "1003"]
  }
}
```

**失败响应（已领过）：**
```json
{
  "success": false,
  "code": 409,
  "message": "User has already claimed this coupon",
  "user_message": "已领过",
  "data": null
}
```

### 2. 资格校验接口 (POST /api/v1/coupons/validate)
在用户点击领取按钮前调用，预先检查是否有资格领取，用于前端展示按钮状态。

### 3. 结果回传接口 (POST /api/v1/coupons/callback)
记录券包的展示、点击、使用等行为数据，用于后续数据分析和转化统计。

## 资格校验规则

1. **重复领取检查** - 检查用户是否已领取过该活动的该券包
2. **活动状态检查** - 检查活动是否进行中
3. **活动时间检查** - 检查当前时间是否在活动有效期内
4. **新读者限制** - 检查是否仅限新读者
5. **会员等级限制** - 检查用户会员等级是否满足要求
6. **地区限制** - 检查用户地区是否在允许范围内
7. **库存检查** - 检查券包库存是否充足

## 错误码说明

| 错误码 | 前端展示文案 | 说明 |
|--------|-------------|------|
| 200 | - | 成功 |
| 403 | 仅限新读者 | 非新读者无法领取 |
| 403 | 会员等级不足 | 会员等级未达到要求 |
| 403 | 当前地区不支持领取 | 用户地区不在允许范围内 |
| 409 | 已领过 | 用户已领取过该券包 |
| 410 | 券包已被抢光 | 库存不足 |
| 412 | 活动未开始 | 活动尚未开始 |
| 412 | 活动已结束 | 活动已结束 |
| 412 | 活动暂停中 | 活动暂停 |
| 404 | 用户不存在 | 用户ID无效 |
| 404 | 活动不存在 | 活动ID无效 |
| 404 | 券包不存在 | 券包类型无效 |
| 400 | 请求参数错误 | 参数校验失败 |
| 500 | 系统繁忙，请稍后再试 | 系统异常 |

## 技术栈

- **Web框架**: FastAPI 0.109
- **数据库**: MySQL 8.0 + SQLAlchemy 2.0
- **缓存**: Redis
- **异步支持**: 全异步架构 (async/await)
- **测试**: pytest + pytest-asyncio

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置环境变量

```bash
cp .env.example .env
# 修改 .env 中的数据库和Redis配置
```

### 启动服务

```bash
python -m app.main
```

### API文档

启动后访问:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 运行测试

```bash
# 安装测试依赖
pip install pytest pytest-asyncio pytest-cov faker

# 运行测试
pytest tests/ -v

# 生成覆盖率报告
pytest tests/ --cov=app --cov-report=html
```

## 项目结构

```
.
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI应用入口
│   ├── api/
│   │   ├── __init__.py
│   │   └── coupon.py           # 券包相关API接口
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py         # 配置管理
│   ├── core/
│   │   ├── __init__.py
│   │   ├── constants.py        # 常量和枚举定义
│   │   └── exceptions.py       # 自定义异常类
│   ├── db/
│   │   ├── __init__.py
│   │   └── session.py          # 数据库和Redis连接
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py             # 用户模型
│   │   ├── activity.py         # 活动模型
│   │   ├── coupon_package.py   # 券包配置模型
│   │   ├── coupon_package_sku.py # 券包SKU模型
│   │   ├── user_coupon.py      # 用户领取记录模型
│   │   └── user_behavior_log.py # 行为埋点模型
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── coupon.py           # 请求/响应DTO
│   └── services/
│       ├── __init__.py
│       ├── coupon_service.py   # 发券核心业务逻辑
│       └── validation_service.py # 资格校验服务
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # 测试配置和fixture
│   ├── test_validation_service.py
│   ├── test_coupon_service.py
│   └── test_api_endpoints.py
├── requirements.txt
├── pyproject.toml
├── .env.example
├── .env.test
├── alembic.ini
└── README.md
```

## 数据库表结构

### users (用户表)
- user_id: 用户标识
- member_level: 会员等级 (0-免费 1-白银 2-黄金 3-铂金 4-钻石)
- region: 地区编码
- is_new_reader: 是否新读者

### activities (活动表)
- activity_id: 活动编号
- status: 状态 (0-草稿 1-进行中 2-暂停 3-已结束)
- start_time/end_time: 活动时间
- allowed_regions: 允许地区
- min_member_level: 最低会员等级
- require_new_reader: 是否仅限新读者

### coupon_packages (券包配置表)
- package_id: 券包ID
- activity_id: 关联活动
- type: 券包类型 (new_reader, member_exclusive, regular, co_brand)
- display_text: 展示文案
- valid_days: 有效天数
- applicable_comics: 适用作品ID列表
- total_quantity/claimed_quantity: 库存统计

### coupon_package_skus (券包SKU表)
- sku_id: SKU ID
- package_id: 关联券包
- coupon_code: 券码
- status: 状态 (0-可发放 1-已发放 2-已使用 3-已过期)
- expire_time: 过期时间
- user_id: 领取用户

### user_coupons (用户领取记录表)
- record_id: 领取记录ID
- user_id/activity_id/package_id: 关联信息
- coupon_code: 券码
- status: 状态 (0-未使用 1-已使用 2-已过期 3-已回收)
- valid_start_time/valid_end_time: 有效期
- applicable_comics: 适用作品
- display_text: 展示文案

### user_behavior_logs (行为埋点表)
- log_id: 日志ID
- user_id/activity_id/package_id: 关联信息
- behavior_type: 行为类型 (impression-展示 click-点击 use-使用)
- trigger_scene: 触发场景
- extra: 扩展信息 (JSON)
- created_at: 行为时间

## 关键设计要点

### 1. 幂等性保证
- 调用方传入 `request_id` 实现幂等
- Redis缓存7天内的请求结果，重复请求直接返回

### 2. 并发控制
- SKU发放使用 `SELECT ... FOR UPDATE SKIP LOCKED` 行锁
- Redis原子操作预扣库存
- 数据库事务保证数据一致性

### 3. 性能优化
- 热点数据Redis缓存（库存、领取状态）
- 异步IO全链路支持
- 数据库连接池配置

### 4. 用户友好错误
- 所有异常都有对应的 `user_message` 字段
- 直接返回前端可展示的中文文案
- 错误码分类清晰，便于调用方处理

## 接入示例

### Python
```python
import httpx

async def issue_coupon(user_id: str, activity_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/coupons/issue",
            json={
                "user_id": user_id,
                "activity_id": activity_id,
                "package_type": "new_reader",
                "trigger_scene": "member_center",
                "request_id": f"req_{int(time.time()*1000)}",
            }
        )
        data = response.json()
        if data["success"]:
            print(f"领取成功: {data['data']['display_text']}")
        else:
            print(f"领取失败: {data['user_message']}")
```

### 前端展示逻辑
```javascript
// 1. 先调用校验接口
const validateResult = await fetch('/api/v1/coupons/validate', {...});
const validateData = await validateResult.json();

if (validateData.success) {
  // 显示可领取按钮
  showClaimButton();
} else {
  // 显示不可领取状态，直接展示user_message
  showDisabledButton(validateData.user_message);
}

// 2. 用户点击后调用发券接口
const issueResult = await fetch('/api/v1/coupons/issue', {...});
const issueData = await issueResult.json();

if (issueData.success) {
  // 展示券包信息
  showCouponSuccess(issueData.data);
} else {
  // 展示失败原因
  showToast(issueData.user_message);
}

// 3. 展示和点击时回传行为数据
await fetch('/api/v1/coupons/callback', {
  method: 'POST',
  body: JSON.stringify({
    user_id: 'user_001',
    activity_id: 'act_001',
    package_id: 'pkg_001',
    behavior_type: 'impression', // 或 'click'
    trigger_scene: 'member_center',
    extra: { position: 'banner_top' }
  })
});
```
