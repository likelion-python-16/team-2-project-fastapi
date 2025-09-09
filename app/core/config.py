# app/core/config.py
import os
from enum import Enum
from functools import lru_cache
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Environment(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"

class Settings(BaseSettings):
    environment: Environment = Environment.DEVELOPMENT
    project_name: str = "Team Project API"
    project_version: str = "1.0.0"
    project_description: str = "팀프로젝트 FastAPI 백엔드"
    id_fingerprint_secret: str = os.getenv("ID_FINGERPRINT_SECRET", "default-fingerprint-secret-change-in-prod")
    # 로깅
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


    # NAVER Cloud Platform - Maps
    naver_maps_client_id: str = os.getenv("NAVER_MAPS_CLIENT_ID", "")
    naver_maps_client_secret: str = os.getenv("NAVER_MAPS_CLIENT_SECRET", "")

    # NAVER Open API (Local Search; 선택)
    naver_search_client_id: str = os.getenv("NAVER_SEARCH_CLIENT_ID", "")
    naver_search_client_secret: str = os.getenv("NAVER_SEARCH_CLIENT_SECRET", "")

    # 행안부(도로명주소) API 키
    juso_search_api_key: str = os.getenv("JUSO_SEARCH_API_KEY", "")
    juso_coord_api_key: str = os.getenv("JUSO_COORD_API_KEY", "")

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True

    # DB
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = "root"
    mysql_database: str = "team2_challenge_dev"
    mysql_root_password: str = "root"

    # JWT
    jwt_secret: str = os.getenv("JWT_SECRET", "team-project-secret-key-change-this-in-production")
    jwt_refresh_secret: str = os.getenv("JWT_REFRESH_SECRET", "team-project-refresh-secret-change-this-in-production")
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

    #toss
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
    smtp_starttls: bool = os.getenv("SMTP_STARTTLS", "false").lower() in ("1", "true", "yes")

    # 기본값을 8000으로 통일 (단일 앱 실행 환경 안전값)
    verification_link_base: str = os.getenv("VERIFICATION_LINK_BASE", "http://localhost:8000/api/v1")
    verify_success_url: str = os.getenv("VERIFY_SUCCESS_URL", "http://localhost:8000/verify/success")
    verify_fail_url: str = os.getenv("VERIFY_FAIL_URL", "http://localhost:8000/verify/fail")
    email_token_expire_minutes: int = int(os.getenv("EMAIL_TOKEN_EXPIRE_MINUTES", "30"))

    # 링크 베이스
    api_base_url: str = os.getenv("API_BASE_URL", "http://localhost/api/v1")
    front_base_url: str = os.getenv("FRONT_BASE_URL", "http://localhost")
    session_secret: str = os.getenv("SESSION_SECRET", "dev-session-secret")
    # Email verification policy (general signup)
    require_email_verification: bool = os.getenv("REQUIRE_EMAIL_VERIFICATION", "false").lower() in ("1","true","yes")
    
    # ---------- Auth: Cookies / JWT (Login) ----------
    auth_access_cookie_name: str = os.getenv("AUTH_ACCESS_COOKIE_NAME", "access_token")
    auth_refresh_cookie_name: str = os.getenv("AUTH_REFRESH_COOKIE_NAME", "refresh_token")
    auth_cookie_domain: str = os.getenv("AUTH_COOKIE_DOMAIN", "")
    auth_cookie_path: str = os.getenv("AUTH_COOKIE_PATH", "/")
    auth_cookie_secure: bool = os.getenv("AUTH_COOKIE_SECURE", "false").lower() in ("1", "true", "yes")
    auth_cookie_http_only: bool = os.getenv("AUTH_COOKIE_HTTP_ONLY", "true").lower() in ("1", "true", "yes")
    auth_cookie_samesite: str = os.getenv("AUTH_COOKIE_SAMESITE", "lax")  # lax | strict | none

    # Optional JWT claims metadata
    jwt_issuer: str = os.getenv("JWT_ISSUER", "team-project-api")
    jwt_audience: str = os.getenv("JWT_AUDIENCE", "team-project-clients")
    
    # Social login
    naver_client_id: str = os.getenv("NAVER_CLIENT_ID", "")
    naver_client_secret: str = os.getenv("NAVER_CLIENT_SECRET", "")
    naver_redirect_path: str = os.getenv("NAVER_REDIRECT_PATH", "/api/v1/auth/callback/naver")

    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    google_redirect_path: str = os.getenv("GOOGLE_REDIRECT_PATH", "/api/v1/auth/callback/google")

    # ---------- Signup Policy ----------
    signup_enabled: bool = os.getenv("SIGNUP_ENABLED", "true").lower() in ("1", "true", "yes")
    signup_default_role: str = os.getenv("SIGNUP_DEFAULT_ROLE", "user")
    signup_min_password_length: int = int(os.getenv("SIGNUP_MIN_PASSWORD_LENGTH", "8"))
    signup_require_number: bool = os.getenv("SIGNUP_REQUIRE_NUMBER", "false").lower() in ("1", "true", "yes")
    signup_require_uppercase: bool = os.getenv("SIGNUP_REQUIRE_UPPERCASE", "false").lower() in ("1", "true", "yes")
    signup_require_special: bool = os.getenv("SIGNUP_REQUIRE_SPECIAL", "false").lower() in ("1", "true", "yes")

    # ---------- Tags / Interests Policy ----------
    # If true, allow creating Tag rows on the fly from interests.keywords
    allow_dynamic_tag_create: bool = os.getenv("ALLOW_DYNAMIC_TAG_CREATE", "true").lower() in ("1","true","yes")

    # ---------- Login Rate Limit ----------
    login_max_attempts: int = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
    login_lockout_minutes: int = int(os.getenv("LOGIN_LOCKOUT_MINUTES", "15"))

    # 초기 관리자 설정
    initial_admin_username: str = os.getenv("INITIAL_ADMIN_USERNAME", "")
    initial_admin_email: str = os.getenv("INITIAL_ADMIN_EMAIL", "")  
    initial_admin_password: str = os.getenv("INITIAL_ADMIN_PASSWORD", "")
    initial_admin_name: str = os.getenv("INITIAL_ADMIN_NAME", "System Admin")
    # Control whether to auto-seed initial admin at startup (default: disabled)
    enable_initial_admin_seed: bool = os.getenv("ENABLE_INITIAL_ADMIN_SEED", "false").lower() in ("1", "true", "yes")

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

    # Convenience flags for social providers
    @property
    def naver_oauth_configured(self) -> bool:
        return bool(self.naver_client_id and self.naver_client_secret and self.naver_redirect_path)

    @property
    def google_oauth_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret and self.google_redirect_path)

    def validate_required_keys(self):
        missing_keys = []
        if self.is_production:
            if not self.fernet_key:
                missing_keys.append("FERNET_KEY")
            if not self.aws_access_key_id:
                missing_keys.append("AWS_ACCESS_KEY_ID")
        if missing_keys:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing_keys)}")

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # 추가 필드 무시

class DevelopmentSettings(Settings):
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = True
    mysql_host: str = "localhost"

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

DATABASE_URL = settings.database_url
JWT_SECRET = settings.jwt_secret
FERNET_KEY = settings.fernet_key
AWS_REGION = settings.aws_region
AWS_ACCESS_KEY_ID = settings.aws_access_key_id
AWS_SECRET_ACCESS_KEY = settings.aws_secret_access_key
S3_BUCKET = settings.s3_bucket
TOSS_SECRET_KEY=settings.toss_secret_key
TOSS_CLIENT_KEY=settings.toss_client_key
