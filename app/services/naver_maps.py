# app/services/naver_maps.py
import httpx
from urllib.parse import quote
from app.core.config import settings

NAVER_STATIC_URL = "https://maps.apigw.ntruss.com/map-static/v2"
# ✅ 실제 호출 엔드포인트로 교체
NAVER_GEOCODE_URL = "https://maps.apigw.ntruss.com/map-geocode/v2/geocode"
NAVER_REVERSE_URL = "https://maps.apigw.ntruss.com/map-reversegeocode/v2/gc"

def _maps_headers():
    key_id = (settings.naver_maps_client_id or "").strip()
    key = (settings.naver_maps_client_secret or "").strip()
    if not key_id or not key:
        # 값이 비어있으면 httpx Headers에 None이 들어가서 타입 에러 → 여기서 명확히 막기
        raise RuntimeError("NCP Maps 키가 설정되지 않았습니다. (.env의 NAVER_MAPS_CLIENT_ID / NAVER_MAPS_CLIENT_SECRET)")
    return {
        "X-NCP-APIGW-API-KEY-ID": key_id,
        "X-NCP-APIGW-API-KEY": key,
    }

async def geocode(road_address: str):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(NAVER_GEOCODE_URL, headers=_maps_headers(), params={"query": road_address})
        r.raise_for_status()
        data = r.json()
        if not data.get("addresses"):
            return None
        a0 = data["addresses"][0]
        lat = float(a0["y"]); lng = float(a0["x"])
        return {
            "road_address": a0.get("roadAddress"),
            "address": a0.get("jibunAddress"),
            "lat": lat,
            "lng": lng
        }

async def reverse_geocode(lat: float, lng: float):
    params = {"coords": f"{lng},{lat}", "orders": "roadaddr,addr", "output": "json"}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(NAVER_REVERSE_URL, headers=_maps_headers(), params=params)
        r.raise_for_status()
        data = r.json()
        results = data.get("results", [])
        def join(x):
            if not x: return None
            region = x["region"]; land = x.get("land") or {}
            parts = [region["area1"]["name"], region["area2"]["name"], region["area3"]["name"], region["area4"]["name"]]
            if land.get("name"): parts.append(land["name"])
            if land.get("number1"):
                num = land["number1"]
                if land.get("number2"): num += "-" + land["number2"]
                parts.append(num)
            return " ".join([p for p in parts if p])
        road = next((x for x in results if x.get("name")=="roadaddr"), None)
        addr = next((x for x in results if x.get("name")=="addr"), None)
        return {"road_address": join(road), "address": join(addr)}

def build_naver_map_url(place_name: str | None, lat: float | None, lng: float | None, place_id: str | None = None) -> str:
    """
    네이버 지도 URL 생성
    - 좌표가 있으면 지도 좌표 링크
    - 없으면 검색 URL
    - 좌표 URL 끝에는 ,dh 를 붙여야 바로 이동 가능
    """
    if lat is not None and lng is not None:
        return f"https://map.naver.com/v5/?c={lng},{lat},15,0,0,0,dh"

    key = (place_name or "").strip()
    return f"https://map.naver.com/v5/search/{quote(key)}"

def build_static_map(lat: float, lng: float, scale: int = 2, w: int = 600, h: int = 400) -> str:
    return (f"{NAVER_STATIC_URL}?w={w}&h={h}&scale={scale}"
            f"&center={lng},{lat}&level=15&markers=type:d|{lng},{lat}")
