from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse
from ..utils.logging import api_logger


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Log the incoming request
        user = request.headers.get("username", "anonymous")
        api_logger.log_request(request, user)
        
        response = await call_next(request)
        
        # Log the response
        api_logger.log_response(request, response, user)
        
        return response


class SecurityLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Log security events for certain status codes
        if response.status_code in [401, 403, 422]:
            user = request.headers.get("username", "anonymous")
            ip = request.client.host
            api_logger.log_security_event(f"Unauthorized access attempt: {request.method} {request.url}", user, ip)
        
        return response