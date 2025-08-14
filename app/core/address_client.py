import os, httpx

KAKAO_REST_KEY = os.getenv("KAKAO_REST_KEY")

def _score_address(addr: str) -> int:
    score = 0
    for k in ("시", "구", "동"):
        if k in addr:
            score += 1
    return score

async def autocomplete(query: str) -> list[dict]:
    if not KAKAO_REST_KEY:
        return []
    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_KEY}"}
    params = {"query": query, "size": 5}
    async with httpx.AsyncClient(timeout=5) as cli:
        r = await cli.get(url, headers=headers, params=params)
        r.raise_for_status()
        docs = r.json().get("documents", [])

    ranked = sorted(docs, key=lambda d: _score_address(d.get("address_name","")), reverse=True)
    results = []
    for d in ranked:
        full = d.get("address_name") or d.get("road_address_name") or ""
        results.append({"full": full})
    return results