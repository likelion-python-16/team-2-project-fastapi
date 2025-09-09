# app/nlp/model_loader.py
from __future__ import annotations
from functools import lru_cache
import numpy as np
from sentence_transformers import SentenceTransformer

# 멀티언어 짧은 쿼리/고유명사에 강한 베이스
MODEL_ID = "paraphrase-multilingual-MiniLM-L12-v2"

# 글로벌 변수로 모델 캐시
_model_cache = None

def get_model() -> SentenceTransformer:
    global _model_cache
    if _model_cache is None:
        # 메모리 효율성을 위해 device='cpu' 명시
        _model_cache = SentenceTransformer(MODEL_ID, device='cpu')
    return _model_cache

def embed_texts(texts: list[str]) -> np.ndarray:
    """
    입력: 텍스트 리스트
    출력: L2 정규화된 임베딩 (N, 384) float32
    """
    if not texts:
        return np.empty((0, 384), dtype="float32")
    model = get_model()
    vecs = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    # vecs는 이미 L2 정규화됨 → 코사인유사도 = 내적
    return vecs.astype("float32", copy=False)