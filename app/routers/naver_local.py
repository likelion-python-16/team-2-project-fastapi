# app/routers/naver_local.py
from fastapi import APIRouter, Query, HTTPException
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
