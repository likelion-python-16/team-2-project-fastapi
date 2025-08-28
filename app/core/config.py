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

    class Config:
        env_file = ".env"
        case_sensitive = False

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

DATABASE_URL = settings.database_url
JWT_SECRET = settings.jwt_secret
FERNET_KEY = settings.fernet_key
AWS_REGION = settings.aws_region
AWS_ACCESS_KEY_ID = settings.aws_access_key_id
AWS_SECRET_ACCESS_KEY = settings.aws_secret_access_key
S3_BUCKET = settings.s3_bucket
TOSS_SECRET_KEY=settings.toss_secret_key
TOSS_CLIENT_KEY=settings.toss_client_key