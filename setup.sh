#!/bin/bash

echo "=== 팀프로젝트 개발환경 설정 ==="

# 색상 정의
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

# 환경 변수 파일 생성
setup_env() {
    if [ ! -f .env ]; then
        print_status ".env 파일을 .env.example에서 복사합니다..."
        cp .env.example .env
        print_warning ".env 파일을 프로젝트에 맞게 수정해주세요!"
    else
        print_status ".env 파일이 이미 존재합니다."
    fi
}

# SQL 초기화 디렉토리 생성
setup_sql() {
    if [ ! -d "sql" ]; then
        mkdir sql
        print_status "sql 디렉토리가 생성되었습니다."
    fi
}

# 🆕 Alembic 초기화
setup_alembic() {
    print_header "Alembic 설정"
    
    # Alembic 디렉토리가 없으면 초기화
    if [ ! -d "alembic" ]; then
        print_status "Alembic 초기화 중..."
        
        # requirements.txt에 alembic이 있는지 확인
        if ! grep -q "alembic" requirements.txt; then
            print_warning "requirements.txt에 alembic을 추가하는 것을 권장합니다."
        fi
        
        # alembic.ini 파일이 있는지 확인
        if [ ! -f "alembic.ini" ]; then
            print_warning "alembic.ini 파일이 없습니다. 프로젝트 설정을 확인해주세요."
        else
            print_status "✅ Alembic 설정 파일이 준비되었습니다."
        fi
    else
        print_status "✅ Alembic이 이미 초기화되어 있습니다."
    fi
}

# Docker 설치 확인
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker가 설치되지 않았습니다."
        print_status "Docker 설치 가이드: https://docs.docker.com/get-docker/"
        return 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose가 설치되지 않았습니다."
        print_status "Docker Compose 설치 가이드: https://docs.docker.com/compose/install/"
        return 1
    fi

    print_status "Docker 환경이 준비되었습니다."
    return 0
}

# 개발 환경 실행
start_dev() {
    print_header "개발 환경 시작"
    
    print_status "Docker 컨테이너를 빌드하고 실행합니다..."
    docker-compose -f docker-compose.local.yml up --build -d
    
    print_status "컨테이너 상태 확인 중..."
    sleep 10
    docker-compose -f docker-compose.local.yml ps
    
    # 🆕 Alembic 마이그레이션 실행
    print_status "데이터베이스 마이그레이션 적용 중..."
    sleep 5
    
    # API 컨테이너에서 Alembic 실행
    if docker-compose -f docker-compose.local.yml exec -T api alembic upgrade head; then
        print_status "✅ 데이터베이스 마이그레이션 완료"
    else
        print_warning "⚠️ 마이그레이션 실행 중 문제가 발생했습니다. 수동으로 확인해주세요."
        print_status "수동 실행: docker-compose -f docker-compose.local.yml exec api alembic upgrade head"
    fi
    
    print_status "헬스 체크 수행 중..."
    sleep 5
    
    for i in {1..10}; do
        if curl -f http://localhost:8001/health 2>/dev/null; then
            print_status "✅ API 서버가 정상 실행 중입니다!"
            break
        else
            print_warning "API 서버 대기 중... ($i/10)"
            sleep 3
        fi
    done
}

# 접속 정보 출력
print_access_info() {
    print_header "접속 정보"
    echo "🚀 API 서버: http://localhost:8001"
    echo "📚 API 문서: http://localhost:8001/docs"
    echo "❤️  헬스체크: http://localhost:8001/health"
    echo "🗄️  phpMyAdmin: http://localhost:8081"
    echo ""
    echo "📋 데이터베이스 정보:"
    echo "   Host: localhost:3307"
    echo "   Database: team_project_db"
    echo "   Username: team_user"
    echo "   Password: team_password_123"
    echo ""
    echo "🛠️  개발 명령어:"
    echo "   docker-compose -f docker-compose.local.yml logs -f        # 로그 확인"
    echo "   docker-compose -f docker-compose.local.yml restart       # 재시작"
    echo "   docker-compose -f docker-compose.local.yml down          # 중지"
    echo "   docker-compose -f docker-compose.local.yml exec api sh   # API 컨테이너 접속"
    echo "   docker-compose -f docker-compose.local.yml exec mysql mysql -u team_user -p team_project_db  # MySQL 접속"
    echo ""
    echo "🗄️  Alembic 명령어:"
    echo "   docker-compose -f docker-compose.local.yml exec api alembic revision --autogenerate -m 'description'  # 새 마이그레이션 생성"
    echo "   docker-compose -f docker-compose.local.yml exec api alembic upgrade head                              # 마이그레이션 적용"
    echo "   docker-compose -f docker-compose.local.yml exec api alembic downgrade -1                              # 마이그레이션 롤백"
    echo "   docker-compose -f docker-compose.local.yml exec api alembic current                                   # 현재 마이그레이션 상태"
    echo "   docker-compose -f docker-compose.local.yml exec api alembic history                                   # 마이그레이션 히스토리"
}

# 메인 실행
main() {
    print_header "팀프로젝트 개발환경 설정 시작"
    
    # 환경 확인
    if ! check_docker; then
        exit 1
    fi
    
    # 환경 설정
    setup_env
    setup_sql
    setup_alembic
    
    # 개발자에게 선택권 제공
    echo ""
    echo "다음 중 선택하세요:"
    echo "1) 개발 환경 시작 (docker-compose up + 마이그레이션)"
    echo "2) 환경 설정만 하고 종료"
    echo ""
    read -p "선택 (1 또는 2): " choice
    
    case $choice in
        1)
            start_dev
            print_access_info
            ;;
        2)
            print_status "환경 설정이 완료되었습니다."
            print_status "개발을 시작하려면: docker-compose -f docker-compose.local.yml up --build -d"
            print_status "마이그레이션 적용: docker-compose -f docker-compose.local.yml exec api alembic upgrade head"
            ;;
        *)
            print_warning "잘못된 선택입니다. 환경 설정만 완료합니다."
            ;;
    esac
    
    print_status "설정 완료! 팀 개발을 시작하세요! 🎉"
}

# 스크립트 실행
main "$@"