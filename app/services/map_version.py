# app/services/map_version.py
import os, asyncio, httpx, logging
from typing import Optional

NAVER_ID  = os.getenv("NAVER_MAPS_CLIENT_ID")
NAVER_KEY = os.getenv("NAVER_MAPS_CLIENT_SECRET")
LASTVER_URL = "https://maps.apigw.ntruss.com/map-static/v2/lastversion"

_version: Optional[str] = None
_interval: int = 86400  # 기본 1일

async def fetch_version_once():
    global _version, _interval
    if not NAVER_ID or not NAVER_KEY:
        logging.warning("Naver Maps keys not set; skip version fetch")
        return
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(LASTVER_URL, headers={
            "X-NCP-APIGW-API-KEY-ID": NAVER_ID,
            "X-NCP-APIGW-API-KEY": NAVER_KEY,
        })
    if r.status_code == 200:
        data = r.json()
        _version  = str(data.get("version") or "").strip() or None
        _interval = int(data.get("interval") or _interval)
        logging.info(f"[MapVersion] version={_version} interval={_interval}s")
    else:
        logging.warning(f"[MapVersion] failed {r.status_code}: {r.text}")

async def start_version_refresher():
    # 최초 1회
    await fetch_version_once()
    # 주기 갱신
    while True:
        await asyncio.sleep(max(3600, _interval))  # 최소 1시간
        await fetch_version_once()

def get_version() -> Optional[str]:
    return _version
