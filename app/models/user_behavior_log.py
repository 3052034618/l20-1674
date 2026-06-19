from datetime import datetime

from sqlalchemy import DateTime, Integer, String, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class UserBehaviorLog(Base):
    __tablename__ = "user_behavior_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    log_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="日志ID")
    user_id: Mapped[str] = mapped_column(String(64), index=True, comment="用户标识")
    activity_id: Mapped[str] = mapped_column(String(64), index=True, comment="活动编号")
    package_id: Mapped[str] = mapped_column(String(64), default="", index=True, comment="券包ID")
    user_coupon_id: Mapped[str] = mapped_column(String(64), default="", index=True, comment="用户券包记录ID")
    behavior_type: Mapped[str] = mapped_column(String(32), index=True, comment="行为类型：impression-展示 click-点击 use-使用")
    trigger_scene: Mapped[str] = mapped_column(String(32), default="", comment="触发场景")
    extra: Mapped[dict] = mapped_column(JSON, default={}, comment="扩展信息")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True, comment="创建时间")
