from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.core import ActivityStatus, BehaviorType, CouponType, MemberLevel, TriggerScene


class CreateActivityRequest(BaseModel):
    activity_id: str = Field(..., description="活动编号", min_length=1, max_length=64)
    name: str = Field(..., description="活动名称", min_length=1, max_length=128)
    description: str = Field(default="", description="活动描述", max_length=512)
    status: ActivityStatus = Field(default=ActivityStatus.DRAFT, description="活动状态")
    start_time: datetime = Field(..., description="活动开始时间")
    end_time: datetime = Field(..., description="活动结束时间")
    allowed_regions: str = Field(default="", description="允许的地区，逗号分隔", max_length=256)
    min_member_level: MemberLevel = Field(default=MemberLevel.FREE, description="最低会员等级")
    require_new_reader: bool = Field(default=False, description="是否要求新读者")

    @field_validator("activity_id", "name")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("不能为空字符串")
        return v.strip()

    @field_validator("end_time")
    @classmethod
    def end_time_after_start_time(cls, v: datetime, info: Any) -> datetime:
        start_time = info.data.get("start_time")
        if start_time and v <= start_time:
            raise ValueError("结束时间必须晚于开始时间")
        return v


class CreateActivityResponse(BaseModel):
    success: bool = Field(..., description="是否成功")
    code: int = Field(..., description="状态码")
    message: str = Field(..., description="消息")
    user_message: str = Field(..., description="给前端展示的消息")
    data: dict[str, Any] | None = Field(default=None, description="活动信息")


class CreateCouponPackageRequest(BaseModel):
    package_id: str = Field(..., description="券包ID", min_length=1, max_length=64)
    activity_id: str = Field(..., description="活动编号", min_length=1, max_length=64)
    name: str = Field(..., description="券包名称", min_length=1, max_length=128)
    type: CouponType = Field(..., description="券包类型")
    display_text: str = Field(default="", description="展示文案", max_length=256)
    valid_days: int = Field(default=30, description="有效天数", ge=1, le=365)
    applicable_comics: str = Field(default="", description="适用作品ID列表，逗号分隔")
    comic_categories: str = Field(default="", description="适用漫画分类，逗号分隔")
    discount_value: int = Field(default=0, description="优惠值", ge=0)
    discount_type: str = Field(default="fixed", description="优惠类型：fixed-固定金额 percent-百分比")

    @field_validator("package_id", "activity_id", "name")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("不能为空字符串")
        return v.strip()


class CreateCouponPackageResponse(BaseModel):
    success: bool = Field(..., description="是否成功")
    code: int = Field(..., description="状态码")
    message: str = Field(..., description="消息")
    user_message: str = Field(..., description="给前端展示的消息")
    data: dict[str, Any] | None = Field(default=None, description="券包信息")


class GenerateCouponCodesRequest(BaseModel):
    package_id: str = Field(..., description="券包ID", min_length=1, max_length=64)
    quantity: int = Field(..., description="生成数量", ge=1, le=10000)
    expire_days: int = Field(default=365, description="过期天数", ge=1, le=730)
    prefix: str = Field(default="", description="券码前缀", max_length=16)

    @field_validator("package_id")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("不能为空字符串")
        return v.strip()


class GenerateCouponCodesResponse(BaseModel):
    success: bool = Field(..., description="是否成功")
    code: int = Field(..., description="状态码")
    message: str = Field(..., description="消息")
    user_message: str = Field(..., description="给前端展示的消息")
    data: dict[str, Any] | None = Field(default=None, description="生成结果")


class ImportCouponCodesRequest(BaseModel):
    package_id: str = Field(..., description="券包ID", min_length=1, max_length=64)
    coupon_codes: list[str] = Field(..., description="券码列表", min_length=1, max_length=10000)
    expire_days: int = Field(default=365, description="过期天数", ge=1, le=730)

    @field_validator("package_id")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("不能为空字符串")
        return v.strip()

    @field_validator("coupon_codes")
    @classmethod
    def validate_codes(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("券码列表不能为空")
        for code in v:
            if not code or len(code.strip()) == 0:
                raise ValueError("券码不能为空")
            if len(code.strip()) > 64:
                raise ValueError("券码长度不能超过64")
        return [c.strip() for c in v]


class ImportCouponCodesResponse(BaseModel):
    success: bool = Field(..., description="是否成功")
    code: int = Field(..., description="状态码")
    message: str = Field(..., description="消息")
    user_message: str = Field(..., description="给前端展示的消息")
    data: dict[str, Any] | None = Field(default=None, description="导入结果")


class PackageStatsResponse(BaseModel):
    success: bool = Field(..., description="是否成功")
    code: int = Field(..., description="状态码")
    message: str = Field(..., description="消息")
    user_message: str = Field(..., description="给前端展示的消息")
    data: dict[str, Any] | None = Field(default=None, description="统计数据")


class ActivityListResponse(BaseModel):
    success: bool = Field(..., description="是否成功")
    code: int = Field(..., description="状态码")
    message: str = Field(..., description="消息")
    user_message: str = Field(..., description="给前端展示的消息")
    data: list[dict[str, Any]] | None = Field(default=None, description="活动列表")


class PackageListResponse(BaseModel):
    success: bool = Field(..., description="是否成功")
    code: int = Field(..., description="状态码")
    message: str = Field(..., description="消息")
    user_message: str = Field(..., description="给前端展示的消息")
    data: list[dict[str, Any]] | None = Field(default=None, description="券包列表")


class BehaviorStatsRequest(BaseModel):
    activity_id: str = Field(..., description="活动编号", min_length=1, max_length=64)
    package_type: CouponType | None = Field(default=None, description="券包类型，可选")
    start_time: datetime | None = Field(default=None, description="统计开始时间")
    end_time: datetime | None = Field(default=None, description="统计结束时间")

    @field_validator("activity_id")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("不能为空字符串")
        return v.strip()


class BehaviorSceneStats(BaseModel):
    trigger_scene: str = Field(..., description="触发场景")
    impression_count: int = Field(..., description="展示次数")
    click_count: int = Field(..., description="点击次数")
    use_count: int = Field(..., description="使用次数")


class BehaviorStatsResponse(BaseModel):
    success: bool = Field(..., description="是否成功")
    code: int = Field(..., description="状态码")
    message: str = Field(..., description="消息")
    user_message: str = Field(..., description="给前端展示的消息")
    data: dict[str, Any] | None = Field(default=None, description="统计数据")
