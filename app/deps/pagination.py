from fastapi import Query

def pagination_params(
    skip: int = Query(0, ge=0, description="건너뛸 레코드 수 (offset)"),
    limit: int = Query(10, ge=1, le=100, description="가져올 최대 레코드 수"),
):
    """
    공통 페이징 의존성
    - skip: 시작 위치 (offset)
    - limit: 가져올 데이터 수 (최대 100)
    """
    return {"skip": skip, "limit": limit}
