from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str = "http://localhost:8000/auth/callback"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"

    llm_provider: str = "ollama"  # "ollama" or "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    secret_key: str = "dev-secret-change-me"
    frontend_url: str = "http://localhost:3000"
    database_url: str = "sqlite:///./app.db"

    class Config:
        env_file = ".env"


settings = Settings()

# Gmail scopes: read-only is enough for an MVP that only categorizes,
# not one that modifies/labels messages.
GMAIL_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/gmail.readonly",
]

CATEGORIES = [
    "Job/Interview",
    "Bills/Payments",
    "Personal",
    "Newsletter/Promotions",
    "Other",
]
