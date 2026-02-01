from fastapi import HTTPException, status
from fastapi.responses import JSONResponse


class CustomException(HTTPException):
    def __init__(self, status_code: int, detail: str):
        super().__init__(status_code=status_code, detail=detail)


class BadRequestException(CustomException):
    def __init__(self, detail: str = "Bad Request"):
        super().__init__(status.HTTP_400_BAD_REQUEST, detail)


class NotFoundException(CustomException):
    def __init__(self, detail: str = "Not Found"):
        super().__init__(status.HTTP_404_NOT_FOUND, detail)


class ForbiddenException(CustomException):
    def __init__(self, detail: str = "Forbidden"):
        super().__init__(status.HTTP_403_FORBIDDEN, detail)


class UnauthorizedException(CustomException):
    def __init__(self, detail: str = "Unauthorized"):
        super().__init__(status.HTTP_401_UNAUTHORIZED, detail)


class InternalServerErrorException(CustomException):
    def __init__(self, detail: str = "Internal Server Error"):
        super().__init__(status.HTTP_500_INTERNAL_SERVER_ERROR, detail)


# Global exception handlers
async def http_error_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


async def custom_error_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


async def validation_error_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()}
    )


async def general_exception_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred"}
    )