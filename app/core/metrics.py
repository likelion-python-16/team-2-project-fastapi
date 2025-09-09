from prometheus_client import Counter, Histogram, Gauge, generate_latest
from fastapi import Request, Response
from typing import Callable
import time

# 메트릭 정의
REQUEST_COUNT = Counter(
    'fastapi_requests_total',
    'Total number of requests',
    ['method', 'endpoint', 'status_code']
)

REQUEST_DURATION = Histogram(
    'fastapi_request_duration_seconds',
    'Time spent processing requests',
    ['method', 'endpoint']
)

ACTIVE_CONNECTIONS = Gauge(
    'fastapi_active_connections',
    'Active connections'
)

DATABASE_CONNECTIONS = Gauge(
    'fastapi_database_connections_active',
    'Active database connections'
)

ERROR_COUNT = Counter(
    'fastapi_errors_total',
    'Total number of errors',
    ['error_type']
)

# 메트릭 미들웨어
class MetricsMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        method = request.method
        path = request.url.path
        
        # 건강 체크나 메트릭 엔드포인트는 제외
        if path in ["/health", "/metrics"]:
            await self.app(scope, receive, send)
            return

        start_time = time.time()
        ACTIVE_CONNECTIONS.inc()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code = message["status"]
                
                # 메트릭 업데이트
                REQUEST_COUNT.labels(
                    method=method,
                    endpoint=path,
                    status_code=status_code
                ).inc()
                
                REQUEST_DURATION.labels(
                    method=method,
                    endpoint=path
                ).observe(time.time() - start_time)
                
                # 에러 카운트
                if status_code >= 400:
                    if status_code >= 500:
                        ERROR_COUNT.labels(error_type="server_error").inc()
                    else:
                        ERROR_COUNT.labels(error_type="client_error").inc()
                        
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            ACTIVE_CONNECTIONS.dec()

def get_metrics():
    """Prometheus 메트릭 반환"""
    return generate_latest()