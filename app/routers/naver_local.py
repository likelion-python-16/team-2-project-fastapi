# app/routers/naver_local.py
from fastapi import APIRouter, Query, HTTPException
import httpx, os
from typing import Optional

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


@router.get("/resolve-place-id")
async def resolve_place_id(query: str = Query(..., min_length=1), lat: Optional[float] = None, lng: Optional[float] = None):
    """
    베스트에포트: map.naver.com의 검색 API를 사용하여 placeId(=entry/place/{id}) 추출 시도.
    공식 문서가 없어 구조 변경 가능성이 있으므로 실패 시 placeId는 None을 반환합니다.
    """
    # 내부 API (공식 문서화 X). 프런트에서 직접 호출하면 CORS 차단되므로 서버가 호출.
    params = {"caller": "pcweb", "query": query, "type": "all"}
    # 좌표가 있으면 가중치 부여(정확도 향상). 형식은 실제 엔드포인트와 다를 수 있어 무시될 수 있음.
    if lat is not None and lng is not None:
        params["coordinate"] = f"{lng},{lat}"
    url = "https://map.naver.com/v5/api/search"
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(url, params=params)
        if r.status_code != 200:
            return {"placeId": None}
        j = r.json()
    except Exception:
        return {"placeId": None}

    # 구조 탐색: result.place.list[*].id 또는 result.site.list[*].id 등
    def pick_id(data):
        res = data.get("result") if isinstance(data, dict) else None
        if not isinstance(res, dict):
            return None
        # 우선 place 탭
        place = res.get("place") or {}
        lst = place.get("list") or []
        for it in lst:
            pid = (it.get("id") or it.get("placeId") or it.get("key"))
            if pid:
                return str(pid)
        # 사이트/주소 탭 등에서 대체
        site = res.get("site") or {}
        lst2 = site.get("list") or []
        for it in lst2:
            pid = (it.get("id") or it.get("placeId") or it.get("key"))
            if pid:
                return str(pid)
        return None

    pid = pick_id(j)
    return {"placeId": pid}
