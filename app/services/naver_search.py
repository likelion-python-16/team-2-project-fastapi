# app/services/naver_search.py (선택)
import httpx
from html import unescape
from app.core.config import settings
from app.services.naver_maps import geocode, build_naver_map_url

NAVER_LOCAL_URL = "https://openapi.naver.com/v1/search/local.json"

def _search_headers():
    return {
        "X-Naver-Client-Id": settings.naver_search_client_id or "",
        "X-Naver-Client-Secret": settings.naver_search_client_secret or "",
    }

async def search_places(query: str, display: int = 5):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(NAVER_LOCAL_URL, headers=_search_headers(), params={"query": query, "display": display})
        r.raise_for_status()
        data = r.json()
        items = data.get("items", [])
        results = []
        for it in items:
            title = unescape(it.get("title", "")).replace("<b>", "").replace("</b>", "")
            road_addr = it.get("roadAddress")
            jibun_addr = it.get("address")
            lat = lng = None
            geo = None
            if road_addr:
                try:
                    geo = await geocode(road_addr)
                except Exception:
                    geo = None
            if geo:
                lat, lng = geo["lat"], geo["lng"]
                road_addr = geo.get("road_address") or road_addr
                if not jibun_addr:
                    jibun_addr = geo.get("address")
            map_url = build_naver_map_url(title, lat, lng)  # ← 마지막 None 제거!
            results.append({
                "place_name": title or query,
                "address": jibun_addr,
                "road_address": road_addr,
                "latitude": lat,
                "longitude": lng,
                "map_url": map_url,
            })
