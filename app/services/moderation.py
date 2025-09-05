"""
app/services/moderation.py

경량 신고 자동판정 로직:
- PII 마스킹 → 룰 체크 → 독성 점수(HF API or 로컬 휴리스틱)
- 간단 가중 합으로 auto_decision, auto_confidence 산출

네트워크가 막힌 환경에서도 동작하도록 HF API 토큰이 없는 경우
룰 기반/휴리스틱 점수를 사용해 대략적인 판정을 수행합니다.
"""
from __future__ import annotations

import hashlib
import os
import re
import time
from dataclasses import dataclass
from typing import Iterable

import json
import urllib.request


# ── 기본 설정 (환경변수) ─────────────────────────────────────────────────────
HF_API_TOKEN = os.getenv("HF_API_TOKEN", "").strip()
TOXICITY_MODEL_ID = os.getenv("TOXICITY_MODEL_ID", "unitary/unbiased-toxic-roberta").strip()

# threshold (0~1)
THRESH_HIGH = float(os.getenv("TOXICITY_THRESHOLD_HIGH", "0.85"))
THRESH_LOW = float(os.getenv("TOXICITY_THRESHOLD_LOW", "0.30"))


# ── 금칙어 룰(샘플) ───────────────────────────────────────────────────────────
# 실제 운영에서는 외부 파일/DB에서 로드하도록 교체 권장
BANNED_KEYWORDS: tuple[str, ...] = (
    # 한국어 욕설/비하 샘플(최소)
    "멍청", "미친", "바보", "죽어", "꺼져",
    # 영어 toxic 샘플
    "idiot", "stupid", "shut up", "kill you",
)


# ── 유틸: PII 마스킹 ─────────────────────────────────────────────────────────
EMAIL_RE = re.compile(r"([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+)\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d{1,3})?[\s.-]?(\d{2,3})[\s.-]?(\d{3,4})[\s.-]?(\d{4})")


def mask_pii(text: str) -> str:
    def mask_email(m: re.Match) -> str:
        local = m.group(1)
        domain = m.group(2)
        return f"{local[:2]}***@{domain[:1]}***"

    def mask_phone(m: re.Match) -> str:
        return f"{m.group(1)}-***-{m.group(3)}"

    t = EMAIL_RE.sub(mask_email, text)
    t = PHONE_RE.sub(mask_phone, t)
    return t


def rule_hit(text: str, keywords: Iterable[str] = BANNED_KEYWORDS) -> bool:
    t = text.lower()
    return any(k.lower() in t for k in keywords)


def _hf_infer_toxicity(text: str) -> float | None:
    """Hugging Face Inference API로 독성 점수(0~1)를 시도. 실패 시 None.
    모델에 따라 반환 포맷이 다를 수 있으므로 대표 케이스만 처리.
    """
    if not HF_API_TOKEN:
        return None
    url = f"https://api-inference.huggingface.co/models/{TOXICITY_MODEL_ID}"
    payload = {"inputs": text}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {HF_API_TOKEN}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None

    # 대표적인 텍스트 분류 결과 포맷: [[{"label": "toxic", "score": 0.93}, ...]]
    try:
        preds = body[0]
        if isinstance(preds, list):
            for item in preds:
                label = str(item.get("label", "")).lower()
                score = float(item.get("score", 0.0))
                if "toxic" in label or label in {"toxic", "toxicity"}:
                    return max(0.0, min(1.0, score))
            # 못 찾으면 최대 스코어를 보수적으로 사용
            if preds:
                max_s = max(float(p.get("score", 0.0)) for p in preds)
                return max(0.0, min(1.0, max_s))
    except Exception:
        pass
    return None


def _heuristic_toxicity(text: str) -> float:
    """HF API 불가 시 간단 휴리스틱(룰 기반 강화)으로 0~1 추정치 산출"""
    t = text.lower()
    hits = sum(t.count(k.lower()) for k in BANNED_KEYWORDS)
    length = max(10, len(t))
    ratio = min(1.0, hits * 3 / length)  # 거친 근사치
    return ratio


def comment_fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class AutoEvalResult:
    toxic_score: float      # 0~1
    rule_flag: bool
    reporter_trust: float  # 0~1
    multi_report_norm: float  # 0~1
    final_score: float      # 0~1
    auto_decision: str      # "true"|"false"|"review"


def run_auto_eval(
    text: str,
    reporter_trust: float = 0.5,
    multi_report_norm: float = 0.0,
) -> AutoEvalResult:
    masked = mask_pii(text)
    rule = rule_hit(masked)

    toxic = _hf_infer_toxicity(masked)
    if toxic is None:
        toxic = _heuristic_toxicity(masked)

    # 가중합
    final = 0.7 * toxic + 0.2 * (1.0 if rule else 0.0) + 0.05 * reporter_trust + 0.05 * multi_report_norm
    # clip
    final = max(0.0, min(1.0, final))
    if final >= 0.75:
        dec = "true"
    elif final <= 0.35:
        dec = "false"
    else:
        dec = "review"
    return AutoEvalResult(
        toxic_score=toxic,
        rule_flag=rule,
        reporter_trust=reporter_trust,
        multi_report_norm=multi_report_norm,
        final_score=final,
        auto_decision=dec,
    )

