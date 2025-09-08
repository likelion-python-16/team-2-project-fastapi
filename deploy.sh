#!/bin/bash

# FastTeam 배포 스크립트
# 사용법: ./deploy.sh [dev|prod] [--rebuild]

set -e  # 에러 발생 시 스크립트 중단

# 색상 코드
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로깅 함수
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# 기본 설정
ENVIRONMENT=${1:-dev}
REBUILD=${2:-false}
PROJECT_NAME="fastteam"
COMPOSE_FILE=""

# 환경별 설정
case $ENVIRONMENT in
    "dev"|"development")
        COMPOSE_FILE="docker-compose.yml"
        ENV_FILE=".env"
        log_info "개발 환경으로 배포합니다."
        ;;
    "prod"|"production")
        COMPOSE_FILE="docker-compose.prod.yml"
        ENV_FILE=".env.production"
        log_info "프로덕션 환경으로 배포합니다."
        ;;
    "aws"|"ec2")
        COMPOSE_FILE="docker-compose.prod.yml"
        ENV_FILE=".env.production"
        log_info "AWS EC2 환경으로 배포합니다."
        ;;
    *)
        log_error "잘못된 환경입니다. 'dev', 'prod', 또는 'aws'를 선택하세요."
        ;;
esac

# 필수 파일 체크
check_requirements() {
    log_info "배포 환경을 확인하고 있습니다..."
    
    # Docker 설치 확인
    if ! command -v docker &> /dev/null; then
        log_error "Docker가 설치되지 않았습니다."
    fi
    
    # Docker Compose 설치 확인
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose가 설치되지 않았습니다."
    fi
    
    # Compose 파일 확인
    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "Compose 파일($COMPOSE_FILE)을 찾을 수 없습니다."
    fi
    
    # 환경 설정 파일 확인
    if [ ! -f "$ENV_FILE" ]; then
        log_error "환경 설정 파일($ENV_FILE)을 찾을 수 없습니다."
    fi
    
    log_success "모든 요구사항이 충족되었습니다."
}

# 기존 컨테이너 정리
cleanup_containers() {
    log_info "기존 컨테이너를 정리하고 있습니다..."
    
    docker-compose -f "$COMPOSE_FILE" down --remove-orphans
    
    if [ "$REBUILD" = "--rebuild" ]; then
        log_info "이미지를 다시 빌드합니다..."
        docker-compose -f "$COMPOSE_FILE" build --no-cache
        
        # 사용하지 않는 이미지 정리
        docker image prune -f
    fi
    
    log_success "컨테이너 정리가 완료되었습니다."
}

# 데이터베이스 마이그레이션
run_migrations() {
    log_info "데이터베이스 마이그레이션을 실행하고 있습니다..."
    
    # MySQL 컨테이너가 시작될 때까지 대기
    docker-compose -f "$COMPOSE_FILE" up -d mysql
    
    # MySQL 헬스체크 대기
    log_info "데이터베이스 연결을 대기하고 있습니다..."
    sleep 30
    
    # 마이그레이션 실행
    docker-compose -f "$COMPOSE_FILE" run --rm api alembic upgrade head
    
    log_success "데이터베이스 마이그레이션이 완료되었습니다."
}

# 애플리케이션 시작
start_application() {
    log_info "애플리케이션을 시작하고 있습니다..."
    
    docker-compose -f "$COMPOSE_FILE" up -d
    
    log_info "컨테이너 상태를 확인하고 있습니다..."
    sleep 15
    
    # 헬스체크
    if [ "$ENVIRONMENT" = "prod" ]; then
        HEALTH_URL="http://localhost/health"
    else
        HEALTH_URL="http://localhost:8001/health"
    fi
    
    # 최대 60초 대기
    for i in {1..12}; do
        if curl -f -s "$HEALTH_URL" > /dev/null; then
            log_success "애플리케이션이 성공적으로 시작되었습니다!"
            break
        else
            log_info "헬스체크 대기 중... ($i/12)"
            sleep 5
        fi
        
        if [ $i -eq 12 ]; then
            log_warning "헬스체크가 실패했습니다. 로그를 확인하세요."
        fi
    done
}

# 상태 확인
check_status() {
    log_info "배포된 서비스 상태:"
    docker-compose -f "$COMPOSE_FILE" ps
    
    echo ""
    log_info "서비스 접속 정보:"
    
    if [ "$ENVIRONMENT" = "prod" ]; then
        echo "🌐 웹 애플리케이션: http://localhost"
        echo "📊 모니터링 대시보드: http://monitoring.localhost"
        echo "📈 메트릭: http://localhost/metrics"
    else
        echo "🌐 웹 애플리케이션: http://localhost:8001"
        echo "📊 phpMyAdmin: http://localhost:8080"
        echo "📈 메트릭: http://localhost:8001/metrics"
        echo "📝 API 문서: http://localhost:8001/docs"
    fi
}

# 메인 실행
main() {
    log_info "🚀 FastTeam 배포를 시작합니다..."
    echo "Environment: $ENVIRONMENT"
    echo "Compose File: $COMPOSE_FILE"
    echo "Rebuild: $REBUILD"
    echo ""
    
    check_requirements
    cleanup_containers
    
    if [ "$ENVIRONMENT" = "prod" ]; then
        run_migrations
    fi
    
    start_application
    check_status
    
    log_success "🎉 배포가 완료되었습니다!"
}

# 도움말
show_help() {
    echo "FastTeam 배포 스크립트"
    echo ""
    echo "사용법:"
    echo "  ./deploy.sh [환경] [옵션]"
    echo ""
    echo "환경:"
    echo "  dev, development   개발 환경 (기본값)"
    echo "  prod, production   프로덕션 환경"
    echo ""
    echo "옵션:"
    echo "  --rebuild          Docker 이미지 재빌드"
    echo "  --help, -h         도움말 표시"
    echo ""
    echo "예시:"
    echo "  ./deploy.sh dev              # 개발 환경 배포"
    echo "  ./deploy.sh prod --rebuild   # 프로덕션 환경 재빌드 배포"
}

# 파라미터 처리
if [ "$1" = "--help" ] || [ "$1" = "-h" ] || [ -z "$1" ]; then
    show_help
    exit 0
fi

# 메인 함수 실행
main