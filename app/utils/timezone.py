# app/utils/timezone.py
"""
한국 시간대 유틸리티
전체 애플리케이션에서 일관된 시간대 사용을 위한 모듈
"""
from datetime import datetime
import pytz

# 한국 시간대 정의
KST = pytz.timezone('Asia/Seoul')

def now_kst() -> datetime:
    """한국 시간대 기준 현재 시간 반환"""
    return datetime.now(KST)

def utc_to_kst(utc_dt: datetime) -> datetime:
    """UTC 시간을 한국 시간으로 변환"""
    if utc_dt.tzinfo is None:
        # naive datetime인 경우 UTC로 간주
        utc_dt = pytz.utc.localize(utc_dt)
    return utc_dt.astimezone(KST)

def kst_to_utc(kst_dt: datetime) -> datetime:
    """한국 시간을 UTC로 변환"""
    if kst_dt.tzinfo is None:
        # naive datetime인 경우 KST로 간주
        kst_dt = KST.localize(kst_dt)
    return kst_dt.astimezone(pytz.utc)