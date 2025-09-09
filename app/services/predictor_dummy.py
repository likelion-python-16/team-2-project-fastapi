# 임시 더미 predictor - AI 없이 동작
from typing import Tuple

def predict_category(query: str) -> Tuple[str, float]:
    """
    AI 기능 비활성화 상태 - 항상 '기타' 반환
    """
    return "기타", 0.5