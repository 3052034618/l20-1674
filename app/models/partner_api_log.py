from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class PartnerApiLog(Base):
    __tablename__ = "partner_api_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    log_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="日志ID")
    partner_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False, comment="合作方标识")
    api_path: Mapped[str] = mapped_column(String(128), nullable=False, comment="接口路径")
    request_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="请求时间")
    success: Mapped[int] = mapped_column(Integer, default=0, comment="是否成功：0-失败 1-成功")
    error_key: Mapped[str] = mapped_column(String(64), default="", comment="失败原因标识")
    is_idempotent_hit: Mapped[int] = mapped_column(Integer, default=0, comment="是否幂等命中：0-否 1-是")
    activity_id: Mapped[str] = mapped_column(String(64), default="", comment="活动编号")
    package_type: Mapped[str] = mapped_column(String(32), default="", comment="券包类型")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")
