from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Partner(Base):
    __tablename__ = "partners"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    partner_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False, comment="合作方标识")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="合作方名称")
    sign_key: Mapped[str] = mapped_column(String(64), nullable=False, comment="签名密钥")
    allowed_activities: Mapped[str] = mapped_column(Text, default="", comment="允许调用的活动ID列表，逗号分隔")
    allowed_package_types: Mapped[str] = mapped_column(String(256), default="", comment="允许调用的券包类型，逗号分隔")
    daily_limit: Mapped[int] = mapped_column(Integer, default=0, comment="每日发券上限，0表示不限")
    status: Mapped[int] = mapped_column(Integer, default=1, index=True, comment="状态：0-禁用 1-启用")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
