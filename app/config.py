import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # 데이터베이스 설정
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "mysql")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "team_user")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "team_password_123")
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "team_project_db")
    
    # API 설정
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    
    # 프로젝트 정보
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "Team Project API")
    PROJECT_VERSION: str = os.getenv("PROJECT_VERSION", "1.0.0")
    PROJECT_DESCRIPTION: str = os.getenv("PROJECT_DESCRIPTION", "팀프로젝트 FastAPI 백엔드")
    
    @property
    def DATABASE_URL(self) -> str:
        return f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"

settings = Settings()