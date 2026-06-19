from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.core import TriggerScene, CouponType, BehaviorType


class IssueCouponRequest(BaseModel):
    user_id: str = Field(..., description="用户标识", min_length=1, max_length=64)
    activity_id: str = Field(..., description="活动编号", min_length=1, max_length=64)
    package_type: CouponType = Field(..., description="券包类型")
    trigger_scene: TriggerScene = Field(..., description="触发场景")
    request_id: str | None = Field(default=None, description="请求幂等ID", max_length=64)

    @field_validator("user_id", "activity_id")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("不能为空字符串")
        return v.strip()


class ValidateCouponRequest(BaseModel):
    user_id: str = Field(..., description="用户标识", min_length=1, max_length=64)
    activity_id: str = Field(..., description="活动编号", min_length=1, max_length=64)
    package_type: CouponType = Field(..., description="券包类型")
    trigger_scene: TriggerScene = Field(..., description="触发场景")

    @field_validator("user_id", "activity_id")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("不能为空字符串")
        return v.strip()


class CouponCallbackRequest(BaseModel):
    user_id: str = Field(..., description="用户标识", min_length=1, max_length=64)
    activity_id: str = Field(..., description="活动编号", min_length=1, max_length=64)
    package_id: str = Field(default="", description="券包ID", max_length=64)
    user_coupon_id: str = Field(default="", description="用户券包记录ID", max_length=64)
    behavior_type: BehaviorType = Field(..., description="行为类型")
    trigger_scene: TriggerScene = Field(..., description="触发场景")
    extra: dict[str, Any] = Field(default_factory=dict, description="扩展信息")

    @field_validator("user_id", "activity_id")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("不能为空字符串")
        return v.strip()


class CouponInfo(BaseModel):
    record_id: str = Field(..., description="领取记录ID")
    coupon_code: str = Field(..., description="券码")
    package_id: str = Field(..., description="券包ID")
    package_name: str = Field(..., description="券包名称")
    display_text: str = Field(..., description="展示文案")
    valid_start_time: datetime = Field(..., description="生效开始时间")
    valid_end_time: datetime = Field(..., description="生效结束时间")
    applicable_comics: list[str] = Field(default_factory=list, description="适用作品ID列表")


class IssueCouponResponse(BaseModel):
    success: bool = Field(..., description="是否成功")
    code: int = Field(..., description="状态码")
    message: str = Field(..., description="消息")
    user_message: str = Field(..., description="给前端展示的消息")
    data: CouponInfo | None = Field(default=None, description="券包信息")


class ValidateCouponResponse(BaseModel):
    success: bool = Field(..., description="是否成功")
    code: int = Field(..., description="状态码")
    message: str = Field(..., description="消息")
    user_message: str = Field(..., description="给前端展示的消息")
    data: dict[str, Any] | None = Field(default=None, description="校验通过时的补充信息")


class CouponCallbackResponse(BaseModel):
    success: bool = Field(..., description="是否成功")
    code: int = Field(..., description="状态码")
    message: str = Field(..., description="消息")
    user_message: str = Field(..., description="给前端展示的消息")
    data: None = None
