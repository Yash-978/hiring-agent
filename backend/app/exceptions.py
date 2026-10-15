"""Application custom exceptions mapped to HTTP status codes."""


class AppException(Exception):
    def __init__(self, message: str = "") -> None:
        self.message = message
        super().__init__(message)


class NotFoundException(AppException):
    pass


class ForbiddenException(AppException):
    pass


class ConflictException(AppException):
    pass


class ApprovalRequiredException(AppException):
    pass
