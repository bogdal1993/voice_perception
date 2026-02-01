import logging
from datetime import datetime
import json
from typing import Dict, Any
from fastapi import Request
from fastapi.responses import Response


class APILogger:
    def __init__(self, name: str = "api_logger"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Create a handler for logging to a file
        if not self.logger.handlers:
            handler = logging.StreamHandler()  # Using StreamHandler for console output
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def log_request(self, request: Request, user: str = "anonymous"):
        """Log incoming requests"""
        self.logger.info(f"Request: {request.method} {request.url} | User: {user}")
    
    def log_response(self, request: Request, response: Response, user: str = "anonymous"):
        """Log outgoing responses"""
        self.logger.info(f"Response: {request.method} {request.url} | Status: {response.status_code} | User: {user}")
    
    def log_error(self, request: Request, error: Exception, user: str = "anonymous"):
        """Log errors"""
        self.logger.error(f"Error in {request.method} {request.url} | User: {user} | Error: {str(error)}")
    
    def log_db_query(self, query: str, params: tuple = (), user: str = "anonymous"):
        """Log database queries"""
        self.logger.debug(f"DB Query: {query} | Params: {params} | User: {user}")
    
    def log_security_event(self, event: str, user: str = "anonymous", ip: str = "unknown"):
        """Log security-related events"""
        self.logger.warning(f"Security Event: {event} | User: {user} | IP: {ip}")
    
    def log_user_action(self, action: str, user: str, details: Dict[str, Any] = None):
        """Log user actions"""
        details_str = f" | Details: {json.dumps(details, default=str)}" if details else ""
        self.logger.info(f"User Action: {action} | User: {user}{details_str}")


# Create a global logger instance
api_logger = APILogger()