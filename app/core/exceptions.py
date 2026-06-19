from .constants import ERROR_MESSAGES


class CouponException(Exception):
    def __init__(self, message: str, code: int = 400, user_message: str | None = None):
        super().__init__(message)
        self.code = code
        self.user_message = user_message or message
        self.message = message


class CouponAlreadyClaimedError(CouponException):
    def __init__(self, message: str = "User has already claimed this coupon"):
        super().__init__(
            message=message,
            code=409,
            user_message=ERROR_MESSAGES["already_claimed"],
        )


class CouponStockError(CouponException):
    def __init__(self, message: str = "Insufficient coupon stock"):
        super().__init__(
            message=message,
            code=410,
            user_message=ERROR_MESSAGES["stock_insufficient"],
        )


class CouponEligibilityError(CouponException):
    def __init__(self, message: str, error_key: str):
        super().__init__(
            message=message,
            code=403,
            user_message=ERROR_MESSAGES.get(error_key, message),
        )


class CouponActivityError(CouponException):
    def __init__(self, message: str, error_key: str):
        super().__init__(
            message=message,
            code=412,
            user_message=ERROR_MESSAGES.get(error_key, message),
        )


class CouponUserError(CouponException):
    def __init__(self, message: str, error_key: str):
        super().__init__(
            message=message,
            code=404,
            user_message=ERROR_MESSAGES.get(error_key, message),
        )
