"""Configuration management for the ingestion service."""
import os
from dataclasses import dataclass


@dataclass
class Config:
    """Service configuration loaded from environment variables."""
    
    redis_url: str
    db_api_host: str
    db_api_port: int
    broker_service_host: str
    broker_service_port: int
    broker_account_id: str
    log_level: str
    consumer_batch_size: int
    consumer_block_ms: int
    
    @property
    def db_api_base_url(self) -> str:
        """Full base URL for the database accessor API."""
        return f"http://{self.db_api_host}:{self.db_api_port}"
    
    @property
    def broker_service_base_url(self) -> str:
        """Full base URL for the broker service API."""
        return f"http://{self.broker_service_host}:{self.broker_service_port}"


def load_config() -> Config:
    """Load configuration from environment variables."""
    return Config(
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        db_api_host=os.getenv("DATABASE_ACCESSOR_HOST", "database-accessor-api"),
        db_api_port=int(os.getenv("DATABASE_ACCESSOR_PORT", "8000")),
        broker_service_host=os.getenv("BROKER_SERVICE_HOST", "broker-service"),
        broker_service_port=int(os.getenv("BROKER_SERVICE_PORT", "8050")),
        broker_account_id=os.getenv("ACCOUNT_ID", "12345"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        consumer_batch_size=int(os.getenv("CONSUMER_BATCH_SIZE", "100")),
        consumer_block_ms=int(os.getenv("CONSUMER_BLOCK_MS", "5000")),
    )
