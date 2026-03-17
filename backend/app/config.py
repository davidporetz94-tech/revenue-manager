from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://david@localhost:5432/multifamily_rm"
    ANTHROPIC_API_KEY: str = "your-api-key-here"
    SECRET_KEY: str = "dev-jwt-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
