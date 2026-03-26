from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    secret_key: str = "super-secret-key-for-mfa-demo"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

settings = Settings()
