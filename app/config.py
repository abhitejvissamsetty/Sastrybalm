import hmac

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Deployment tooling may supply infrastructure-only variables (for example
    # MYSQL_ROOT_PASSWORD). Ignore those instead of preventing application/test
    # startup; only declared application settings are consumed.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Safar SFA"
    environment: str = "development"
    secret_key: str = ""
    cors_origins: str = "http://localhost:8080,http://127.0.0.1:8080"
    secure_cookies: bool = False
    enable_api_docs: bool = True
    timezone: str = "Asia/Kolkata"
    timezone_offset: str = "+05:30"

    db_host: str = "localhost"
    db_port: int = 8889
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "safar_db"

    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080  # 7 days

    admin_username: str = "admin"
    admin_password: str = ""
    backup_encryption_key: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@safar.com"

    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.1
    metrics_token: str = ""
    parquet_backup_retention_days: int = 2555

    @property
    def trusted_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    def validate_runtime_security(self) -> None:
        if not self.is_production:
            return
        insecure_application_secrets = {
            "change-this-in-production",
            "change-this-to-a-long-random-string-in-production",
            "admin123",
        }
        insecure_database_passwords = {
            "", "root", "rootpassword", "safar_password",
            "sastrybalm_password", "password",
        }
        if len(self.secret_key) < 32 or self.secret_key in insecure_application_secrets:
            raise RuntimeError("Production SECRET_KEY must be a unique value of at least 32 characters.")
        if self.db_user.lower() == "root":
            raise RuntimeError("Production DB_USER must be a least-privilege application account, not root.")
        if self.db_password.lower() in insecure_database_passwords or len(self.db_password) < 16:
            raise RuntimeError("Production DB_PASSWORD must be a rotated value of at least 16 characters.")
        if self.admin_password in insecure_application_secrets or len(self.admin_password) < 16:
            raise RuntimeError("Production ADMIN_PASSWORD must be a rotated value of at least 16 characters.")
        if len(self.backup_encryption_key) < 32:
            raise RuntimeError(
                "Production BACKUP_ENCRYPTION_KEY must be a unique value of at least 32 characters."
            )
        if hmac.compare_digest(self.backup_encryption_key, self.secret_key):
            raise RuntimeError(
                "Production BACKUP_ENCRYPTION_KEY must be independent from SECRET_KEY."
            )
        if not self.smtp_host:
            raise RuntimeError("Production SMTP_HOST is required.")
        if not self.smtp_password or len(self.smtp_password) < 16:
            raise RuntimeError("Production SMTP_PASSWORD must be a rotated value of at least 16 characters.")
        if not self.secure_cookies:
            raise RuntimeError("Production SECURE_COOKIES must be enabled.")
        if self.enable_api_docs:
            raise RuntimeError("Production ENABLE_API_DOCS must be disabled.")
        if not self.trusted_cors_origins or any("*" in origin for origin in self.trusted_cors_origins):
            raise RuntimeError("Production CORS_ORIGINS must contain explicit trusted origins.")
        if any(not origin.startswith("https://") for origin in self.trusted_cors_origins):
            raise RuntimeError("Production CORS_ORIGINS must use HTTPS.")
        if not self.sentry_dsn.startswith("https://"):
            raise RuntimeError("Production SENTRY_DSN must be an HTTPS DSN.")
        if not 0 <= self.sentry_traces_sample_rate <= 1:
            raise RuntimeError(
                "SENTRY_TRACES_SAMPLE_RATE must be between zero and one."
            )
        if len(self.metrics_token) < 32:
            raise RuntimeError(
                "Production METRICS_TOKEN must contain at least 32 characters."
            )
        if self.parquet_backup_retention_days < 365:
            raise RuntimeError(
                "Production PARQUET_BACKUP_RETENTION_DAYS must be at least 365."
            )

    @property
    def db_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )


settings = Settings()
