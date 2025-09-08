# app/services/naver_maps.py
from __future__ import annotations
import os
import httpx
from fastapi import APIRouter

"""
NOTE:
This module previously exposed stub endpoints under the 
same prefix as the real Naver local router ("/naver").
That caused route collisions with /naver/local. To avoid
masking the real endpoints, we publish any demo/stub routes
under a distinct prefix.
"""

router = APIRouter(prefix="/naver-maps", tags=["Naver Maps"])

NCP_ID  = os.getenv("NAVER_MAPS_CLIENT_ID")  or os.getenv("X_NCP_APIGW_API_KEY_ID")
NCP_KEY = os.getenv("NAVER_MAPS_CLIENT_SECRET") or os.getenv("X_NCP_APIGW_API_KEY")

# Intentionally no overlapping endpoints here.
# The actual search/geocode/staticmap routes live in:
# - app/routers/naver_local.py (/naver/local)
# - app/routers/places.py (/places/geocode, /places/staticmap)

# --- 지오코딩: 주소/장소명 -> 좌표
async def geocode(query: str) -> dict | None:
    if not NCP_ID or not NCP_KEY:
        raise RuntimeError("NAVER_MAPS_CLIENT_ID/SECRET not set")
    url = "https://naveropenapi.apigw.ntruss.com/map-geocode/v2/geocode"
    headers = {
        "X-NCP-APIGW-API-KEY-ID": NCP_ID,
        "X-NCP-APIGW-API-KEY": NCP_KEY,
    }
    params = {"query": query}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url, headers=headers, params=params)
    r.raise_for_status()
    j = r.json()
    if j.get("meta", {}).get("totalCount", 0) == 0:
        return None
    addr = j["addresses"][0]
    return {
        "lat": float(addr["y"]),
        "lng": float(addr["x"]),
        "road_address": addr.get("roadAddress"),
        "address": addr.get("jibunAddress"),
    }

# --- 리버스 지오코딩(선택)
async def reverse_geocode(lat: float, lng: float) -> dict | None:
    if not NCP_ID or not NCP_KEY:
        raise RuntimeError("NAVER_MAPS_CLIENT_ID/SECRET not set")
    url = "https://naveropenapi.apigw.ntruss.com/map-reversegeocode/v2/gc"
    headers = {
        "X-NCP-APIGW-API-KEY-ID": NCP_ID,
        "X-NCP-APIGW-API-KEY": NCP_KEY,
    }
    params = {
        "coords": f"{lng},{lat}",
        "orders": "roadaddr,addr",
        "output": "json",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url, headers=headers, params=params)
    r.raise_for_status()
    j = r.json()
    if not j.get("results"):
        return None

    road = None
    addr = None
    for res in j["results"]:
        if res.get("name") == "roadaddr":
            road = res.get("region", {}).get("area1", {}).get("name")
        # 간단화. 실제로는 구조 파싱해서 문자열 만드는 로직 필요

    return {"address": addr, "road_address": road}

# --- Static Map URL 생성
def build_static_map(lat: float, lng: float, w: int = 360, h: int = 220, level: int = 16, scale: int = 2) -> str:
    # 네이버는 정적지도 이미지 URL로 직접 접근 가능
    base = "https://naveropenapi.apigw.ntruss.com/map-static/v2/raster"
    markers = f"type:d|size:mid|pos:{lng} {lat}"
    # 헤더는 실제 다운로드 시 필요하지만, 우리는 URL만 돌려주고
    # 프론트에서 <img src>에 직접 넣는 대신 백엔드 프록시를 쓰지 않고
    # "서명없는" 접근이 막히는 경우가 있어, 실무에선 백엔드 프록시 권장.
    # 쉬운 방안: 백엔드가 URL을 다시 프록시하지 않고, 그 대신 /preview-static으로
    # RedirectResponse를 주지 않고 "서명 헤더가 필요 없는" 가공 URL을 만들어 전달.
    # (NCP는 정적지도도 헤더 인증 필요 -> 그래서 이 함수는 백엔드 프록시에서 사용 권장)
    # 여기서는 /places/preview-static에서 httpx로 받아 링크를 생성해 주는 방식 사용.

    # 프록시 다운로드가 아닌 "백엔드가 사전 서명 없이 접근한 뒤 URL 제공" 전략:
    # 우리는 /places/preview-static에서 실제 호출 후 임시 Data URL을 못 주므로,
    # 간단화: 네이버 지도 링크만 주고, 프론트에서 이미지는 /places/preview-static이 만든
    # Redirect/프록시를 이미지 src로 사용(아래 라우터 참조).
    return f"{base}?w={w}&h={h}&scale={scale}&level={level}&markers={markers}"

def build_naver_map_url(name: str | None, lat: float, lng: float) -> str:
    if lat and lng:
        return f"https://map.naver.com/v5/?c={lng},{lat},15,0,0,0,dh"
    return f"https://map.naver.com/v5/search/{name or ''}"
