# app/core/config.py
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from enum import Enum
from functools import lru_cache
import os
from typing import Literal, Optional

class Environment(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"

class Settings(BaseSettings):
    # ===== 기본 =====
    environment: Environment = Environment.DEVELOPMENT
    project_name: str = "Team Project API"
    project_version: str = "1.0.0"
    project_description: str = "팀프로젝트 FastAPI 백엔드"

    # ===== API =====
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True

    # ===== DB =====
    mysql_host: str = "mysql"
    mysql_port: int = 3306
    mysql_user: str = "team_user"
    mysql_password: str = "team_password_123"
    mysql_database: str = "team_project_db"
    mysql_root_password: str = "root_password_123"

    # (둘 다 지원) database_url 필드로도 받고, 없으면 조합해서 사용
    database_url: Optional[str] = Field(default=None, validation_alias="DATABASE_URL")

    # ===== JWT / 보안 =====
    # .env가 둘 중 아무 키든 오게 허용: secret_key / JWT_SECRET
    secret_key: Optional[str] = Field(default=None, validation_alias="SECRET_KEY")
    jwt_secret: str = Field(
        default="team-project-secret-key-change-this-in-production",
        validation_alias="JWT_SECRET",
    )
    # .env가 둘 중 아무 키든 오게 허용: algorithm / JWT_ALGORITHM
    algorithm: Optional[str] = Field(default=None, validation_alias="ALGORITHM")
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    # .env가 둘 중 아무 키든 오게 허용:
    # access_token_expire_minutes / JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    access_token_expire_minutes: Optional[int] = Field(
        default=None, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    jwt_access_token_expire_minutes: int = Field(
        default=30, validation_alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES"
    )

    # ===== 필드 암호화/외부키 =====
    # .env가 둘 중 아무 키든 오게 허용: field_aes_key / FERNET_KEY
    field_aes_key: Optional[str] = Field(default=None, validation_alias="FIELD_AES_KEY")
    fernet_key: str = Field(default="", validation_alias="FERNET_KEY")

    kakao_rest_key: Optional[str] = Field(default=None, validation_alias="KAKAO_REST_KEY")

    # ===== AWS =====
    aws_region: str = Field(default="", validation_alias="AWS_REGION")
    aws_access_key_id: str = Field(default="", validation_alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(default="", validation_alias="AWS_SECRET_ACCESS_KEY")
    s3_bucket: str = Field(default="", validation_alias="S3_BUCKET")

    # ===== 로깅 =====
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", validation_alias="LOG_LEVEL"
    )

    # ===== CORS =====
    allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:8080",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8080",
            "http://54.180.237.228:3000",
            "http://54.180.237.228:8080",
        ]
    )

    # ===== v2 설정 =====
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",  # 모델에 없는 키는 무시 (필요 시 'forbid'로 강화)
    )

    # ===== 계산 프로퍼티 =====
    @property
    def resolved_secret_key(self) -> str:
        # secret_key 우선 → 없으면 jwt_secret 사용
        return self.secret_key or self.jwt_secret

    @property
    def resolved_algorithm(self) -> str:
        return self.algorithm or self.jwt_algorithm

    @property
    def resolved_access_token_expire_minutes(self) -> int:
        return self.access_token_expire_minutes or self.jwt_access_token_expire_minutes

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
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
        """프로덕션에서만 필수 키 체크"""
        if not self.is_production:
            return
        missing = []
        if not (self.field_aes_key or self.fernet_key):
            missing.append("FIELD_AES_KEY/FERNET_KEY")
        if not self.aws_access_key_id:
            missing.append("AWS_ACCESS_KEY_ID")
        if missing:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


# ===== 환경 클래스들 =====
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

# 하위 호환 노출
DATABASE_URL = settings.resolved_database_url
JWT_SECRET = settings.resolved_secret_key
FERNET_KEY = settings.field_aes_key or settings.fernet_key
AWS_REGION = settings.aws_region
AWS_ACCESS_KEY_ID = settings.aws_access_key_id
AWS_SECRET_ACCESS_KEY = settings.aws_secret_access_key
S3_BUCKET = settings.s3_bucket
