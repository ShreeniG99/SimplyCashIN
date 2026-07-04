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
    redis_url: str = "redis://localhost:6379/0"
    enable_scheduler: bool = False
    enable_celery_dispatch: bool = False

    # M3 channels — all empty by default: the factory falls back to
    # SimulatedChannel so tests and the demo never need real credentials.
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = ""
    twilio_sms_from: str = ""
    twilio_validate_signature: bool = False
    twilio_to_map: str = ""   # JSON {"buyer_id": "+91..."} until buyer contact columns land
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    email_to_map: str = ""    # JSON {"buyer_id": "a@b.c"} until buyer contact columns land

    # M4 auth — unset means dev fallback: every request resolves to owner "ramesh".
    supabase_jwt_secret: str = ""


settings = Settings()
