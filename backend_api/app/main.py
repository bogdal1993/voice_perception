from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from .api.routers import auth, calls, mentors, tags, api_keys, metadata_mappings
from .database.connection import db
from .models.user import User
from .core.config import settings
from .utils.exceptions import (
    http_error_handler, 
    custom_error_handler, 
    validation_error_handler, 
    general_exception_handler
)
from .middleware.logging_middleware import LoggingMiddleware, SecurityLoggingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await db.create_pool()
    print("Database pool created")
    
    # Create default admin user if not exists
    async with db.pool.acquire() as connection:
        await User.create_default_admin(connection)
    
    yield
    
    # Shutdown
    await db.close_pool()
    print("Database pool closed")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Voice Perception Backend API",
    description="API for voice perception and call analytics",
    version="1.0",
    lifespan=lifespan
)

# Add logging middleware
app.add_middleware(LoggingMiddleware)
app.add_middleware(SecurityLoggingMiddleware)

# Configure CORS
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost",
    "http://127.0.1",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register exception handlers
app.add_exception_handler(StarletteHTTPException, http_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Include routers
app.include_router(auth.router, prefix="", tags=["authentication"])
app.include_router(calls.router, prefix="", tags=["calls"])
app.include_router(mentors.router, prefix="", tags=["mentors"])
app.include_router(tags.router, prefix="", tags=["tags"])
app.include_router(api_keys.router, prefix="", tags=["api_keys"])
app.include_router(metadata_mappings.router, prefix="", tags=["metadata_mappings"])

@app.get("/")
async def root():
    return {"message": "Voice Perception Backend API"}


@app.get("/health")
async def health_check():
    try:
        # Try to get a connection from the pool to check if the database is accessible
        async with db.pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}