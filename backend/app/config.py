from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"
    use_stub_llm: bool = False
    database_url: str = "postgresql+asyncpg://scin:scin@localhost:5432/scin"
    test_database_url: str = "postgresql+asyncpg://scin:scin@localhost:5432/scin_test"
    posthog_api_key: str = ""
    posthog_host: str = "https://us.i.posthog.com"


settings = Settings()
