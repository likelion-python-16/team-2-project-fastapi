# app/core/config.py
import os
import json
from enum import Enum
from functools import lru_cache
from typing import List, Optional

from pydantic import Field, AliasChoices, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()


class Environment(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"


class Settings(BaseSettings):
    # pydantic-settings v2 구성
    # - .env.local, .env 둘 다 읽기
    # - 대소문자 비구분
    # - 알 수 없는 키는 무시(과거 env 키가 있어도 extra_forbidden 안 뜸)
    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 공통
    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        validation_alias=AliasChoices("ENVIRONMENT", "environment"),
    )
    project_name: str = Field(default="Team Project API")
    project_version: str = Field(default="1.0.0")
    project_description: str = Field(default="팀프로젝트 FastAPI 백엔드")

    # 필수 보안 값 (개발에선 기본값, 운영에선 검증)
    id_fingerprint_secret: str = Field(
        default="change-this-in-production",
        validation_alias=AliasChoices("ID_FINGERPRINT_SECRET", "id_fingerprint_secret"),
    )

    # NAVER Cloud Platform - Maps
    naver_maps_client_id: str = Field(
        default="",
        validation_alias=AliasChoices("NAVER_MAPS_CLIENT_ID", "naver_maps_client_id"),
    )
    naver_maps_client_secret: str = Field(
        default="",
        validation_alias=AliasChoices("NAVER_MAPS_CLIENT_SECRET", "naver_maps_client_secret"),
    )

    # NAVER Open API (Local Search; 선택)
    naver_search_client_id: str = Field(
        default="",
        validation_alias=AliasChoices("NAVER_SEARCH_CLIENT_ID", "naver_search_client_id"),
    )
    naver_search_client_secret: str = Field(
        default="",
        validation_alias=AliasChoices("NAVER_SEARCH_CLIENT_SECRET", "naver_search_client_secret"),
    )

    # API
    api_host: str = Field(default="0.0.0.0", validation_alias=AliasChoices("API_HOST", "api_host"))
    api_port: int = Field(default=8000, validation_alias=AliasChoices("API_PORT", "api_port"))
    debug: bool = Field(default=True, validation_alias=AliasChoices("DEBUG", "debug"))
    log_level: str = Field(default="INFO", validation_alias=AliasChoices("LOG_LEVEL", "log_level"))

    # DB (직접 구성 값)
    mysql_host: str = Field(default="mysql", validation_alias=AliasChoices("MYSQL_HOST", "mysql_host"))
    mysql_port: int = Field(default=3306, validation_alias=AliasChoices("MYSQL_PORT", "mysql_port"))
    mysql_user: str = Field(default="team_user", validation_alias=AliasChoices("MYSQL_USER", "mysql_user"))
    mysql_password: str = Field(default="team_password_123", validation_alias=AliasChoices("MYSQL_PASSWORD", "mysql_password"))
    mysql_database: str = Field(default="team_project_db", validation_alias=AliasChoices("MYSQL_DATABASE", "mysql_database"))
    mysql_root_password: str = Field(default="root_password_123", validation_alias=AliasChoices("MYSQL_ROOT_PASSWORD", "mysql_root_password"))

    # DB (직접 URL 주입시 사용) — 과거 키(database_url)도 흡수
    database_url_env: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("DATABASE_URL", "database_url"),
    )

    # JWT — 과거 SECRET_KEY/secret_key도 흡수
    jwt_secret: str = Field(
        default="team-project-secret-key-change-this-in-production",
        validation_alias=AliasChoices("JWT_SECRET", "jwt_secret", "SECRET_KEY", "secret_key"),
    )
    jwt_refresh_secret: str = Field(
        default="team-project-refresh-secret-change-in-prod",
        validation_alias=AliasChoices("JWT_REFRESH_SECRET", "jwt_refresh_secret"),
    )
    jwt_algorithm: str = Field(default="HS256", validation_alias=AliasChoices("JWT_ALGORITHM", "jwt_algorithm", "ALGORITHM", "algorithm"))
    jwt_access_token_expire_minutes: int = Field(
        default=60,
        validation_alias=AliasChoices("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "jwt_access_token_expire_minutes", "ACCESS_TOKEN_EXPIRE_MINUTES", "access_token_expire_minutes"),
    )
    jwt_refresh_expire_minutes: int = Field(
        default=60 * 24 * 7,
        validation_alias=AliasChoices("JWT_REFRESH_EXPIRE_MINUTES", "jwt_refresh_expire_minutes"),
    )

    # Crypto — 과거 FIELD_AES_KEY도 흡수(값을 그대로 사용)
    fernet_key: str = Field(
        default="",
        validation_alias=AliasChoices("FERNET_KEY", "fernet_key", "FIELD_AES_KEY", "field_aes_key"),
    )

    # AWS
    aws_region: str = Field(default="", validation_alias=AliasChoices("AWS_REGION", "aws_region"))
    aws_access_key_id: str = Field(default="", validation_alias=AliasChoices("AWS_ACCESS_KEY_ID", "aws_access_key_id"))
    aws_secret_access_key: str = Field(default="", validation_alias=AliasChoices("AWS_SECRET_ACCESS_KEY", "aws_secret_access_key"))
    s3_bucket: str = Field(default="", validation_alias=AliasChoices("S3_BUCKET", "s3_bucket"))

    # CORS
    allowed_origins: List[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:8080",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8080",
            "http://54.180.237.228:3000",
            "http://54.180.237.228:8080",
        ],
        validation_alias=AliasChoices("ALLOWED_ORIGINS", "allowed_origins"),
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _coerce_origins(cls, v):
        """
        ALLOWED_ORIGINS 가 문자열로 들어오면
        - JSON 배열 문자열 (예: '["http://a","http://b"]') 이거나
        - 콤마 구분 (예: "http://a,http://b")
        둘 다 허용.
        """
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            if s.startswith("["):
                try:
                    return json.loads(s)
                except Exception:
                    pass
            return [x.strip() for x in s.split(",") if x.strip()]
        return v

    @property
    def database_url(self) -> str:
        # 명시적인 DATABASE_URL이 있으면 우선 사용
        if self.database_url_env and self.database_url_env.strip():
            return self.database_url_env.strip()
        # 그렇지 않으면 구성 값으로 조합
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
        missing = []
        # 운영에서만 강제
        if self.is_production:
            if not self.fernet_key:
                missing.append("FERNET_KEY (또는 FIELD_AES_KEY)")
            if not self.aws_access_key_id:
                missing.append("AWS_ACCESS_KEY_ID")
            if not self.jwt_secret or self.jwt_secret.startswith("team-project-secret-key-change"):
                missing.append("JWT_SECRET")
            if not self.jwt_refresh_secret or self.jwt_refresh_secret.startswith("team-project-refresh-secret-change"):
                missing.append("JWT_REFRESH_SECRET")
            if not self.id_fingerprint_secret or self.id_fingerprint_secret.startswith("change-this-in-production"):
                missing.append("ID_FINGERPRINT_SECRET")
        if missing:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


class DevelopmentSettings(Settings):
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = True
    mysql_host: str = "mysql"


class ProductionSettings(Settings):
    environment: Environment = Environment.PRODUCTION
    debug: bool = False

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

# 하위 호환용 모듈 레벨 상수 (기존 코드가 참조해도 동작하도록 유지)
DATABASE_URL = settings.database_url
JWT_SECRET = settings.jwt_secret
FERNET_KEY = settings.fernet_key
AWS_REGION = settings.aws_region
AWS_ACCESS_KEY_ID = settings.aws_access_key_id
AWS_SECRET_ACCESS_KEY = settings.aws_secret_access_key
S3_BUCKET = settings.s3_bucket
