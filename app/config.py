# app/config.py - 환경별 설정 관리
import os
from enum import Enum
from functools import lru_cache
from pydantic_settings import BaseSettings


class Environment(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"


class Settings(BaseSettings):
    # 기본 설정
    environment: Environment = Environment.DEVELOPMENT
    project_name: str = "Team Project API"
    project_version: str = "1.0.0"
    project_description: str = "팀프로젝트 FastAPI 백엔드"
    
    # API 설정
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True
    
    # 데이터베이스 설정 (현재 EC2 환경 기준)
    mysql_host: str = "localhost"  # EC2에서는 localhost (로컬 MySQL 컨테이너)
    mysql_port: int = 3306
    # TODO: 실제 프로젝트에서 사용할 MySQL 사용자명/비밀번호로 변경 필요
    mysql_user: str = "team_user"  # 현재 .env에서 사용 중인 값
    mysql_password: str = "team_password_123"  # 현재 .env에서 사용 중인 값
    mysql_database: str = "team_project_db"  # 현재 사용 중
    mysql_root_password: str = "root_password_123"  # 현재 .env에서 사용 중인 값
    
    # RDS 사용시 (현재는 주석처리)
    # mysql_host: str = "myapp-mysql.c7cmcg408xvn.ap-northeast-2.rds.amazonaws.com"
    # mysql_user: str = "admin"
    # mysql_password: str = "rjschd159951"
    
    # JWT 설정 - TODO: 실제 프로젝트에서는 더 강력한 키로 변경
    jwt_secret: str = "team-project-secret-key-change-this-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    
    # CORS 설정 (현재 EC2 IP 포함)
    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
        "http://54.180.237.228:3000",  # EC2 IP - 프론트엔드용
        "http://54.180.237.228:8080",  # EC2 IP - phpMyAdmin용
        # TODO: 실제 도메인 주소 추가 필요 (도메인 설정시)
        # "https://yourdomain.com",
    ]
    
    @property
    def database_url(self) -> str:
        return f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
    
    @property
    def is_development(self) -> bool:
        return self.environment == Environment.DEVELOPMENT
    
    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION
    
    class Config:
        env_file = ".env"
        case_sensitive = False


class DevelopmentSettings(Settings):
    """개발 환경 설정"""
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = True
    
    # 개발용 데이터베이스 (로컬 Docker 컨테이너)
    mysql_host: str = "localhost"
    mysql_user: str = "team_user"  # 현재 docker-compose.yml에서 사용 중
    mysql_password: str = "team_password_123"


class ProductionSettings(Settings):
    """프로덕션 환경 설정"""
    environment: Environment = Environment.PRODUCTION
    debug: bool = False
    
    # 프로덕션용 데이터베이스 (현재 EC2 로컬 MySQL 사용)
    mysql_host: str = "localhost"  # EC2에서 Docker MySQL 컨테이너 사용
    mysql_user: str = "team_user"
    mysql_password: str = "team_password_123"
    
    # RDS 사용시 주석 해제하고 위 3줄 주석처리
    # mysql_host: str = "myapp-mysql.c7cmcg408xvn.ap-northeast-2.rds.amazonaws.com"
    # mysql_user: str = "admin"
    # mysql_password: str = "rjschd159951"
    
    # CORS - 프로덕션에서는 EC2 IP 포함
    allowed_origins: list[str] = [
        "http://54.180.237.228:3000",  # EC2 프론트엔드
        "http://54.180.237.228:8080",  # EC2 phpMyAdmin
        # TODO: 실제 도메인 설정시 추가
        # "https://yourdomain.com",
        # "https://api.yourdomain.com",
    ]
    
    # TODO: 프로덕션에서는 더 강력한 JWT 시크릿 사용
    jwt_secret: str = "CHANGE-THIS-TO-SUPER-SECURE-KEY-FOR-PRODUCTION"


class TestingSettings(Settings):
    """테스트 환경 설정"""
    environment: Environment = Environment.TESTING
    debug: bool = True
    
    # 테스트용 데이터베이스
    mysql_database: str = "test_team_project_db"


@lru_cache()
def get_settings() -> Settings:
    """환경에 따른 설정 반환"""
    env = os.getenv("ENVIRONMENT", "development").lower()
    
    if env == "production":
        return ProductionSettings()
    elif env == "testing":
        return TestingSettings()
    else:
        return DevelopmentSettings()


# 전역 설정 인스턴스
settings = get_settings()