from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Safar SFA"
    secret_key: str = "change-this-in-production"
    timezone: str = "Asia/Kolkata"
    timezone_offset: str = "+05:30"

    db_host: str = "localhost"
    db_port: int = 8889
    db_user: str = "root"
    db_password: str = "root"
    db_name: str = "safar_db"

    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080  # 7 days

    admin_username: str = "admin"
    admin_password: str = "admin123"

    cmms_base_url: str = ""
    cmms_api_key: str = ""
    connect_base_url: str = ""
    connect_api_key: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@safar.com"

    @property
    def db_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )


settings = Settings()
