from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="用户标识")
    nickname: Mapped[str] = mapped_column(String(64), default="", comment="昵称")
    member_level: Mapped[int] = mapped_column(Integer, default=0, comment="会员等级：0-免费 1-白银 2-黄金 3-铂金 4-钻石")
    region: Mapped[str] = mapped_column(String(32), default="", comment="地区编码")
    is_new_reader: Mapped[bool] = mapped_column(Integer, default=1, comment="是否新读者：0-否 1-是")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间"
    )
