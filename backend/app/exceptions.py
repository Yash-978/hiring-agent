"""Application custom exceptions mapped to HTTP status codes."""


class AppException(Exception):
    def __init__(
        self,
        message: str = "",
        payload: dict[str, object] | None = None,
    ) -> None:
        self.message = message
        # Extra top-level keys merged into the JSON error body by the handler,
        # e.g. {"existing_job_id": 3} for a duplicate-title conflict.
        self.payload = payload or {}
        super().__init__(message)


class NotFoundException(AppException):
    pass


class ForbiddenException(AppException):
    pass


class ConflictException(AppException):
    pass


class ApprovalRequiredException(AppException):
    pass
