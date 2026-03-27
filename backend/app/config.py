from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./f1predict.db"
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24  # 24 hours

    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    frontend_url: str = "http://localhost:3000"

    # ML Pipeline settings
    openweathermap_api_key: str = ""
    jolyon_api_base_url: str = "https://api.jolyon.co/f1"
    fastf1_cache_dir: str = "./fastf1_cache"
    model_storage_dir: str = "./ml_models"

    # Scheduler settings
    scheduler_enabled: bool = True
    data_fetch_delay_minutes: int = 30  # delay after session end before fetching data
    max_retries: int = 3

    model_config = {"env_file": ".env"}


settings = Settings()
