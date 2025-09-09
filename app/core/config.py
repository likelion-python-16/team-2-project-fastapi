# app/core/config.py
import os
from enum import Enum
from functools import lru_cache
from typing import Optional

from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()

class Environment(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"

class Settings(BaseSettings):
    # Pydantic v2 Settings
    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),  # ← 로컬 우선, 그다음 공용
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # 정의 안 된 .env 키는 무시
    )

    environment: Environment = Environment.DEVELOPMENT
    project_name: str = "Team Project API"
    project_version: str = "1.0.0"
    project_description: str = "팀프로젝트 FastAPI 백엔드"

    # 로깅
    log_level: str = Field(default="INFO", validation_alias=AliasChoices("LOG_LEVEL", "log_level"))

    # NAVER Cloud Platform - Maps
    naver_maps_client_id: str = Field(default="", validation_alias=AliasChoices("NAVER_MAPS_CLIENT_ID", "naver_maps_client_id"))
    naver_maps_client_secret: str = Field(default="", validation_alias=AliasChoices("NAVER_MAPS_CLIENT_SECRET", "naver_maps_client_secret"))

    # NAVER Open API (Local Search)
    naver_search_client_id: str = Field(default="", validation_alias=AliasChoices("NAVER_SEARCH_CLIENT_ID", "naver_search_client_id"))
    naver_search_client_secret: str = Field(default="", validation_alias=AliasChoices("NAVER_SEARCH_CLIENT_SECRET", "naver_search_client_secret"))

    # 행안부(도로명주소) API 키
    juso_search_api_key: str = Field(default="", validation_alias=AliasChoices("JUSO_SEARCH_API_KEY", "juso_search_api_key"))
    juso_coord_api_key: str = Field(default="", validation_alias=AliasChoices("JUSO_COORD_API_KEY", "juso_coord_api_key"))

    # API
    api_host: str = Field(default="0.0.0.0", validation_alias=AliasChoices("API_HOST", "api_host"))
    api_port: int = Field(default=8000, validation_alias=AliasChoices("API_PORT", "api_port"))
    debug: bool = Field(default=True, validation_alias=AliasChoices("DEBUG", "debug"))

    # DB
    mysql_host: str = Field(default="mysql", validation_alias=AliasChoices("MYSQL_HOST", "mysql_host"))
    mysql_port: int = Field(default=3306, validation_alias=AliasChoices("MYSQL_PORT", "mysql_port"))
    mysql_user: str = Field(default="team_user", validation_alias=AliasChoices("MYSQL_USER", "mysql_user"))
    mysql_password: str = Field(default="team_password_123", validation_alias=AliasChoices("MYSQL_PASSWORD", "mysql_password"))
    mysql_database: str = Field(default="team_project_db", validation_alias=AliasChoices("MYSQL_DATABASE", "mysql_database"))
    mysql_root_password: str = Field(default="root_password_123", validation_alias=AliasChoices("MYSQL_ROOT_PASSWORD", "mysql_root_password"))

    # DATABASE_URL (직접 지정값 우선)
    database_url_raw: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("DATABASE_URL", "database_url"),
    )

    # JWT (레거시 키 alias 포함)
    jwt_secret: str = Field(
        default="team-project-secret-key-change-this-in-production",
        validation_alias=AliasChoices("JWT_SECRET", "SECRET_KEY", "secret_key"),
    )
    jwt_refresh_secret: str = Field(
        default="team-project-refresh-secret-change-this-in-production",
        validation_alias=AliasChoices("JWT_REFRESH_SECRET", "jwt_refresh_secret"),
    )
    jwt_algorithm: str = Field(
        default="HS256",
        validation_alias=AliasChoices("JWT_ALGORITHM", "ALGORITHM", "algorithm"),
    )
    jwt_access_token_expire_minutes: int = Field(
        default=60,
        validation_alias=AliasChoices("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "ACCESS_TOKEN_EXPIRE_MINUTES", "access_token_expire_minutes"),
    )
    jwt_refresh_expire_minutes: int = Field(
        default=10080,
        validation_alias=AliasChoices("JWT_REFRESH_EXPIRE_MINUTES", "jwt_refresh_expire_minutes"),
    )

    # Crypto (레거시 AES 키 alias 포함)
    fernet_key: str = Field(default="", validation_alias=AliasChoices("FERNET_KEY", "FIELD_AES_KEY", "field_aes_key"))

    # Kakao (레거시 키 흡수)
    kakao_rest_key: Optional[str] = Field(default=None, validation_alias=AliasChoices("KAKAO_REST_KEY", "kakao_rest_key"))

    # Social Login
    google_client_id: str = Field(default="", validation_alias=AliasChoices("GOOGLE_CLIENT_ID", "google_client_id"))
    google_client_secret: str = Field(default="", validation_alias=AliasChoices("GOOGLE_CLIENT_SECRET", "google_client_secret"))
    google_redirect_path: str = Field(default="/api/v1/auth/callback/google",
                                      validation_alias=AliasChoices("GOOGLE_REDIRECT_PATH", "google_redirect_path"))

    naver_client_id: str = Field(default="", validation_alias=AliasChoices("NAVER_CLIENT_ID", "naver_client_id"))
    naver_client_secret: str = Field(default="", validation_alias=AliasChoices("NAVER_CLIENT_SECRET", "naver_client_secret"))
    naver_redirect_path: str = Field(default="/api/v1/auth/callback/naver",
                                     validation_alias=AliasChoices("NAVER_REDIRECT_PATH", "naver_redirect_path"))

    # AWS
    aws_region: str = Field(default="", validation_alias=AliasChoices("AWS_REGION", "aws_region"))
    aws_access_key_id: str = Field(default="", validation_alias=AliasChoices("AWS_ACCESS_KEY_ID", "aws_access_key_id"))
    aws_secret_access_key: str = Field(default="", validation_alias=AliasChoices("AWS_SECRET_ACCESS_KEY", "aws_secret_access_key"))
    s3_bucket: str = Field(default="", validation_alias=AliasChoices("S3_BUCKET", "s3_bucket"))

    # Toss
    toss_client_key: str = Field(default="", validation_alias=AliasChoices("TOSS_CLIENT_KEY", "toss_client_key"))
    toss_secret_key: str = Field(default="", validation_alias=AliasChoices("TOSS_SECRET_KEY", "toss_secret_key"))

    # Origins
    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
        "http://54.180.237.228:3000",
        "http://54.180.237.228:8080",
    ]

    # 메일/링크
    mail_from: str = Field(default="no-reply@example.com", validation_alias=AliasChoices("MAIL_FROM", "mail_from"))
    smtp_host: str = Field(default="", validation_alias=AliasChoices("SMTP_HOST", "smtp_host"))
    smtp_port: int = Field(default=465, validation_alias=AliasChoices("SMTP_PORT", "smtp_port"))
    smtp_user: str = Field(default="", validation_alias=AliasChoices("SMTP_USER", "smtp_user"))
    smtp_pass: str = Field(default="", validation_alias=AliasChoices("SMTP_PASS", "smtp_pass"))

    verification_link_base: str = Field(default="http://localhost:8000/api/v1", validation_alias=AliasChoices("VERIFICATION_LINK_BASE", "verification_link_base"))
    verify_success_url: str = Field(default="http://localhost:8000/verify/success", validation_alias=AliasChoices("VERIFY_SUCCESS_URL", "verify_success_url"))
    verify_fail_url: str = Field(default="http://localhost:8000/verify/fail", validation_alias=AliasChoices("VERIFY_FAIL_URL", "verify_fail_url"))
    email_token_expire_minutes: int = Field(default=30, validation_alias=AliasChoices("EMAIL_TOKEN_EXPIRE_MINUTES", "email_token_expire_minutes"))

    api_base_url: str = Field(default="http://localhost/api/v1", validation_alias=AliasChoices("API_BASE_URL", "api_base_url"))
    front_base_url: str = Field(default="http://localhost", validation_alias=AliasChoices("FRONT_BASE_URL", "front_base_url"))
    session_secret: str = Field(default="dev-session-secret", validation_alias=AliasChoices("SESSION_SECRET", "session_secret"))

    # 이메일 인증 정책
    require_email_verification: bool = Field(
        default=False,
        validation_alias=AliasChoices("REQUIRE_EMAIL_VERIFICATION", "require_email_verification"),
    )

    # 초기 관리자
    initial_admin_username: str = Field(default="", validation_alias=AliasChoices("INITIAL_ADMIN_USERNAME", "initial_admin_username"))
    initial_admin_email: str = Field(default="", validation_alias=AliasChoices("INITIAL_ADMIN_EMAIL", "initial_admin_email"))
    initial_admin_password: str = Field(default="", validation_alias=AliasChoices("INITIAL_ADMIN_PASSWORD", "initial_admin_password"))
    initial_admin_name: str = Field(default="System Admin", validation_alias=AliasChoices("INITIAL_ADMIN_NAME", "initial_admin_name"))

    # 유틸
    id_fingerprint_secret: str = Field(
        default="default-fingerprint-secret-change-in-prod",
        validation_alias=AliasChoices("ID_FINGERPRINT_SECRET", "id_fingerprint_secret"),
    )

    @property
    def database_url(self) -> str:
        if self.database_url_raw and self.database_url_raw.strip():
            return self.database_url_raw.strip()
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
        )

    @property
    def is_development(self) -> bool:
        return self.environment == Environment.DEVELOPMENT

    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION

    def validate_required_keys(self):
        missing_keys = []
        if self.is_production:
            if not self.fernet_key:
                missing_keys.append("FERNET_KEY")
            if not self.aws_access_key_id:
                missing_keys.append("AWS_ACCESS_KEY_ID")
        if missing_keys:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing_keys)}")

class DevelopmentSettings(Settings):
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = True
    mysql_host: str = Field(default="mysql", validation_alias=AliasChoices("MYSQL_HOST", "mysql_host"))

class ProductionSettings(Settings):
    environment: Environment = Environment.PRODUCTION
    debug: bool = False
    jwt_secret: str = Field(
        default="CHANGE-THIS-TO-SUPER-SECURE-KEY-FOR-PRODUCTION",
        validation_alias=AliasChoices("JWT_SECRET", "SECRET_KEY", "secret_key"),
    )
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.validate_required_keys()

class TestingSettings(Settings):
    environment: Environment = Environment.TESTING
    debug: bool = True
    mysql_database: str = Field(default="test_team_project_db", validation_alias=AliasChoices("MYSQL_DATABASE", "mysql_database"))

@lru_cache()
def get_settings() -> Settings:
    env = os.getenv("ENVIRONMENT", "development").lower()
    if env == "production":
        return ProductionSettings()
    elif env == "testing":
        return TestingSettings()
    else:
        return DevelopmentSettings()

settings = get_settings()

# 편의 export
DATABASE_URL = settings.database_url
JWT_SECRET = settings.jwt_secret
FERNET_KEY = settings.fernet_key
AWS_REGION = settings.aws_region
AWS_ACCESS_KEY_ID = settings.aws_access_key_id
AWS_SECRET_ACCESS_KEY = settings.aws_secret_access_key
S3_BUCKET = settings.s3_bucket
TOSS_SECRET_KEY = settings.toss_secret_key
TOSS_CLIENT_KEY = settings.toss_client_key

