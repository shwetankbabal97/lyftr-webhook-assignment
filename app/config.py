from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    WEBHOOK_SECRET: str = ""  # Optional - app starts without it, but webhook will reject requests
    DATABASE_URL: str = "sqlite:////data/app.db" 
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env" 

# Create a global settings object
settings = Settings()
