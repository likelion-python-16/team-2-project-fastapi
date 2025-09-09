# app/nlp/model_loader.py
from __future__ import annotations
import numpy as np
from sentence_transformers import SentenceTransformer

# 더 작은 메모리 사용량의 모델
MODEL_ID = "distiluse-base-multilingual-cased"

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
    출력: L2 정규화된 임베딩 (N, 512) float32
    """
    if not texts:
        return np.empty((0, 512), dtype="float32")
    model = get_model()
    vecs = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    return vecs.astype("float32", copy=False)