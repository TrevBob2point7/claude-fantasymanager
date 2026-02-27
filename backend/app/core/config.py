from pydantic import model_validator
from pydantic_settings import BaseSettings

_INSECURE_SECRET_KEY = "change-me-to-a-random-secret-key"


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://fantasy:fantasy_dev_password@db:5432/fantasy_manager"
    SECRET_KEY: str = _INSECURE_SECRET_KEY
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    SYNC_INTERVAL_MINUTES: int = 30
    SYNC_ENABLED: bool = True
    ENVIRONMENT: str = "development"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @model_validator(mode="after")
    def _check_secret_key(self) -> "Settings":
        if self.ENVIRONMENT != "development" and self.SECRET_KEY == _INSECURE_SECRET_KEY:
            raise ValueError(
                "SECRET_KEY must be set to a secure random value in non-development environments"
            )
        return self


settings = Settings()
