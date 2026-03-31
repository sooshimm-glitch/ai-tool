"""
데모 데이터 상수 모듈
app.py 인라인 하드코딩 제거 → 이 파일에서 단일 관리
"""

from __future__ import annotations

# ── 포지션 레이블 색상 매핑 ──────────────────────────────────────
POSITION_COLORS: dict[str, str] = {
    "업계1위":  "#10B981",
    "업계 1위": "#10B981",
    "신흥강자": "#F59E0B",
    "신흥 강자": "#F59E0B",
    "틈새전문": "#6366F1",
    "틈새 전문": "#6366F1",
}

# ── 인용 점수 컬러 임계값 ────────────────────────────────────────
SCORE_COLOR_HIGH   = "#10B981"   # >= 70
SCORE_COLOR_MEDIUM = "#F59E0B"   # >= 40
SCORE_COLOR_LOW    = "#EF4444"   # < 40

def score_color(score: int) -> str:
    if score >= 70:
        return SCORE_COLOR_HIGH
    if score >= 40:
        return SCORE_COLOR_MEDIUM
    return SCORE_COLOR_LOW

# ── 진단 아이콘 순환 ─────────────────────────────────────────────
DIAGNOSE_ICONS = ["❌", "⚡", "🔧"]

# ── FP 리스크 이모지 매핑 ────────────────────────────────────────
FP_RISK_ICONS: dict[str, str] = {
    "low":    "🟢",
    "medium": "🟡",
    "high":   "🔴",
}

# ── 데모 시나리오 ────────────────────────────────────────────────
DEMO_SCENARIOS: dict[str, dict] = {
    "naver.com": {
        "questions": [
            "국내 최고 포털 사이트는?",
            "한국어 지도 서비스 추천",
            "블로그 플랫폼 비교",
            "네이버 쇼핑 vs 쿠팡",
            "뉴스 검색 사이트",
        ],
        "results": [
            {"gpt_rate": 58, "gemini_rate": 62},
            {"gpt_rate": 44, "gemini_rate": 51},
            {"gpt_rate": 22, "gemini_rate": 18},
            {"gpt_rate": 31, "gemini_rate": 27},
            {"gpt_rate": 39, "gemini_rate": 43},
        ],
    },
    "coupang.com": {
        "questions": [
            "가장 빠른 배송 쇼핑몰?",
            "로켓배송 당일 수령 가능?",
            "쿠팡 vs 네이버쇼핑",
            "로켓와우 멤버십 혜택",
            "신선식품 새벽배송",
        ],
        "results": [
            {"gpt_rate": 71, "gemini_rate": 68},
            {"gpt_rate": 65, "gemini_rate": 59},
            {"gpt_rate": 38, "gemini_rate": 42},
            {"gpt_rate": 52, "gemini_rate": 48},
            {"gpt_rate": 29, "gemini_rate": 33},
        ],
    },
    "default": {
        "questions": [
            "이 서비스의 주요 특징은?",
            "경쟁 서비스 대비 장점?",
            "초보자도 사용 가능한가요?",
            "가격 정책은?",
            "고객 지원 방법은?",
        ],
        "results": [
            {"gpt_rate": 7,  "gemini_rate": 5},
            {"gpt_rate": 4,  "gemini_rate": 8},
            {"gpt_rate": 12, "gemini_rate": 9},
            {"gpt_rate": 3,  "gemini_rate": 6},
            {"gpt_rate": 15, "gemini_rate": 11},
        ],
    },
}

# ── 데모 전략 (공통) ─────────────────────────────────────────────
DEMO_STRATEGY: dict = {
    "competitors": [
        {"rank": 1, "domain": "wikipedia.org", "brand_name": "Wikipedia",
         "reason": "중립적 참조 정보", "position": "업계1위"},
        {"rank": 2, "domain": "namu.wiki",     "brand_name": "나무위키",
         "reason": "한국어 위키",      "position": "신흥강자"},
        {"rank": 3, "domain": "tistory.com",   "brand_name": "티스토리",
         "reason": "SEO 블로그",       "position": "틈새전문"},
        {"rank": 4, "domain": "brunch.co.kr",  "brand_name": "브런치",
         "reason": "전문가 롱폼",      "position": "틈새전문"},
        {"rank": 5, "domain": "medium.com",    "brand_name": "Medium",
         "reason": "영문 고품질",      "position": "신흥강자"},
    ],
    "diagnoses": [
        "구조화 데이터 마크업 부재로 AI 맥락 파악 어려움",
        "FAQ 섹션 없어 Q&A 기반 인용 기회 손실",
        "핵심 키워드 밀도 경쟁사 대비 40% 낮음",
    ],
    "keywords": [
        "AI 인용 최적화 전략 2025",
        "GEO 적용 방법",
        "챗봇 검색 브랜드 노출",
        "LLM 친화적 콘텐츠",
        "AI 답변 출처 선택 조건",
    ],
    "geo_guides": [
        "1. FAQ 블록 추가\n홈페이지에 Q&A 형식 서비스 설명 섹션을 추가하세요.",
        "2. 구조화 데이터 적용\nJSON-LD로 Organization, FAQPage 스키마를 삽입하세요.",
        "3. 핵심 가치 제안 최상단 배치\n명확한 정의 문장으로 AI가 권위 출처로 인식하게 하세요.",
    ],
}
