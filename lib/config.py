"""
Environment configuration and secrets management for SignalHire Agent.

This module provides a centralized configuration system that:
- Loads environment variables from .env files
- Validates required configurations
- Provides type-safe access to configuration values
- Supports different environments (dev, test, production)
- Manages API keys and credentials securely
"""

from __future__ import annotations

import os
import warnings
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings
import structlog
from dotenv import load_dotenv

logger = structlog.get_logger(__name__)


class Environment(str, Enum):
    """Supported environments."""

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """Supported log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class SignalHireConfig(BaseModel):
    """SignalHire-specific configuration."""

    email: str | None = Field(None, description="SignalHire account email")
    password: str | None = Field(None, description="SignalHire account password")
    api_key: str | None = Field(None, description="SignalHire API key (if available)")
    base_url: str = Field(
        "https://www.signalhire.com", description="SignalHire base URL"
    )

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if v and '@' not in v:
            raise ValueError('Invalid email format')
        return v


class CallbackServerConfig(BaseModel):
    """Callback server configuration."""

    host: str = Field("0.0.0.0", description="Server host")
    port: int = Field(8000, description="Server port")
    external_host: str | None = Field(
        None, description="External host for webhook URLs"
    )

    @field_validator('port')
    @classmethod
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError('Port must be between 1 and 65535')
        return v


class ApiConfig(BaseModel):
    """API operation configuration."""

    timeout: float = Field(30.0, description="API request timeout in seconds")
    retry_attempts: int = Field(3, description="Number of API retry attempts")
    batch_size: int = Field(
        100, description="Default batch size for API operations (max per request)"
    )
    without_contacts_mode: bool = Field(
        False, description="Use withoutContacts mode to preserve credits"
    )


class RateLimitConfig(BaseModel):
    """Rate limiting configuration based on SignalHire API limits."""

    elements_per_minute: int = Field(
        600, description="Max elements processed per minute (SignalHire limit)"
    )
    max_elements_per_request: int = Field(
        100, description="Max elements per single request"
    )
    max_parallel_requests: int = Field(
        10, description="Max parallel requests (conservative limit)"
    )
    retry_attempts: int = Field(3, description="Number of retry attempts")
    retry_delay: float = Field(1.0, description="Base retry delay in seconds")
    rate_limit_warnings: bool = Field(
        True, description="Show warnings at usage thresholds"
    )


class ExportConfig(BaseModel):
    """Data export configuration."""

    default_format: str = Field("csv", description="Default export format")
    output_dir: Path = Field(Path("./exports"), description="Default export directory")
    include_headers: bool = Field(True, description="Include headers in CSV exports")
    date_format: str = Field("%Y-%m-%d", description="Date format for exports")
    export_timestamps: bool = Field(
        True, description="Add timestamps to export filenames"
    )
    timestamp_format: str = Field(
        "%Y%m%d_%H%M%S", description="Timestamp format for filenames"
    )

    @field_validator('output_dir')
    @classmethod
    def create_output_dir(cls, v):
        v.mkdir(parents=True, exist_ok=True)
        return v


class Config(BaseSettings):
    """Main application configuration."""

    # Environment
    environment: Environment = Field(
        Environment.DEVELOPMENT, description="Application environment"
    )
    debug: bool = Field(False, description="Enable debug mode")
    log_level: LogLevel = Field(LogLevel.INFO, description="Logging level")

    # Service configurations
    signalhire: SignalHireConfig = Field(default_factory=SignalHireConfig)
    callback_server: CallbackServerConfig = Field(default_factory=CallbackServerConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)

    # External API keys
    openai_api_key: str | None = Field(None, validation_alias="OPENAI_API_KEY")
    gemini_api_key: str | None = Field(None, validation_alias="GEMINI_API_KEY")

    # Development settings
    enable_metrics: bool = Field(False, description="Enable metrics collection")
    enable_tracing: bool = Field(False, description="Enable request tracing")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_nested_delimiter = "__"
        case_sensitive = False
        extra = "ignore"  # Allow extra environment variables

    @model_validator(mode='before')
    @classmethod
    def load_signalhire_credentials(cls, values):
        """Load SignalHire credentials from environment."""
        if isinstance(values, dict):
            signalhire_config = values.get('signalhire', {})
            if isinstance(signalhire_config, dict):
                signalhire_config['email'] = os.getenv('SIGNALHIRE_EMAIL')
                signalhire_config['password'] = os.getenv('SIGNALHIRE_PASSWORD')
                signalhire_config['api_key'] = os.getenv('SIGNALHIRE_API_KEY')
                values['signalhire'] = signalhire_config
        return values

    @field_validator('environment', mode='before')
    @classmethod
    def parse_environment(cls, v):
        if isinstance(v, str):
            return Environment(v.lower())
        return v

    def validate_required_credentials(
        self, require_signalhire: bool = True
    ) -> list[str]:
        """Validate that required credentials are present."""
        missing = []

        if require_signalhire:
            if not self.signalhire.email:
                missing.append("SIGNALHIRE_EMAIL")
            if not self.signalhire.password:
                missing.append("SIGNALHIRE_PASSWORD")

        return missing

    def get_callback_url(self) -> str:
        """Get the webhook callback URL."""
        host = self.callback_server.external_host or self.callback_server.host
        if host == "0.0.0.0":
            host = "localhost"
        return f"http://{host}:{self.callback_server.port}/signalhire/callback"

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == Environment.PRODUCTION

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == Environment.DEVELOPMENT

    def is_test(self) -> bool:
        """Check if running in test environment."""
        return self.environment == Environment.TEST

    def get_log_config(self) -> dict[str, Any]:
        """Get logging configuration."""
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": "structlog.stdlib.ProcessorFormatter",
                    "processor": (
                        "structlog.dev.ConsoleRenderer"
                        if self.is_development()
                        else "structlog.processors.JSONRenderer"
                    ),
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                },
            },
            "loggers": {
                "": {
                    "handlers": ["console"],
                    "level": self.log_level.value,
                },
                "uvicorn": {
                    "handlers": ["console"],
                    "level": "INFO",
                    "propagate": False,
                },
            },
        }


# Global configuration instance
_config: Config | None = None


def load_config(
    env_file: str | None = None, reload: bool = False, validate_credentials: bool = True
) -> Config:
    """Load and return the application configuration."""
    global _config

    if _config is not None and not reload:
        return _config

    # Load environment variables
    if env_file:
        load_dotenv(env_file)
    else:
        # Try to load from common locations
        for env_path in [".env", "../.env", "../../.env"]:
            if os.path.exists(env_path):
                load_dotenv(env_path)
                break

    # Create config instance
    try:
        _config = Config()
        logger.info(
            "Configuration loaded successfully", environment=_config.environment.value
        )

        # Validate credentials if requested
        if validate_credentials:
            missing = _config.validate_required_credentials()
            if missing:
                warnings.warn(
                    f"Missing required credentials: {', '.join(missing)}", stacklevel=2
                )
                logger.warning("Missing credentials", missing=missing)

        return _config

    except Exception as e:
        logger.error("Failed to load configuration", error=str(e))
        raise


def get_config() -> Config:
    """Get the current configuration instance."""
    if _config is None:
        return load_config()
    return _config


def update_config(**kwargs) -> None:
    """Update configuration values at runtime."""
    global _config
    if _config is not None:
        for key, value in kwargs.items():
            if hasattr(_config, key):
                setattr(_config, key, value)
                logger.info("Configuration updated", key=key)


def create_test_config(**overrides) -> Config:
    """Create a configuration instance for testing."""
    defaults = {
        "environment": Environment.TEST,
        "debug": True,
        "log_level": LogLevel.DEBUG,
        "signalhire__email": "test@example.com",
        "signalhire__password": "test123",
        "callback_server__port": 8999,
        "browser__headless": True,
    }
    defaults.update(overrides)

    # Set environment variables temporarily
    original_env = {}
    for key, value in defaults.items():
        if "__" in key:
            env_key = key.upper()
            original_env[env_key] = os.environ.get(env_key)
            os.environ[env_key] = str(value)

    try:
        config = Config()
        return config
    finally:
        # Restore original environment
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


# Convenience functions for common config access
def get_signalhire_credentials() -> tuple[str | None, str | None]:
    """Get SignalHire email and password."""
    config = get_config()
    return config.signalhire.email, config.signalhire.password


def get_callback_server_config() -> CallbackServerConfig:
    """Get callback server configuration."""
    return get_config().callback_server


def get_api_config() -> ApiConfig:
    """Get API configuration."""
    return get_config().api


def get_rate_limit_config() -> RateLimitConfig:
    """Get rate limiting configuration."""
    return get_config().rate_limit


def get_export_config() -> ExportConfig:
    """Get export configuration."""
    return get_config().export


if __name__ == "__main__":
    # Example usage and validation
    config = load_config()
    print(f"Environment: {config.environment}")
    print(f"Debug mode: {config.debug}")
    print(f"Callback URL: {config.get_callback_url()}")

    missing = config.validate_required_credentials()
    if missing:
        print(f"Missing credentials: {missing}")
    else:
        print("All required credentials are configured")
