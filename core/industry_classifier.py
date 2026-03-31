"""
업종 분류 레이어 — 2단계 LLM 분류 + 검색 기반 확정

LLM 호출 최소화 전략:
  - 1단계(카테고리) + 2단계(세부) 를 단일 프롬프트로 병합 → LLM 1회
  - 검색 확정은 결과가 모호할 때만 조건부 실행
  - 모호 retry도 같은 흐름 안에서 처리 (별도 호출 X)

의존: schemas, text_processing, ai_client, crawler (search only)
"""

from __future__ import annotations

import re
import json
from typing import Any

from core.logger import get_logger, CaptureError
from core.cache import get_cache
from core.crawler import crawl_search
from core.ai_client import call_gpt, call_gemini
from core.schemas import (
    BusinessInfo, INDUSTRY_CATEGORIES, CATEGORY_TO_DETAIL, _BAD_INDUSTRIES
)

logger = get_logger("industry_classifier")

_BIZ_SYSTEM = (
    "당신은 비즈니스 인텔리전스 전문가입니다. "
    "모든 분석은 제공된 데이터에 근거하여 구체적으로 수행합니다."
)
_CATEGORY_LABELS = " | ".join(INDUSTRY_CATEGORIES)


# ── 캐시 키 버전 상수 ─────────────────────────────────────────────
# 프롬프트 구조가 바뀔 때 이 값을 올려 stale 캐시를 자동 무효화
_CLASSIFIER_VERSION = "v4"


def _make_cache_key(url: str, model_gpt: str, confirmed_industry: str) -> str:
    cache = get_cache()
    return cache.make_key(
        "biz", _CLASSIFIER_VERSION, url, model_gpt, confirmed_industry
    )


# ── 통합 프롬프트 (1+2단계 병합 → LLM 1회) ──────────────────────────
def _build_classify_prompt(
    domain: str,
    clean_text: str,
    search_ctx: str,
    category_hint: str,          # 사전 단서 (있으면 주입, 없으면 "")
) -> str:
    cat_hint_section = (
        f"\n[사전 분류 단서] {category_hint}\n"
        if category_hint else ""
    )
    detail_examples = ""
    if category_hint and category_hint in CATEGORY_TO_DETAIL:
        examples = ", ".join(CATEGORY_TO_DETAIL[category_hint][:4])
        detail_examples = f"\n[세부 업종 예시 참고] {examples}\n"

    return f"""아래 데이터를 분석하여 해당 웹사이트의 업종과 서비스를 정확히 파악하세요.

[도메인] {domain}
[본문 핵심]
{clean_text[:1800]}
[검색 보완 데이터]
{search_ctx[:800] if search_ctx else "(없음)"}
{cat_hint_section}{detail_examples}
[분류 대분류 선택지]
{_CATEGORY_LABELS}

[분석 지침]
- industry_category: 위 선택지 중 정확히 하나 선택
- industry: 구체적 세부 업종 (예시보다 더 구체적 표현 가능)
  ✅ "퍼포먼스 마케팅 광고대행사", "B2B SaaS HR솔루션"
  ❌ "IT 서비스", "온라인 서비스", "디지털 서비스"
- brand_name: 도메인이 아닌 실제 브랜드명 (한국 서비스면 한국어로, 예: "마이프로그레스", "네이버", "카카오"). 본문·타이틀·로고 텍스트에서 우선 추출. 찾을 수 없으면 도메인 줄기를 한국어 발음으로 변환
- confidence: 크롤+데이터 풍부=high, 보통=medium, 부족=low
- 광고·퍼포먼스·IMC·GFA·매체 키워드 → 광고대행사 계열 우선

JSON만 출력 (다른 텍스트 없이):
{{
  "brand_name": "한국어 실제 브랜드명 (예: 마이프로그레스, 네이버, 쿠팡)",
  "industry_category": "선택지 중 택1",
  "industry": "구체적 세부 업종",
  "core_product": "핵심 서비스/상품 한 문장",
  "target_audience": "주요 타겟 고객층",
  "key_services": ["서비스1", "서비스2", "서비스3"],
  "confidence": "high | medium | low 중 택1"
}}"""


def _call_llm(client_gpt, client_gemini, prompt: str, model_gpt: str,
              max_tokens: int = 400, temperature: float = 0.15) -> str:
    result = ""
    with CaptureError("classify_llm", log_level="warning"):
        if client_gpt:
            result = call_gpt(client_gpt, prompt, system=_BIZ_SYSTEM,
                              max_tokens=max_tokens, model=model_gpt,
                              temperature=temperature)
        elif client_gemini:
            result = call_gemini(client_gemini, prompt,
                                 max_tokens=max_tokens, temperature=temperature)
    return result or ""


def _parse_biz_json(raw: str) -> dict[str, Any]:
    with CaptureError("classify_json_parse", log_level="warning"):
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            return json.loads(m.group())
    return {}


def _is_vague(industry: str) -> bool:
    return not industry or any(bad in industry.lower() for bad in _BAD_INDUSTRIES)


# ── 검색 기반 확정 (조건부 실행) ────────────────────────────────────
def _search_confirm(
    client_gpt, client_gemini,
    domain: str,
    ai_industry: str,
    model_gpt: str,
) -> tuple[str, str]:
    """
    AI 추론 업종을 검색 결과로 교차검증.
    반환: (confirmed_industry, evidence)
    """
    stem = domain.split(".")[0]
    search_ctx = crawl_search(f"{stem} {ai_industry} 서비스 소개", use_cache=True)
    if not search_ctx or len(search_ctx) < 100:
        return ai_industry, ""

    prompt = f"""검색 결과를 바탕으로 "{domain}"의 업종을 최종 확정하세요.

[AI 초기 추론] {ai_industry}
[검색 근거]
{search_ctx[:1200]}

규칙:
- 검색 근거가 AI 추론과 일치 → 그대로 출력
- 검색 근거가 더 구체적/정확 → 검색 기반으로 수정
- 검색 근거가 전혀 다른 업종 → 검색 근거 우선
- "IT 서비스" 같은 모호한 표현 절대 사용 금지

JSON만 출력:
{{"industry": "확정 업종명", "evidence": "근거 한 문장"}}"""

    raw = _call_llm(client_gpt, client_gemini, prompt, model_gpt,
                    max_tokens=100, temperature=0.1)
    parsed = _parse_biz_json(raw)
    confirmed = str(parsed.get("industry", "")).strip()
    evidence  = str(parsed.get("evidence", "")).strip()

    if confirmed and not _is_vague(confirmed):
        return confirmed, evidence
    return ai_industry, ""


# ── 공개 API ─────────────────────────────────────────────────────────
def classify_industry(
    client_gpt,
    client_gemini,
    domain: str,
    clean_text: str,
    search_ctx: str,
    model_gpt: str,
    crawl_tier: int = 0,
    confirmed_industry: str = "",
    url: str = "",
    use_cache: bool = True,
) -> BusinessInfo:
    """
    업종 분류 전체 파이프라인 (LLM 최소 1회, 최대 2회).

    Flow:
        cache hit → 즉시 반환
        사용자 확정 업종 있음 → LLM 1회 (brand/product/target 만 추출)
        없음:
            LLM 1회 (카테고리+세부 통합)
            → 결과 모호 → 검색 확정 LLM 1회 (조건부)
    """
    cache_key = _make_cache_key(url or domain, model_gpt, confirmed_industry)

    if use_cache:
        cached = get_cache().get(cache_key)
        if cached:
            logger.info(f"Cache HIT: classify_industry({domain})")
            return BusinessInfo.from_dict(cached)

    stem = domain.split(".")[0]

    # ── 사용자 확정 업종이 있으면 brand/product만 추출, industry 주입 ──
    if confirmed_industry.strip():
        prompt = f"""도메인 "{domain}"의 브랜드 정보만 추출하세요.
업종은 이미 확정됨: {confirmed_industry}

[본문 핵심]
{clean_text[:800]}

JSON만 출력:
{{
  "brand_name": "실제 브랜드명",
  "core_product": "핵심 서비스 한 문장",
  "target_audience": "주요 타겟",
  "key_services": ["서비스1", "서비스2"]
}}"""
        raw  = _call_llm(client_gpt, client_gemini, prompt, model_gpt,
                         max_tokens=200, temperature=0.1)
        d    = _parse_biz_json(raw)
        biz  = BusinessInfo.from_dict({
            **d,
            "industry": confirmed_industry,
            "industry_category": "기타",   # __post_init__ 이 검증
            "confidence": "high",
            "crawl_tier": crawl_tier,
        })
        if use_cache:
            get_cache().set(cache_key, biz.to_dict(), namespace="biz")
        return biz

    # ── 통합 분류 프롬프트 (LLM 1회) ──
    prompt = _build_classify_prompt(domain, clean_text, search_ctx, "")
    raw    = _call_llm(client_gpt, client_gemini, prompt, model_gpt)
    d      = _parse_biz_json(raw)

    ai_industry  = str(d.get("industry", "")).strip()
    ai_category  = str(d.get("industry_category", "")).strip()

    # ── 결과 모호 → 검색 확정 (조건부 LLM 2회째) ──
    if _is_vague(ai_industry):
        confirmed, evidence = _search_confirm(
            client_gpt, client_gemini, domain, ai_industry or stem, model_gpt
        )
        if confirmed != ai_industry:
            logger.info(f"Industry confirmed by search: '{ai_industry}' → '{confirmed}'")
        d["industry"] = confirmed
        if evidence:
            logger.info(f"Search evidence: {evidence}")

    # 폴백
    if not d:
        d = BusinessInfo.fallback(stem, crawl_tier).to_dict()
    else:
        d.setdefault("industry", f"{stem} 관련 서비스")
        d.setdefault("industry_category", "기타")
        d["crawl_tier"] = crawl_tier

    biz = BusinessInfo.from_dict(d)

    if use_cache:
        get_cache().set(cache_key, biz.to_dict(), namespace="biz")

    return biz
