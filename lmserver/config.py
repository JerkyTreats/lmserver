"""Configuration settings for LMServer."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Server settings
    host: str = Field(default="0.0.0.0", description="Host to bind the API server")
    port: int = Field(default=8000, description="Port for the API server")

    # llama-server backend
    llama_server_url: str = Field(
        default="http://127.0.0.1:8080",
        description="URL of the llama-server backend",
    )

    # Concurrency control
    max_concurrent_requests: int = Field(
        default=4,
        description="Maximum concurrent inference requests (tune based on RAM)",
    )
    request_timeout: float = Field(
        default=300.0,
        description="Timeout for inference requests in seconds",
    )

    # DNS registration
    dns_domain_base: str = Field(
        default="internal.jerkytreats.dev",
        description="Base domain for DNS registration (e.g., internal.jerkytreats.dev)",
    )
    dns_api_url: str = Field(
        default="https://dns.internal.jerkytreats.dev",
        description="Custom DNS API server URL",
    )
    dns_service_name: str = Field(
        default="chat",
        description="Service name for DNS registration (combined with dns_domain_base to form full domain)",
    )
    dns_register_on_startup: bool = Field(
        default=False,
        description="Whether to register with DNS on startup (only needed once)",
    )
    dns_target_device: str = Field(
        default="leviathan",
        description="Tailscale device name where the service runs",
    )

    # Model settings (for display/routing)
    default_model: str = Field(
        default="gpt-oss-20b",
        description="Default model name to report in API responses",
    )

    model_config = {
        "env_prefix": "LMSERVER_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()

