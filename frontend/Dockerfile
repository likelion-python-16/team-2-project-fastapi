FROM nginx:alpine

# 프론트엔드 파일 복사
COPY . /usr/share/nginx/html

# Nginx 설정 (선택사항)
# COPY nginx.conf /etc/nginx/nginx.conf

# 포트 노출
EXPOSE 80

# 헬스체크 추가
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:80 || exit 1

# Nginx 실행
CMD ["nginx", "-g", "daemon off;"]