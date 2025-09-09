# 임시 더미 model_loader - AI 없이 동작
import numpy as np

def embed_texts(texts):
    """더미 임베딩 함수 - 랜덤 벡터 반환"""
    return np.random.rand(len(texts), 384)  # 384차원 더미 벡터