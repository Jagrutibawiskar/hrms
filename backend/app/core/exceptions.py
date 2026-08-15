from fastapi import HTTPException, status


class AppError(HTTPException):
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, detail: str, status_code: int | None = None):
        super().__init__(status_code=status_code or self.status_code, detail=detail)


class BadRequest(AppError):
    status_code = status.HTTP_400_BAD_REQUEST


class Unauthorized(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED

    def __init__(self, detail: str = "Not authenticated"):
        super().__init__(detail)
        self.headers = {"WWW-Authenticate": "Bearer"}


class Forbidden(AppError):
    status_code = status.HTTP_403_FORBIDDEN

    def __init__(self, detail: str = "You do not have permission to perform this action"):
        super().__init__(detail)


class NotFound(AppError):
    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, detail: str = "Resource not found"):
        super().__init__(detail)


class Conflict(AppError):
    status_code = status.HTTP_409_CONFLICT
