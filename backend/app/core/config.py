# Application Settings
from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "Creatio"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/creatio_db"
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Paystack
    PAYSTACK_SECRET_KEY: str = ""
    PAYSTACK_PUBLIC_KEY: str = ""
    PAYSTACK_BASE_URL: str = "https://api.paystack.co"
    
    # S3 Storage
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_S3_BUCKET_NAME: str = "creatio-pow"
    AWS_REGION: str = "us-east-1"
    AWS_S3_ENDPOINT_URL: Optional[str] = None  # For local MinIO or other S3-compatible
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Platform
    PLATFORM_COMMISSION_PERCENT: float = 15.0  # 15% platform fee
    CREATOR_SHARE_PERCENT: float = 85.0  # 85% to creator
    
    # Auto-release settings (days)
    POW_AUTO_RELEASE_DAYS: int = 7
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
