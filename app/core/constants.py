from enum import Enum


class ActivityStatus(int, Enum):
    DRAFT = 0
    ONGOING = 1
    PAUSED = 2
    ENDED = 3


class CouponType(str, Enum):
    NEW_READER = "new_reader"
    MEMBER_EXCLUSIVE = "member_exclusive"
    REGULAR = "regular"
    CO_BRAND = "co_brand"


class CouponStatus(int, Enum):
    UNUSED = 0
    USED = 1
    EXPIRED = 2
    REVOKED = 3


class MemberLevel(int, Enum):
    FREE = 0
    SILVER = 1
    GOLD = 2
    PLATINUM = 3
    DIAMOND = 4


class TriggerScene(str, Enum):
    MEMBER_CENTER = "member_center"
    TASK_CENTER = "task_center"
    CO_BRAND = "co_brand"
    PUSH = "push"
    OTHER = "other"


class BehaviorType(str, Enum):
    IMPRESSION = "impression"
    CLICK = "click"
    USE = "use"


ERROR_MESSAGES: dict[str, str] = {
    "already_claimed": "已领过",
    "not_eligible_new_reader": "仅限新读者",
    "not_eligible_member_level": "会员等级不足",
    "region_restricted": "当前地区不支持领取",
    "stock_insufficient": "券包已被抢光",
    "activity_not_started": "活动未开始",
    "activity_ended": "活动已结束",
    "activity_paused": "活动暂停中",
    "activity_not_found": "活动不存在",
    "coupon_not_found": "券包不存在",
    "user_not_found": "用户不存在",
    "invalid_request": "请求参数错误",
    "system_error": "系统繁忙，请稍后再试",
    "partner_auth_failed": "合作方认证失败",
    "partner_forbidden": "合作方无权限访问",
    "partner_daily_limit_reached": "合作方每日发券限额已用尽",
    "signature_missing": "缺少签名头",
    "signature_expired": "请求时间戳已过期",
    "signature_invalid": "签名校验失败",
}
