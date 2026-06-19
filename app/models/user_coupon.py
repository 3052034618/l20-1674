from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class UserCoupon(Base):
    __tablename__ = "user_coupons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    record_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="领取记录ID")
    user_id: Mapped[str] = mapped_column(String(64), index=True, comment="用户标识")
    activity_id: Mapped[str] = mapped_column(String(64), index=True, comment="活动编号")
    package_id: Mapped[str] = mapped_column(String(64), index=True, comment="券包ID")
    sku_id: Mapped[str] = mapped_column(String(64), index=True, comment="SKU ID")
    coupon_code: Mapped[str] = mapped_column(String(64), comment="券码")
    status: Mapped[int] = mapped_column(Integer, default=0, index=True, comment="状态：0-未使用 1-已使用 2-已过期 3-已回收")
    trigger_scene: Mapped[str] = mapped_column(String(32), default="", comment="触发场景")
    valid_start_time: Mapped[datetime] = mapped_column(DateTime, comment="生效开始时间")
    valid_end_time: Mapped[datetime] = mapped_column(DateTime, comment="生效结束时间")
    applicable_comics: Mapped[str] = mapped_column(Text, default="", comment="适用作品ID列表，逗号分隔")
    display_text: Mapped[str] = mapped_column(String(256), default="", comment="展示文案")
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="使用时间")
    used_comic_id: Mapped[str] = mapped_column(String(64), default="", comment="使用的漫画ID")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间"
    )
