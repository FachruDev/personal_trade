from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str
    redis_url: str
    freqtrade_api_url: str = "http://freqtrade:8080"
    freqtrade_api_username: str = "freqtrader"
    freqtrade_api_password: str
    bot_control_token: str


settings = Settings()
