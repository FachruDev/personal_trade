from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Docker injects .env as raw environment variables. Re-reading the file can
    # reinterpret special password characters and break service-to-service auth.
    model_config = SettingsConfigDict(extra="ignore")
    redis_url: str
    postgres_db: str
    postgres_user: str
    postgres_password: str
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    freqtrade_api_url: str = "http://freqtrade:8080"
    freqtrade_api_username: str = "freqtrader"
    freqtrade_api_password: str
    bot_control_token: str

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
