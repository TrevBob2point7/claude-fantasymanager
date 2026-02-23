from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://fantasy:fantasy_dev_password@db:5432/fantasy_manager"
    SECRET_KEY: str = "change-me-to-a-random-secret-key"
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
