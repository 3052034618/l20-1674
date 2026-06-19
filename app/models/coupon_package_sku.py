from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class CouponPackageSku(Base):
    __tablename__ = "coupon_package_skus"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    sku_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="SKU ID")
    package_id: Mapped[str] = mapped_column(String(64), index=True, comment="券包ID")
    coupon_code: Mapped[str] = mapped_column(String(64), unique=True, comment="券码")
    status: Mapped[int] = mapped_column(Integer, default=0, index=True, comment="状态：0-可发放 1-已发放 2-已使用 3-已过期 4-已回收")
    expire_time: Mapped[datetime] = mapped_column(DateTime, comment="过期时间")
    user_id: Mapped[str] = mapped_column(String(64), default="", index=True, comment="领取用户ID")
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="领取时间")
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="使用时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间"
    )
