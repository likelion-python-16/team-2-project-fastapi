# app/core/config.py
import os
from enum import Enum
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from dotenv import load_dotenv

# Ensure values from .env override any pre-set envs in container
load_dotenv(override=True)

class Environment(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"

class Settings(BaseSettings):
    environment: Environment = Environment.DEVELOPMENT
    project_name: str = "Team Project API"
    project_version: str = "1.0.0"
    project_description: str = "팀프로젝트 FastAPI 백엔드"
    id_fingerprint_secret: str
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",      # 🔒 모르는 키는 금지(엄격 모드로 유지하고 싶으면)
        case_sensitive=False
    )

    # ✅ JUSO 키를 정식 필드로 선언(대문자 ENV와 매핑)
    juso_search_api_key: str | None = Field(default=None, alias="JUSO_SEARCH_API_KEY")
    juso_coord_api_key:  str | None = Field(default=None, alias="JUSO_COORD_API_KEY")

    # NAVER Cloud Platform - Maps
    naver_maps_client_id: str = os.getenv("NAVER_MAPS_CLIENT_ID", "")
    naver_maps_client_secret: str = os.getenv("NAVER_MAPS_CLIENT_SECRET", "")

    # NAVER Open API (Local Search; 선택)
    naver_search_client_id: str = os.getenv("NAVER_SEARCH_CLIENT_ID", "")
    naver_search_client_secret: str = os.getenv("NAVER_SEARCH_CLIENT_SECRET", "")

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True

    # DB
    mysql_host: str = "mysql"
    mysql_port: int = 3306
    mysql_user: str = "team_user"
    mysql_password: str = "team_password_123"
    mysql_database: str = "team_project_db"
    mysql_root_password: str = "root_password_123"

    # JWT
    jwt_secret: str = os.getenv("JWT_SECRET", "team-project-secret-key-change-this-in-production")
    jwt_refresh_secret: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_expire_minutes: int = 10080

    # Crypto
    fernet_key: str = os.getenv("FERNET_KEY", "")

    # AWS
    aws_region: str = os.getenv("AWS_REGION", "")
    aws_access_key_id: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    aws_secret_access_key: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    s3_bucket: str = os.getenv("S3_BUCKET", "")

    # CORS
    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
        "http://54.180.237.228:3000",
        "http://54.180.237.228:8080",
    ]

    # ---------- 메일/링크 설정 ----------
    mail_from: str = os.getenv("MAIL_FROM", "no-reply@example.com")
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "465"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_pass: str = os.getenv("SMTP_PASS", "")

    # 기본값을 8000으로 통일 (단일 앱 실행 환경 안전값)
    verification_link_base: str = os.getenv("VERIFICATION_LINK_BASE", "http://localhost:8000/api/v1")
    verify_success_url: str = os.getenv("VERIFY_SUCCESS_URL", "http://localhost:8000/verify/success")
    verify_fail_url: str = os.getenv("VERIFY_FAIL_URL", "http://localhost:8000/verify/fail")
    email_token_expire_minutes: int = int(os.getenv("EMAIL_TOKEN_EXPIRE_MINUTES", "30"))

    # 링크 베이스
    api_base_url: str = os.getenv("API_BASE_URL", "http://localhost:8001/api/v1")
    front_base_url: str = os.getenv("FRONT_BASE_URL", "http://localhost:8000")
    session_secret: str = os.getenv("SESSION_SECRET", "dev-session-secret")
    # Admin master approver (optional)
    admin_master_username: str = os.getenv("ADMIN_MASTER_USERNAME", "")
    admin_master_email: str = os.getenv("ADMIN_MASTER_EMAIL", "")
    admin_master_password: str = os.getenv("ADMIN_MASTER_PASSWORD", "")
    # Email verification policy (general signup)
    require_email_verification: bool = os.getenv("REQUIRE_EMAIL_VERIFICATION", "false").lower() in ("1","true","yes")

    # Social login
    naver_client_id: str = os.getenv("NAVER_CLIENT_ID", "")
    naver_client_secret: str = os.getenv("NAVER_CLIENT_SECRET", "")
    naver_redirect_path: str = os.getenv("NAVER_REDIRECT_PATH", "/api/v1/auth/callback/naver")

    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    google_redirect_path: str = os.getenv("GOOGLE_REDIRECT_PATH", "/api/v1/auth/callback/google")

    @property
    def database_url(self) -> str:
        env_url = os.getenv("DATABASE_URL")
        if env_url and env_url.strip():
            return env_url.strip()
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
    mysql_host: str = "mysql"

class ProductionSettings(Settings):
    environment: Environment = Environment.PRODUCTION
    debug: bool = False
    jwt_secret: str = os.getenv("JWT_SECRET", "CHANGE-THIS-TO-SUPER-SECURE-KEY-FOR-PRODUCTION")
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.validate_required_keys()

class TestingSettings(Settings):
    environment: Environment = Environment.TESTING
    debug: bool = True
    mysql_database: str = "test_team_project_db"

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

# (선택) 기존 별칭
DATABASE_URL = settings.database_url
JWT_SECRET = settings.jwt_secret
FERNET_KEY = settings.fernet_key
AWS_REGION = settings.aws_region
AWS_ACCESS_KEY_ID = settings.aws_access_key_id
AWS_SECRET_ACCESS_KEY = settings.aws_secret_access_key
S3_BUCKET = settings.s3_bucket
