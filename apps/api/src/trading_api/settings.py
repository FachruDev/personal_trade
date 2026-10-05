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
    trading_environment: str = "paper"
    coingecko_api_key: str = ""
    coingecko_base_url: str = "https://api.coingecko.com/api/v3"
    fred_api_key: str = ""
    fred_base_url: str = "https://api.stlouisfed.org/fred"
    ai_shadow_provider: str = "disabled"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = ""
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_model: str = ""
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = ""
    news_api_key: str = ""
    news_api_base_url: str = "https://newsapi.org/v2"
    ai_shadow_min_interval_seconds: int = 900
    global_shadow_refresh_seconds: int = 900
    orderbook_shadow_refresh_seconds: int = 300
    orderbook_shadow_min_observations: int = 8064
    orderbook_shadow_continuity_gap_seconds: int = 3600
    paper_run_heartbeat_seconds: int = 900
    paper_run_continuity_gap_seconds: int = 1800
    paper_run_required_days: int = 56
    binance_public_base_url: str = "https://api.binance.com"
    audit_retention_days: int = 180
    context_retention_days: int = 365
    news_retention_days: int = 30
    ai_shadow_retention_days: int = 365

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
