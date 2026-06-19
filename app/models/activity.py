from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    activity_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="活动编号")
    name: Mapped[str] = mapped_column(String(128), comment="活动名称")
    description: Mapped[str] = mapped_column(Text, default="", comment="活动描述")
    status: Mapped[int] = mapped_column(Integer, default=0, index=True, comment="状态：0-草稿 1-进行中 2-暂停 3-已结束")
    start_time: Mapped[datetime] = mapped_column(DateTime, comment="活动开始时间")
    end_time: Mapped[datetime] = mapped_column(DateTime, comment="活动结束时间")
    allowed_regions: Mapped[str] = mapped_column(String(512), default="", comment="允许地区，逗号分隔，空表示不限制")
    min_member_level: Mapped[int] = mapped_column(Integer, default=0, comment="最低会员等级")
    require_new_reader: Mapped[bool] = mapped_column(Integer, default=0, comment="是否仅限新读者")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间"
    )
