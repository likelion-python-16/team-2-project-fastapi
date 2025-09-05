# app/routers/naver_local.py
from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import httpx, os, asyncio, re
from urllib.parse import quote, unquote
import json
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.config import settings
from app.core.deps import get_current_user_soft
from app.models.user import User
from sqlalchemy.orm import Session

router = APIRouter(prefix="/naver", tags=["Naver"])

# Enhanced response models
class PlaceInfo(BaseModel):
    """장소 정보 모델"""
    name: str
    category: str = ""
    tel: str = ""
    address: str = ""
    roadAddress: str = ""
    mapx: Optional[str] = None
    mapy: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    map_url: str = ""
    naver_url: Optional[str] = None
    distance: Optional[float] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    
    class Config:
        from_attributes = True

class SearchResponse(BaseModel):
    """검색 응답 모델"""
    total: int
    start: int
    display: int
    items: List[PlaceInfo]
    query: str
    cached: bool = False
    search_time: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Simple in-memory cache for search results (15 minutes)
SEARCH_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_DURATION = timedelta(minutes=15)

# Utility functions
def clean_html_tags(text: str) -> str:
    """HTML 태그 제거"""
    return re.sub(r'<[^>]+>', '', text)

def clean_category(category: str) -> str:
    """카테고리 정리 (> 기호로 분리된 경우 마지막 항목만)"""
    if '>' in category:
        return category.split('>')[-1].strip()
    return category.strip()

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 점 사이의 거리 계산 (km)"""
    import math
    
    # Haversine formula
    R = 6371  # Earth's radius in kilometers
    
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    a = (math.sin(dlat / 2) * math.sin(dlat / 2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) * math.sin(dlon / 2))
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c

# Enhanced search with caching and additional features
@router.get("/local", response_model=SearchResponse)
async def naver_local_search(
    q: str = Query(..., min_length=1, max_length=100, description="검색 키워드"),
    display: int = Query(10, ge=1, le=100, description="검색 결과 출력 건수"),
    start: int = Query(1, ge=1, le=1000, description="검색 시작 위치"),
    sort: str = Query("random", regex="^(random|comment)$", description="정렬 옵션"),
    include_coords: bool = Query(True, description="좌표 정보 포함"),
    cache_enabled: bool = Query(True, description="캐시 사용 여부"),
    current_user: Optional[User] = Depends(get_current_user_soft),
):
    """네이버 지역 검색 API (Enhanced with caching and additional features)"""
    
    # Create cache key
    cache_key = f"{q}:{display}:{start}:{sort}:{include_coords}"
    
    # Check cache first
    if cache_enabled and cache_key in SEARCH_CACHE:
        cache_entry = SEARCH_CACHE[cache_key]
        if datetime.now() - cache_entry["timestamp"] < CACHE_DURATION:
            cache_entry["data"]["cached"] = True
            return cache_entry["data"]
        else:
            # Remove expired cache entry
            del SEARCH_CACHE[cache_key]
    
    # Get credentials
    cid = (settings.naver_search_client_id or os.getenv("NAVER_SEARCH_CLIENT_ID") or os.getenv("NAVER_CLIENT_ID"))
    csec = (settings.naver_search_client_secret or os.getenv("NAVER_SEARCH_CLIENT_SECRET") or os.getenv("NAVER_CLIENT_SECRET"))
    if not cid or not csec:
        # Graceful fallback: return empty results instead of 500
        return SearchResponse(total=0, start=start, display=display, items=[], query=q, cached=False, search_time=datetime.now())

    headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec}
    params = {"query": q, "display": display, "start": start, "sort": sort}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get("https://openapi.naver.com/v1/search/local.json", headers=headers, params=params)
        
        if r.status_code != 200:
            # Return empty results gracefully
            return SearchResponse(total=0, start=start, display=display, items=[], query=q, cached=False, search_time=datetime.now())

        data = r.json()
        items = []
        
        for it in data.get("items", []):
            name = clean_html_tags(it.get("title") or "")
            mapx, mapy = it.get("mapx"), it.get("mapy")
            latitude, longitude = None, None

            # Enhanced URL generation
            map_url = f"https://map.naver.com/v5/search/{quote(name)}"
            naver_url = None
            
            try:
                if mapx and mapy:
                    longitude = int(mapx) / 1e7  # 경도
                    latitude = int(mapy) / 1e7  # 위도
                    if include_coords:
                        map_url = f"https://map.naver.com/v5/?c={longitude},{latitude},15,0,0,0,dh"
                        naver_url = f"https://map.naver.com/v5/entry/place/{it.get('link', '')}"
            except (ValueError, TypeError):
                pass

            # Clean and process data
            category = clean_category(it.get("category") or "")
            address = it.get("address") or ""
            road_address = it.get("roadAddress") or ""
            
            place_info = PlaceInfo(
                name=name,
                category=category,
                tel=it.get("telephone") or "",
                address=address,
                roadAddress=road_address,
                mapx=mapx,
                mapy=mapy,
                latitude=latitude if include_coords else None,
                longitude=longitude if include_coords else None,
                map_url=map_url,
                naver_url=naver_url
            )
            items.append(place_info)

        # Create response
        response_data = SearchResponse(
            total=data.get("total", 0),
            start=start,
            display=display,
            items=items,
            query=q,
            cached=False,
            search_time=datetime.now()
        )
        
        # Cache the result
        if cache_enabled:
            SEARCH_CACHE[cache_key] = {
                "timestamp": datetime.now(),
                "data": response_data
            }
            
            # Clean old cache entries (simple LRU-like behavior)
            if len(SEARCH_CACHE) > 100:
                oldest_key = min(SEARCH_CACHE.keys(), key=lambda k: SEARCH_CACHE[k]["timestamp"])
                del SEARCH_CACHE[oldest_key]

        return response_data
        
    except httpx.TimeoutException:
        return SearchResponse(total=0, start=start, display=display, items=[], query=q, cached=False, search_time=datetime.now())
    except httpx.RequestError:
        return SearchResponse(total=0, start=start, display=display, items=[], query=q, cached=False, search_time=datetime.now())
    except Exception:
        return SearchResponse(total=0, start=start, display=display, items=[], query=q, cached=False, search_time=datetime.now())

# Legacy endpoint for backward compatibility
@router.get("/local/legacy")
async def naver_local_search_legacy(
    q: str = Query(..., min_length=1),
    display: int = 10,
    start: int = 1,
    sort: str = "random",
):
    """네이버 지역 검색 API (Legacy format)"""
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

# New enhanced endpoints
@router.get("/local/nearby")
async def search_nearby_places(
    lat: float = Query(..., ge=-90, le=90, description="위도"),
    lng: float = Query(..., ge=-180, le=180, description="경도"),
    radius: float = Query(1.0, ge=0.1, le=10.0, description="검색 반경 (km)"),
    query: str = Query("", description="검색 키워드 (선택)"),
    category: str = Query("", description="카테고리 필터"),
    limit: int = Query(20, ge=1, le=100, description="결과 개수"),
    current_user: Optional[User] = Depends(get_current_user_soft),
):
    """근처 장소 검색 (위치 기반)"""
    try:
        # Base search query
        search_query = query if query else "맛집 카페 병원 편의점"
        if category:
            search_query = f"{category} {search_query}"
        
        # Use existing search function
        search_response = await naver_local_search(
            q=search_query,
            display=min(limit * 2, 100),  # Get more results to filter by distance
            start=1,
            sort="random",
            include_coords=True,
            cache_enabled=True,
            current_user=current_user
        )
        
        # Filter by distance
        nearby_places = []
        for place in search_response.items:
            if place.latitude and place.longitude:
                distance = calculate_distance(lat, lng, place.latitude, place.longitude)
                if distance <= radius:
                    place.distance = round(distance, 2)
                    nearby_places.append(place)
        
        # Sort by distance and limit results
        nearby_places.sort(key=lambda x: x.distance or float('inf'))
        nearby_places = nearby_places[:limit]
        
        return {
            "success": True,
            "center_lat": lat,
            "center_lng": lng,
            "radius": radius,
            "query": search_query,
            "total_found": len(nearby_places),
            "places": nearby_places
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/local/categories")
async def get_popular_categories():
    """인기 검색 카테고리 목록"""
    categories = [
        {"name": "맛집", "keywords": ["맛집", "레스토랑", "식당"], "icon": "🍽️"},
        {"name": "카페", "keywords": ["카페", "커피", "디저트"], "icon": "☕"},
        {"name": "병원", "keywords": ["병원", "의원", "치과", "약국"], "icon": "🏥"},
        {"name": "편의점", "keywords": ["편의점", "마트", "슈퍼"], "icon": "🏪"},
        {"name": "주유소", "keywords": ["주유소", "기름", "연료"], "icon": "⛽"},
        {"name": "은행", "keywords": ["은행", "ATM", "금융"], "icon": "🏦"},
        {"name": "숙박", "keywords": ["호텔", "모텔", "펜션", "숙박"], "icon": "🏨"},
        {"name": "운동", "keywords": ["헬스장", "수영장", "체육관", "요가"], "icon": "💪"},
        {"name": "미용", "keywords": ["미용실", "네일", "마사지"], "icon": "💅"},
        {"name": "교육", "keywords": ["학원", "도서관", "학교"], "icon": "📚"}
    ]
    
    return {
        "success": True,
        "categories": categories
    }

@router.get("/cache/status")
async def get_cache_status(current_user: Optional[User] = Depends(get_current_user_soft)):
    """캐시 상태 조회"""
    now = datetime.now()
    active_entries = 0
    expired_entries = 0
    
    for cache_key, cache_entry in SEARCH_CACHE.items():
        if now - cache_entry["timestamp"] < CACHE_DURATION:
            active_entries += 1
        else:
            expired_entries += 1
    
    return {
        "success": True,
        "cache_stats": {
            "total_entries": len(SEARCH_CACHE),
            "active_entries": active_entries,
            "expired_entries": expired_entries,
            "cache_duration_minutes": CACHE_DURATION.total_seconds() / 60,
            "memory_usage_estimate": f"{len(SEARCH_CACHE) * 0.5:.1f}KB"  # Rough estimate
        }
    }

@router.delete("/cache/clear")
async def clear_cache(current_user: Optional[User] = Depends(get_current_user_soft)):
    """캐시 초기화"""
    old_size = len(SEARCH_CACHE)
    SEARCH_CACHE.clear()
    
    return {
        "success": True,
        "message": f"Cache cleared. {old_size} entries removed."
    }

@router.get("/local/batch")
async def batch_search_places(
    queries: str = Query(..., description="검색어들 (쉼표로 구분)"),
    max_per_query: int = Query(5, ge=1, le=20, description="쿼리당 최대 결과 수"),
    current_user: Optional[User] = Depends(get_current_user_soft),
):
    """여러 검색어로 한번에 검색"""
    try:
        query_list = [q.strip() for q in queries.split(',') if q.strip()]
        if len(query_list) > 10:
            raise HTTPException(400, "Too many queries (max 10)")
        
        results = {}
        
        for query in query_list:
            try:
                search_response = await naver_local_search(
                    q=query,
                    display=max_per_query,
                    start=1,
                    sort="random",
                    include_coords=True,
                    cache_enabled=True,
                    current_user=current_user
                )
                
                results[query] = {
                    "success": True,
                    "total": search_response.total,
                    "items": search_response.items[:max_per_query]
                }
                
            except Exception as e:
                results[query] = {
                    "success": False,
                    "error": str(e)
                }
            
            # Small delay to avoid rate limiting
            await asyncio.sleep(0.1)
        
        return {
            "success": True,
            "queries_processed": len(query_list),
            "results": results
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}
