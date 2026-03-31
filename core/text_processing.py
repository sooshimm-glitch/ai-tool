"""
텍스트 후처리 레이어 — 크롤 결과 정제

역할: CrawlResult.body_text → 업종 분류에 적합한 clean_text
biz_analysis / industry_classifier 양쪽에서 import.
LLM 호출 없음, 순수 텍스트 처리.
"""

from __future__ import annotations

import re

# ── 노이즈 패턴 (모듈 로드 시 1회만 컴파일) ─────────────────────────
_NOISE_RAW = [
    r'copyright\s*©?\s*\d{4}[^\n]*',
    r'all\s+rights\s+reserved[^\n]*',
    r'privacy\s+policy[^\n]*',
    r'terms\s+(of\s+)?(service|use)[^\n]*',
    r'쿠키\s*(정책|설정|동의)[^\n]*',
    r'개인정보\s*(처리방침|보호정책)[^\n]*',
    r'이용약관[^\n]*',
    r'사업자\s*등록번호[^\n]*',
    r'대표이사\s*:[^\n]*',
    r'로그인\s*회원가입[^\n]*',
    r'(홈|메뉴|닫기|열기|더보기)\s+(홈|메뉴|닫기|열기|더보기)[^\n]*',
    r'(skip\s+to|go\s+to)\s+(content|main|nav)[^\n]*',
    r'https?://\S+',
    r'[\w.+-]+@[\w.-]+\.\w{2,6}',
    r'\d{2,4}[-.\s]\d{3,4}[-.\s]\d{4}',  # 전화번호
]
_COMPILED_NOISE: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in _NOISE_RAW
]

# ── 시그널 키워드 (모듈 수준 상수 — 함수 내부 참조 버그 수정) ─────────
_SIGNAL_KEYWORDS: tuple[str, ...] = (
    "서비스", "솔루션", "플랫폼", "기능", "특징", "소개", "about",
    "product", "service", "feature", "solution", "overview",
    "우리는", "회사", "company", "brand", "we are", "we provide",
    "전문", "특화", "전략", "광고", "마케팅", "쇼핑", "배송",
)

_MIN_CHUNK_LEN = 10   # 이보다 짧은 조각은 버림
_PARA_SPLIT    = re.compile(r'\n{2,}|\r\n\r\n')


def _signal_score(chunk: str) -> int:
    """청크의 시그널 키워드 포함 개수 반환. 상수를 직접 참조."""
    lower = chunk.lower()
    return sum(1 for kw in _SIGNAL_KEYWORDS if kw in lower)


def extract_business_text(raw_text: str, max_chars: int = 2500) -> str:
    """
    크롤 본문에서 업종 판별에 유용한 핵심 텍스트만 추출.

    Steps:
        1. 노이즈 패턴 제거 (법적고지·메뉴·URL 등)
        2. 문단 분리 & 너무 짧은 조각 제거
        3. 시그널 키워드 밀도 높은 문단 앞으로 정렬
        4. max_chars 이내로 결합해 반환
    """
    if not raw_text:
        return ""

    # 1. 노이즈 제거
    cleaned = raw_text
    for pat in _COMPILED_NOISE:
        cleaned = pat.sub("", cleaned)

    # 2. 문단 분리 + 짧은 조각 버림
    chunks = [
        c.strip()
        for c in _PARA_SPLIT.split(cleaned)
        if len(c.strip()) >= _MIN_CHUNK_LEN
    ]
    if not chunks:
        return ""

    # 3. 시그널 점수 내림차순 → 같은 점수면 원래 순서 유지
    scored = sorted(
        enumerate(chunks),
        key=lambda x: (-_signal_score(x[1]), x[0]),
    )

    # 4. max_chars 이내로 결합
    parts: list[str] = []
    total = 0
    for _, chunk in scored:
        need = len(chunk) + (1 if parts else 0)  # 구분자 \n 1자
        if total + need > max_chars:
            remaining = max_chars - total - 1
            if remaining > 30:
                parts.append(chunk[:remaining])
            break
        parts.append(chunk)
        total += need

    return "\n".join(parts)
