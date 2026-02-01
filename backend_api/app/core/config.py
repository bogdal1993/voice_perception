import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database settings
    DSN: str = os.getenv("DSN", "")
    DB_SCHEMA: str = os.getenv("DB_SCHEMA", "vp")
    
    # Security settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    
    # Application settings
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    class Config:
        env_file = ".env"


settings = Settings()