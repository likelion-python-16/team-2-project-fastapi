# FastTeam 배포 및 모니터링 가이드

FastAPI + MySQL 기반의 팀 프로젝트를 위한 완전한 배포 및 모니터링 시스템입니다.

## 🚀 빠른 시작

### 개발 환경 배포
```bash
./deploy.sh dev
```

### 프로덕션 환경 배포
```bash
./deploy.sh prod
```

## 📁 프로젝트 구조

```
FastTeam/
├── 🐳 docker-compose.yml          # 개발용 Docker 구성
├── 🐳 docker-compose.prod.yml     # 프로덕션용 Docker 구성
├── 🚀 deploy.sh                   # 자동 배포 스크립트
├── nginx/                         # Nginx 리버스 프록시 설정
├── monitoring/                    # 모니터링 시스템 설정
│   ├── prometheus.yml            # 메트릭 수집 설정
│   ├── grafana/                  # 대시보드 설정
│   ├── loki/                     # 로그 수집 설정
│   └── promtail/                 # 로그 전송 설정
├── mysql/                        # MySQL 설정
├── .github/workflows/            # CI/CD 파이프라인
└── logs/                         # 로그 파일
```

## 🛠️ 시스템 구성

### 개발 환경 (docker-compose.yml)
- **FastAPI**: 포트 8001
- **MySQL 8.0**: 포트 3307
- **phpMyAdmin**: 포트 8080
- 간단한 구조로 빠른 개발 가능

### 프로덕션 환경 (docker-compose.prod.yml)
- **Nginx**: 포트 80, 443 (리버스 프록시)
- **FastAPI**: 내부 네트워크
- **MySQL 8.0**: 내부 네트워크
- **Redis**: 캐싱 및 세션
- **Prometheus**: 메트릭 수집
- **Grafana**: 모니터링 대시보드
- **Loki + Promtail**: 로그 수집 및 분석

## 📊 모니터링 시스템

### 메트릭 수집
- **Prometheus**: 애플리케이션 메트릭, 시스템 메트릭
- **Custom Metrics**: API 응답시간, 요청 수, 에러율
- **Database Metrics**: 연결 수, 쿼리 성능

### 대시보드
- **Grafana**: `http://monitoring.localhost` (프로덕션)
- **기본 대시보드**: FastAPI API 성능 모니터링
- **실시간 알림**: 임계값 초과 시 알림

### 로그 관리
- **Loki**: 중앙화된 로그 수집
- **Promtail**: 모든 컨테이너 로그 자동 수집
- **구조화된 로그**: JSON 형태로 쿼리 가능

## 🔧 배포 방법

### 1. 수동 배포

#### 개발 환경
```bash
# 기본 배포
./deploy.sh dev

# 이미지 재빌드하여 배포
./deploy.sh dev --rebuild
```

#### 프로덕션 환경
```bash
# 프로덕션 배포 (마이그레이션 포함)
./deploy.sh prod

# 이미지 재빌드하여 배포
./deploy.sh prod --rebuild
```

### 2. 자동 배포 (CI/CD)

GitHub Actions를 통한 자동 배포:

- **develop/donghee 브랜치**: 스테이징 환경 자동 배포
- **main 브랜치**: 프로덕션 환경 배포 (승인 필요)

#### 필요한 GitHub Secrets
```
EC2_HOST=your-staging-server-ip
EC2_USER=ec2-user
EC2_KEY=your-private-key

PROD_HOST=your-production-server-ip
PROD_USER=deploy
PROD_SSH_KEY=your-production-private-key
```

## 📱 접속 정보

### 개발 환경
- **메인 애플리케이션**: http://localhost:8001
- **API 문서**: http://localhost:8001/docs
- **phpMyAdmin**: http://localhost:8080
- **메트릭**: http://localhost:8001/metrics

### 프로덕션 환경
- **메인 애플리케이션**: http://your-domain.com
- **모니터링 대시보드**: http://monitoring.your-domain.com
- **메트릭**: http://your-domain.com/metrics

## 🔒 보안 설정

### Nginx 보안 기능
- Rate Limiting (API: 10req/s, 로그인: 5req/m)
- 보안 헤더 자동 추가
- 정적 파일 캐싱
- 내부 메트릭 엔드포인트 접근 제한

### 환경별 설정
- **개발**: `.env` 파일 사용
- **프로덕션**: `.env.production` 파일 사용
- 민감한 정보는 환경변수로 분리

## 🛠️ 유지보수

### 로그 확인
```bash
# 전체 서비스 로그
docker-compose -f docker-compose.prod.yml logs -f

# 특정 서비스 로그
docker-compose -f docker-compose.prod.yml logs -f api
docker-compose -f docker-compose.prod.yml logs -f mysql
```

### 데이터베이스 백업
```bash
# MySQL 백업
docker-compose -f docker-compose.prod.yml exec mysql \
  mysqldump -u root -p${MYSQL_ROOT_PASSWORD} ${MYSQL_DATABASE} > backup.sql
```

### 컨테이너 상태 확인
```bash
# 서비스 상태 확인
docker-compose -f docker-compose.prod.yml ps

# 리소스 사용량 확인
docker stats
```

### 업데이트
```bash
# 코드 업데이트 후 재배포
git pull origin main
./deploy.sh prod
```

## 📈 성능 최적화

### 애플리케이션 레벨
- Prometheus 메트릭으로 성능 모니터링
- 데이터베이스 연결 풀 최적화
- Redis 캐싱 활용

### 인프라 레벨
- Nginx 압축 및 캐싱
- MySQL 설정 최적화
- Docker 리소스 제한

## 🚨 트러블슈팅

### 자주 발생하는 문제
1. **컨테이너가 시작되지 않는 경우**
   ```bash
   docker-compose logs -f [서비스명]
   ```

2. **데이터베이스 연결 실패**
   - MySQL 컨테이너 헬스체크 확인
   - 환경변수 설정 확인

3. **메트릭이 수집되지 않는 경우**
   - Prometheus 설정 확인
   - 방화벽 설정 확인

### 긴급 복구
```bash
# 모든 서비스 재시작
./deploy.sh prod --rebuild

# 특정 서비스만 재시작
docker-compose -f docker-compose.prod.yml restart api
```

## 📞 지원

문제가 발생하거나 도움이 필요한 경우:
1. 로그 파일 확인
2. Grafana 대시보드에서 메트릭 확인
3. GitHub Issues에 문제 보고

---

**배포 시스템을 통해 안정적이고 확장 가능한 FastTeam 애플리케이션을 운영하세요! 🚀**