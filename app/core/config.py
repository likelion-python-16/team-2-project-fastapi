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

    # 필수 시크릿 (env에 반드시 넣어두세요)
    id_fingerprint_secret: str
    jwt_refresh_secret: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",        # 모르는 키는 금지(엄격 모드 유지)
        case_sensitive=False,  # ENV 키 대소문자 구분 안 함
    )

    # ---------- 외부 서비스 키들 ----------
    # NAVER Cloud Platform - Maps
    naver_maps_client_id: str = os.getenv("NAVER_MAPS_CLIENT_ID", "")
    naver_maps_client_secret: str = os.getenv("NAVER_MAPS_CLIENT_SECRET", "")

    # NAVER Open API (Local Search; 선택)
    naver_search_client_id: str = os.getenv("NAVER_SEARCH_CLIENT_ID", "")
    naver_search_client_secret: str = os.getenv("NAVER_SEARCH_CLIENT_SECRET", "")

    # ✅ JUSO 키를 정식 필드로 선언(대문자 ENV와 매핑)
    juso_search_api_key: str | None = Field(default=None, alias="JUSO_SEARCH_API_KEY")
    juso_coord_api_key:  str | None = Field(default=None, alias="JUSO_COORD_API_KEY")

    # ---------- 런타임 기본 ----------
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True

    # ---------- DB 기본(조립형) ----------
    # *로컬에서 Alembic을 바로 돌릴 땐 127.0.0.1이 안전한 기본값*
    mysql_host: str = os.getenv("MYSQL_HOST", "127.0.0.1")
    mysql_port: int = int(os.getenv("MYSQL_PORT", "3306"))
    mysql_user: str = os.getenv("MYSQL_USER", "team_user")
    mysql_password: str = os.getenv("MYSQL_PASSWORD", "team_password_123")
    mysql_database: str = os.getenv("MYSQL_DATABASE", "team_project_db")
    mysql_root_password: str = os.getenv("MYSQL_ROOT_PASSWORD", "root_password_123")

    # ✅ DSN 직입력 ENV(대문자)를 받는 전용 필드 (extra=forbid를 깨지 않기 위해 별도 이름 사용)
    sqlalchemy_database_url_env: str | None = Field(default=None, alias="SQLALCHEMY_DATABASE_URL")
    database_url_env: str | None = Field(default=None, alias="DATABASE_URL")

    # ---------- JWT ----------
    jwt_secret: str = os.getenv("JWT_SECRET", "team-project-secret-key-change-this-in-production")
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_expire_minutes: int = 10080

    # ---------- Crypto ----------
    fernet_key: str = os.getenv("FERNET_KEY", "")

    # ---------- AWS ----------
    aws_region: str = os.getenv("AWS_REGION", "")
    aws_access_key_id: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    aws_secret_access_key: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    s3_bucket: str = os.getenv("S3_BUCKET", "")

    # ---------- Toss ----------
    toss_client_key: str = os.getenv("TOSS_CLIENT_KEY", "")
    toss_secret_key: str = os.getenv("TOSS_SECRET_KEY", "")

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

    # Social login
    naver_client_id: str = os.getenv("NAVER_CLIENT_ID", "")
    naver_client_secret: str = os.getenv("NAVER_CLIENT_SECRET", "")
    naver_redirect_path: str = os.getenv("NAVER_REDIRECT_PATH", "/api/v1/auth/callback/naver")

    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    google_redirect_path: str = os.getenv("GOOGLE_REDIRECT_PATH", "/api/v1/auth/callback/google")

    # Admin master approver (optional)
    admin_master_username: str = os.getenv("ADMIN_MASTER_USERNAME", "")
    admin_master_email: str = os.getenv("ADMIN_MASTER_EMAIL", "")
    admin_master_password: str = os.getenv("ADMIN_MASTER_PASSWORD", "")

    # Email verification policy (general signup)
    require_email_verification: bool = os.getenv("REQUIRE_EMAIL_VERIFICATION", "false").lower() in ("1","true","yes")

    # Tag taxonomy policy
    allow_dynamic_tag_create: bool = os.getenv("ALLOW_DYNAMIC_TAG_CREATE", "false").lower() in ("1","true","yes")

    # ---------- DB DSN 우선순위 ----------
    # 1) SQLALCHEMY_DATABASE_URL(대문자) → 2) DATABASE_URL(대문자) → 3) 조립형(mysql_* 필드)
    @property
    def database_url(self) -> str:
        dsn = (self.sqlalchemy_database_url_env or self.database_url_env)
        if dsn and dsn.strip():
            return dsn.strip()

        base = (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
        )
        # mysql이면 charset 기본 부여
        return base + "?charset=utf8mb4"

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
    # 로컬 기본 호스트는 127.0.0.1 (Docker DNS 'mysql'이 아닐 수도 있으니)
    mysql_host: str = os.getenv("MYSQL_HOST", "127.0.0.1")

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
TOSS_SECRET_KEY = settings.toss_secret_key
TOSS_CLIENT_KEY = settings.toss_client_key
