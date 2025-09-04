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
    params = {"caller": "pcweb", "query": query, "type": "all"}
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

    def pick_id(data):
        res = data.get("result") if isinstance(data, dict) else None
        if not isinstance(res, dict):
            return None
        place = res.get("place") or {}
        lst = place.get("list") or []
        for it in lst:
            pid = (it.get("id") or it.get("placeId") or it.get("key"))
            if pid:
                return str(pid)
        site = res.get("site") or {}
        lst2 = site.get("list") or []
        for it in lst2:
            pid = (it.get("id") or it.get("placeId") or it.get("key"))
            if pid:
                return str(pid)
        return None

    pid = pick_id(j)
    return {"placeId": pid}


@router.get("/nearby")
async def naver_nearby_places(
    lat: float = Query(...),
    lng: float = Query(...),
    q: Optional[str] = "",
    limit: int = 10,
):
    """
    좌표 기준 주변 장소 추천.
    내부 API(map.naver.com/v5/api/search)를 'caller=pcweb'로 호출하여,
    좌표 가중치를 둔 place 리스트를 받아옵니다.
    """
    url = "https://map.naver.com/v5/api/search"
    params = {
        "caller": "pcweb",
        "query": (q or "").strip(),
        "type": "all",
        "displayCount": limit,     # 명시: limit 반영
        "coordinate": f"{lng},{lat}",  # 네이버는 lng,lat 순
    }

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(url, params=params)
        if r.status_code != 200:
            return {"items": []}
        data = r.json()
    except Exception:
        return {"items": []}

    def make_link(pid: Optional[str], lat: Optional[float], lng: Optional[float], title: str):
        lvl = 15
        if pid:
            c = f"?c={lng},{lat},{lvl},0,0,0,dh" if (lat is not None and lng is not None) else ""
            return f"https://map.naver.com/v5/entry/place/{pid}{c}"
        key = (title or "").strip()
        if key:
            c = f"?c={lng},{lat},{lvl},0,0,0,dh" if (lat is not None and lng is not None) else ""
            return f"https://map.naver.com/v5/search/{httpx.QueryParams({'': key})._dict['']}{c}"
        return "https://map.naver.com/v5"

    items = []
    try:
        place = (data or {}).get("result", {}).get("place", {})
        lst = place.get("list") or []
        for it in lst:
            pid = str(it.get("id") or it.get("placeId") or it.get("key") or "").strip() or None
            title = (it.get("name") or it.get("title") or "").strip()
            road = it.get("roadAddress") or ""
            addr = it.get("address") or ""
            link = make_link(pid, lat, lng, title)
            items.append({
                "title": title,
                "roadAddress": road,
                "address": addr,
                "placeId": pid,
                "link": link,
            })
            if len(items) >= limit:
                break
    except Exception:
        items = []

    return {"items": items}
