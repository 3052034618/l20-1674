from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class CouponPackage(Base):
    __tablename__ = "coupon_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    package_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="券包ID")
    activity_id: Mapped[str] = mapped_column(String(64), index=True, comment="活动编号")
    name: Mapped[str] = mapped_column(String(128), comment="券包名称")
    type: Mapped[str] = mapped_column(String(32), index=True, comment="券包类型")
    display_text: Mapped[str] = mapped_column(String(256), default="", comment="展示文案")
    valid_days: Mapped[int] = mapped_column(Integer, default=30, comment="有效天数")
    applicable_comics: Mapped[str] = mapped_column(Text, default="", comment="适用作品ID列表，逗号分隔")
    comic_categories: Mapped[str] = mapped_column(String(256), default="", comment="适用漫画分类，逗号分隔")
    discount_value: Mapped[int] = mapped_column(Integer, default=0, comment="优惠值（分或百分比）")
    discount_type: Mapped[str] = mapped_column(String(16), default="fixed", comment="优惠类型：fixed-固定金额 percent-百分比")
    total_quantity: Mapped[int] = mapped_column(Integer, default=0, comment="总发放数量")
    claimed_quantity: Mapped[int] = mapped_column(Integer, default=0, comment="已领取数量")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间"
    )
