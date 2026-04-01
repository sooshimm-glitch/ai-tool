"""
문맥 인식 인용 탐지 엔진
기존 방식의 문제:
  if any(v in response.lower() for v in variants) → false positive 폭발

개선 방식:
1. Citation Pattern 분석 — "according to X", "X에 따르면", "X가 ~" 패턴
2. Entity Boundary 검사 — 단어 경계 기반 정확한 매칭
3. Context Window 검사 — 브랜드명 주변 문맥이 긍정적 인용인지 확인
4. Confidence Score — 탐지 신뢰도 0.0~1.0 반환
5. Negative Pattern 필터 — "X를 쓰지 마세요" 같은 부정 인용 제외
"""

import re
import math
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

from .logger import get_logger

logger = get_logger("citation")


@dataclass
class CitationMatch:
    brand_variant: str          # 매칭된 변형어
    pattern_type: str           # url / entity / citation / mention
    context_snippet: str        # 매칭 전후 50자
    confidence: float           # 0.0~1.0
    is_negative: bool = False   # "쓰지 마세요", "비추천" 등
    position: int = -1          # 응답 내 위치


@dataclass
class CitationResult:
    cited: bool
    confidence: float           # 최고 confidence
    matches: list[CitationMatch] = field(default_factory=list)
    response_sample: str = ""

    @property
    def is_positive_citation(self) -> bool:
        """부정적 언급 제외한 긍정 인용 여부"""
        return self.cited and not all(m.is_negative for m in self.matches)


# ─────────────────────────────────────────────
# 브랜드 변형 생성 (개선된 버전)
# ─────────────────────────────────────────────
_EN2KO = {
    "naver": "네이버", "kakao": "카카오", "coupang": "쿠팡",
    "toss": "토스", "baemin": "배민", "krafton": "크래프톤",
    "nexon": "넥슨", "ncsoft": "엔씨소프트", "netmarble": "넷마블",
    "samsung": "삼성", "lg": "엘지", "hyundai": "현대",
    "lotte": "롯데", "sk": "에스케이", "kt": "케이티",
    "line": "라인", "nhn": "엔에이치엔", "melon": "멜론",
    "woowa": "우아한형제들", "daum": "다음", "musinsa": "무신사",
    "kurly": "마켓컬리", "yogiyo": "요기요", "gmarket": "지마켓",
    "kakaopay": "카카오페이", "kakaotalk": "카카오톡",
}

_KO2EN = {v: k for k, v in _EN2KO.items()}


def build_brand_variants(target_url: str, biz_info: dict) -> list[str]:
    """
    탐지 변형 목록 — 정밀도 우선 (오탐 최소화).
    과거 버전과 달리 타이포 변형 제외, 최소 3자 이상만 포함.
    """
    try:
        p = urlparse(target_url if target_url.startswith("http") else "https://" + target_url)
        domain = p.netloc.replace("www.", "")
    except Exception:
        domain = target_url

    domain_stem = domain.split(".")[0].lower()
    brand_name  = (biz_info.get("brand_name") or "").strip()

    variants: set[str] = set()

    # 1. 도메인 기반
    variants.add(domain.lower())
    if len(domain_stem) >= 3:
        variants.add(domain_stem)

    # 2. 브랜드명 기반 (정확한 것만)
    if brand_name and len(brand_name) >= 2:
        variants.add(brand_name)
        variants.add(brand_name.lower())
        # 공백 제거 버전
        no_space = brand_name.replace(" ", "")
        if len(no_space) >= 2:
            variants.add(no_space.lower())

    # 3. EN↔KO 매핑
    stem_lower = domain_stem.lower()
    if stem_lower in _EN2KO:
        variants.add(_EN2KO[stem_lower])
    for ko, en in _KO2EN.items():
        if ko in brand_name:
            variants.add(en)
            variants.add(ko)
    for en, ko in _EN2KO.items():
        if en in brand_name.lower() or en == stem_lower:
            variants.add(ko)
            variants.add(en)

    # 4. 약칭 (2글자 이상 영문)
    if brand_name:
        words = brand_name.split()
        if len(words) >= 2:
            abbrev = "".join(w[0] for w in words if w).lower()
            if len(abbrev) >= 2:
                variants.add(abbrev)

    # 필터: 최소 2자, 순수 숫자 제외, 너무 일반적인 단어 제외
    _blacklist = {"the", "inc", "co", "com", "net", "org", "ltd", "corp",
                  "www", "http", "https", "서비스", "쇼핑", "앱"}
    return [
        v for v in variants
        if v and len(v) >= 2 and not v.isdigit() and v.lower() not in _blacklist
    ]


# ─────────────────────────────────────────────
# 인용 패턴 정의
# ─────────────────────────────────────────────
_CITATION_PATTERNS_KO = [
    # 강한 인용 (confidence boost)
    r"(?:에\s*따르면|에서\s*발표|에서\s*제공|이\s*발표한|가\s*공개한)",
    r"(?:공식\s*사이트|홈페이지|웹사이트)\s*[은는이가]",
    r"(?:서비스|플랫폼|솔루션)\s*[을를은는이가]",
    r"(?:에서\s*확인|통해\s*확인|에서\s*이용)",
    r"(?:추천|권장|사용|이용|선택)\s*(?:합니다|드립니다|할\s*수\s*있습니다)",
]

_CITATION_PATTERNS_EN = [
    r"(?:according\s+to|based\s+on|via|through|from|at)\s+\w",
    r"(?:website|platform|service|solution|tool|app)\s",
    r"(?:recommend|suggest|use|try|visit|check)",
    r"(?:official|verified|trusted|reliable)",
]

_NEGATIVE_PATTERNS_KO = [
    r"(?:하지\s*마세요|쓰지\s*마세요|피하세요|비추|불량|위험|사기|사기|문제)",
    r"(?:단점|불편|느림|비쌈|최악)",
    r"(?:보다\s*나쁜|보다\s*못한|대신\s*사용)",
]

_NEGATIVE_PATTERNS_EN = [
    r"(?:avoid|don't\s+use|not\s+recommended|scam|fraud|poor|worst|terrible)",
    r"(?:instead\s+of|rather\s+than|unlike)",
]

_ALL_CITATION = _CITATION_PATTERNS_KO + _CITATION_PATTERNS_EN
_ALL_NEGATIVE = _NEGATIVE_PATTERNS_KO + _NEGATIVE_PATTERNS_EN


def _check_context_window(text: str, pos: int, window: int = 80) -> tuple[str, bool, float]:
    """
    브랜드명 위치(pos) 주변 window 문자 내 문맥 분석.
    반환: (snippet, is_negative, confidence_boost)
    """
    start = max(0, pos - window)
    end   = min(len(text), pos + window)
    snippet = text[start:end]

    # 부정 패턴 체크
    for pat in _ALL_NEGATIVE:
        if re.search(pat, snippet, re.IGNORECASE):
            return snippet, True, 0.0

    # 인용 패턴 체크
    boost = 0.0
    for pat in _ALL_CITATION:
        if re.search(pat, snippet, re.IGNORECASE):
            boost += 0.2
            break  # 첫 매칭에서 충분

    return snippet, False, min(boost, 0.4)


def detect_citation(response: str, brand_variants: list[str],
                    threshold: float = 0.3) -> CitationResult:
    """
    문맥 인식 인용 탐지.

    탐지 우선순위:
    1. URL 패턴 매칭 (confidence: 0.9)
    2. 정확한 단어 경계 매칭 + 인용 문맥 (0.6~0.9)
    3. 단순 포함 + 문맥 검증 (0.3~0.6)

    threshold 미만이면 cited=False.
    """
    if not response or not brand_variants:
        return CitationResult(cited=False, confidence=0.0)

    response_lower = response.lower()
    best_confidence = 0.0
    all_matches: list[CitationMatch] = []

    for variant in brand_variants:
        if not variant or len(variant) < 2:
            continue

        v_lower = variant.lower()

        # ── 패턴 1: URL 매칭 (최고 신뢰도) ──
        url_pat = re.escape(v_lower)
        if re.search(rf'https?://[^\s]*{url_pat}|{url_pat}\.[a-z]{{2,6}}', response_lower):
            snippet, is_neg, boost = _check_context_window(
                response_lower,
                response_lower.find(v_lower)
            )
            conf = 0.0 if is_neg else min(0.9 + boost, 1.0)
            m = CitationMatch(
                brand_variant=variant,
                pattern_type="url",
                context_snippet=snippet,
                confidence=conf,
                is_negative=is_neg,
                position=response_lower.find(v_lower),
            )
            all_matches.append(m)
            best_confidence = max(best_confidence, conf)
            continue

        # ── 패턴 2: 단어 경계 매칭 ──
        # 한글: 공백/구두점 경계
        # 영문: \b 단어 경계
        is_korean = bool(re.search(r'[가-힣]', v_lower))

        if is_korean:
            # 한글은 어절 단위 — 앞뒤 공백/구두점/문장 부호
            boundary_pat = rf'(?<![가-힣a-z]){re.escape(v_lower)}(?![가-힣a-z0-9])'
        else:
            boundary_pat = rf'\b{re.escape(v_lower)}\b'

        for m_obj in re.finditer(boundary_pat, response_lower, re.IGNORECASE):
            pos = m_obj.start()
            snippet, is_neg, boost = _check_context_window(response_lower, pos)
            conf = 0.0 if is_neg else (0.55 + boost)
            m = CitationMatch(
                brand_variant=variant,
                pattern_type="entity",
                context_snippet=snippet,
                confidence=conf,
                is_negative=is_neg,
                position=pos,
            )
            all_matches.append(m)
            best_confidence = max(best_confidence, conf)
            break  # 첫 매칭만

        if best_confidence >= 0.6:
            continue  # 충분히 확신, 다음 변형 체크 불필요

        # ── 패턴 3: 단순 포함 (낮은 신뢰도, 문맥 검증 필수) ──
        if v_lower in response_lower:
            pos = response_lower.find(v_lower)
            snippet, is_neg, boost = _check_context_window(response_lower, pos)
            conf = 0.0 if is_neg else (0.25 + boost)
            m = CitationMatch(
                brand_variant=variant,
                pattern_type="mention",
                context_snippet=snippet,
                confidence=conf,
                is_negative=is_neg,
                position=pos,
            )
            all_matches.append(m)
            best_confidence = max(best_confidence, conf)

    cited = best_confidence >= threshold
    best_match = max(all_matches, key=lambda x: x.confidence) if all_matches else None

    return CitationResult(
        cited=cited,
        confidence=best_confidence,
        matches=all_matches,
        response_sample=(
            best_match.context_snippet if best_match and cited else ""
        ),
    )


# ─────────────────────────────────────────────
# 통계 유틸
# ─────────────────────────────────────────────
def wilson_ci(hits: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Wilson Score Interval — 소표본에서도 안정적."""
    if n == 0:
        return 0.0, 100.0
    z = 1.96 if confidence == 0.95 else 2.576
    p = hits / n
    denom  = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = (z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))) / denom
    return (
        round(max(0.0, (center - margin) * 100), 1),
        round(min(100.0, (center + margin) * 100), 1),
    )
