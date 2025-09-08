# app/routers/naver_local.py
from fastapi import APIRouter, Query, HTTPException
from typing import Optional
import math
import httpx, os

router = APIRouter(prefix="/naver", tags=["Naver"])

@router.get("/local")
async def naver_local_search(
    q: str = Query(..., min_length=1),
    display: int = 10,
    start: int = 1,
    sort: str = "random",
):
    cid  = os.getenv("NAVER_SEARCH_CLIENT_ID") or os.getenv("NAVER_CLIENT_ID")
    csec = os.getenv("NAVER_SEARCH_CLIENT_SECRET") or os.getenv("NAVER_CLIENT_SECRET")
    if not cid or not csec:
        raise HTTPException(500, "NAVER_SEARCH_CLIENT_ID/SECRET not set")

    headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec}
    params = {"query": q, "display": display, "start": start, "sort": sort}

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get("https://openapi.naver.com/v1/search/local.json", headers=headers, params=params)
    if r.status_code != 200:
        raise HTTPException(r.status_code, r.text)

    data = r.json()
    items = []
    for it in data.get("items", []):
        name = (it.get("title") or "").replace("<b>", "").replace("</b>", "")
        mapx, mapy = it.get("mapx"), it.get("mapy")

        # 네이버 지도 URL 강제
        map_url = f"https://map.naver.com/v5/search/{name}"
        try:
            if mapx and mapy:
                x = int(mapx) / 1e7  # 경도
                y = int(mapy) / 1e7  # 위도
                map_url = f"https://map.naver.com/v5/?c={x},{y},15,0,0,0,dh"
        except Exception:
            pass

        items.append({
            "name": name,
            "category": it.get("category") or "",
            "tel": it.get("telephone") or "",
            "address": it.get("address") or "",
            "roadAddress": it.get("roadAddress") or "",
            "map_url": map_url,
        })

    return {"total": data.get("total", 0), "items": items}


@router.get("/local/nearby")
async def search_nearby(
    lat: float = Query(..., ge=-90.0, le=90.0, description="위도"),
    lng: float = Query(..., ge=-180.0, le=180.0, description="경도"),
    radius: float = Query(1.0, ge=0.1, le=50.0, description="반경 km"),
    query: Optional[str] = Query("", description="검색 키워드 (선택)"),
    limit: int = Query(20, ge=1, le=100, description="최대 결과 수"),
):
    """주변 장소 추천 API

    - 내부적으로 네이버 로컬 검색을 사용하고, 반환된 mapx/mapy를 위경도로 변환해
      하버사인 거리로 필터링합니다.
    - 프론트 호환을 위해 { items: [...] } 형태로 반환합니다.
    """
    # 내부 검색 재사용 (표준화: 최대 100건까지 받아서 근접 필터)
    try:
        cid  = os.getenv("NAVER_SEARCH_CLIENT_ID") or os.getenv("NAVER_CLIENT_ID")
        csec = os.getenv("NAVER_SEARCH_CLIENT_SECRET") or os.getenv("NAVER_CLIENT_SECRET")
        if not cid or not csec:
            # 키가 없으면 빈 결과 반환 (500 대신 graceful)
            return {"items": []}

        headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec}
        q = (query or "").strip() or "맛집 카페 병원 편의점"
        params = {"query": q, "display": min(100, max(limit * 2, 10)), "start": 1, "sort": "random"}

        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get("https://openapi.naver.com/v1/search/local.json", headers=headers, params=params)
        if r.status_code != 200:
            return {"items": []}

        data = r.json()
        raw = data.get("items", [])

        def to_deg(mx: str | None, my: str | None):
            try:
                if mx is None or my is None:
                    return None, None
                return (int(mx) / 1e7), (int(my) / 1e7)
            except Exception:
                return None, None

        def haversine(lat1, lon1, lat2, lon2):
            R = 6371.0
            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)
            a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            return R * c

        out = []
        for it in raw:
            name = (it.get("title") or "").replace("<b>", "").replace("</b>", "")
            mx, my = it.get("mapx"), it.get("mapy")
            lon2, lat2 = to_deg(mx, my)  # 주의: mapx=경도, mapy=위도 → (lon, lat)
            if lat2 is None or lon2 is None:
                continue
            dist = haversine(lat, lng, lat2, lon2)
            if dist <= radius:
                # 프론트 호환 필드 구성
                out.append({
                    "title": name,
                    "name": name,
                    "roadAddress": it.get("roadAddress") or "",
                    "address": it.get("address") or "",
                    "distance": round(dist, 3),
                    "link": f"https://map.naver.com/v5/?c={lon2},{lat2},15,0,0,0,dh",
                    "placeId": None,
                })

        # 거리 순 정렬 후 제한
        out.sort(key=lambda x: x.get("distance") or 9999)
        return {"items": out[:limit]}
    except Exception:
        return {"items": []}


@router.get("/resolve-place-id")
async def resolve_place_id(
    query: str = Query(..., description="장소명"),
    lat: Optional[float] = Query(None),
    lng: Optional[float] = Query(None),
):
    """호환용 엔드포인트. 현재 placeId는 사용하지 않으므로 항상 None 반환.

    프론트 일부 코드(challenge_create.html)가 있으면 호출하지만,
    실제 동작에는 영향을 주지 않습니다. 콘솔 404를 없애기 위한 더미 구현입니다.
    """
    return {"placeId": None}
