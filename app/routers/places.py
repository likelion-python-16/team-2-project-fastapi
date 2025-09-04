# app/routers/places.py
from fastapi import APIRouter, HTTPException, Query, Response
import httpx, os
from app.services.naver_search import search_places
from app.services.naver_maps import reverse_geocode, geocode as ncp_geocode, build_naver_map_url

router = APIRouter(prefix="/places", tags=["places"])

# -----------------------------
# 장소 검색
@router.get("/search")
async def search(query: str = Query(..., min_length=1), limit: int = 5):
    items = await search_places(query, display=limit)
    return {"items": items}

# -----------------------------
# 좌표 → 주소 변환
@router.get("/reverse")
async def reverse(lat: float, lng: float):
    data = await reverse_geocode(lat, lng)
    if not data:
        raise HTTPException(404, "주소를 찾을 수 없습니다.")
    return {"address": data.get("address"), "road_address": data.get("road_address")}

# -----------------------------
# 주소 → 좌표 변환
@router.get("/geocode")
async def geocode(query: str = Query(..., description="주소 또는 장소명")):
    data = await ncp_geocode(query)
    if not data:
        raise HTTPException(404, "좌표를 찾을 수 없습니다.")
    return data

# -----------------------------
# ✅ Static Map 이미지 스트리밍
@router.get("/staticmap")
async def staticmap(
    lat: float,
    lng: float,
    w: int = 300,
    h: int = 300,
    level: int = 16,
    scale: int = 2,   # Retina 해상도 (2배)
):
    cid = os.getenv("NAVER_MAPS_CLIENT_ID")
    csec = os.getenv("NAVER_MAPS_CLIENT_SECRET")
    if not cid or not csec:
        raise HTTPException(500, "NAVER_MAPS_CLIENT_ID/SECRET not set")

    # 네이버 지도 Static Map API 제한 → scale=2일 때 w,h 최대 640px
    if w * scale > 1280:
        w = 1280 // scale
    if h * scale > 1280:
        h = 1280 // scale

    url = "https://maps.apigw.ntruss.com/map-static/v2/raster"
    params = {
        "w": w, "h": h, "level": level, "scale": scale,
        "center": f"{lng},{lat}",
        "markers": f"type:d|size:mid|pos:{lng} {lat}"
    }
    headers = {
        "X-NCP-APIGW-API-KEY-ID": cid,
        "X-NCP-APIGW-API-KEY": csec
    }

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url, params=params, headers=headers)

    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=r.text)

    return Response(content=r.content, media_type="image/png")

# -----------------------------
# ✅ JSON Preview (프론트에서 바로 <img> 태그 src로 활용 가능)
@router.get("/preview-static")
async def preview_static(
    lat: float = Query(...),
    lng: float = Query(...),
    scale: int = 2,
    w: int = 600,
    h: int = 300,
    level: int = 16,
):
    return {
        "img_src": f"/places/staticmap?lat={lat}&lng={lng}&w={w}&h={h}&scale={scale}&level={level}",
        "map_url": build_naver_map_url(None, lat, lng),
    }
