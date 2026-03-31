"""
비즈니스 분석 오케스트레이터 v3.1

이 파일은 순수 조율 레이어. 실제 로직은 하위 레이어에 위임:

  core/schemas.py              — 데이터 스키마 (BusinessInfo, Competitor)
  core/text_processing.py     — 크롤 텍스트 정제
  core/industry_classifier.py — 업종 분류 (LLM 1~2회)
  core/competitor_finder.py   — 경쟁사 도출 + 2단계 검증 (DNS/HEAD → Crawl)
  core/question_generator.py  — 질문 생성 (5개, 브랜드명 미포함)
  core/strategy_analyzer.py   — 전략 분석 (경쟁사·진단·키워드·GEO)

이 파일에서 직접 LLM 호출 / 인라인 프롬프트 / 캐시 키 생성 없음.
"""

from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

from core.logger import get_logger, CaptureError
from core.crawler import crawl, crawl_search
from core.text_processing import extract_business_text
from core.industry_classifier import classify_industry
from core.competitor_finder import discover_competitors
from core.schemas import BusinessInfo, Competitor

# ── 역할 분리된 모듈 re-export (app.py / pipeline.py import 경로 유지) ──
from core.question_generator import generate_target_questions
from core.strategy_analyzer import run_strategy_analysis

logger = get_logger("biz_analysis")

__all__ = [
    "BusinessInfo", "Competitor",
    "analyze_business", "discover_competitors",
    "generate_target_questions", "run_strategy_analysis",
]


# ─────────────────────────────────────────────
# 비즈니스 분석 (오케스트레이터)
# ─────────────────────────────────────────────
def analyze_business(
    client_gpt,
    client_gemini,
    url: str,
    model_gpt: str,
    confirmed_industry: str = "",
    use_cache: bool = True,
) -> BusinessInfo:
    """
    Pipeline:
        1. 3-tier 크롤링
        2. 텍스트 정제  (text_processing)
        3. 검색 보완 수집
        4. 업종 분류   (industry_classifier) ← LLM 최소 1회
    """
    try:
        p = urlparse(url if url.startswith("http") else "https://" + url)
        domain = p.netloc.replace("www.", "")
    except Exception:
        domain = url

    stem = domain.split(".")[0]

    # Step 1: 크롤링
    crawl_result = crawl(url, use_cache=use_cache)

    # Step 2: 텍스트 정제
    clean_text = extract_business_text(crawl_result.body_text)
    logger.info(
        f"extract_business_text: {len(crawl_result.body_text)}"
        f"→{len(clean_text)} chars (tier={crawl_result.tier_used})"
    )

    # Step 3: 검색 보완 (크롤 품질과 무관하게 항상 수집)
    search_ctx = ""
    with CaptureError("biz_search", log_level="info"):
        search_ctx = crawl_search(f"{stem} 서비스 업종 소개", use_cache=use_cache)
        if not search_ctx or len(search_ctx) < 200:
            search_ctx = crawl_search(
                f"{stem} company overview service", use_cache=use_cache
            )

    # Step 4: 업종 분류 위임
    return classify_industry(
        client_gpt=client_gpt,
        client_gemini=client_gemini,
        domain=domain,
        clean_text=clean_text,
        search_ctx=search_ctx,
        model_gpt=model_gpt,
        crawl_tier=crawl_result.tier_used,
        confirmed_industry=confirmed_industry,
        url=url,
        use_cache=use_cache,
    )
