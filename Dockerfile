# Improved Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY ./app ./app
COPY alembic.ini ./
COPY alembic ./alembic
COPY ./data ./data

# 🔥 환경별 설정
# 개발환경에서만 .env 파일 복사
# 프로덕션에서는 docker compose가 환경변수를 주입하므로 파일을 복사할 필요가 없습니다.
ARG ENV=development
# COPY .env* ./

# 🆕 환경변수 검증 스크립트 추가
COPY <<EOF /app/check_env.py
import os
import sys
from app.core.config import settings

try:
    print(f"Environment: {settings.environment}")
    if settings.is_production:
        settings.validate_required_keys()
        print("✅ Production environment validated")
    else:
        print("✅ Development environment loaded")
except Exception as e:
    print(f"❌ Environment validation failed: {e}")
    sys.exit(1)
EOF

# 환경변수 검증 실행
RUN python check_env.py

# 포트 노출
EXPOSE 8000

# 헬스체크 추가
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 애플리케이션 실행
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]