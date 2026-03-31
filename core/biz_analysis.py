"""
비즈니스 분석 오케스트레이터 v3.0

이 파일은 순수 조율 레이어. 실제 로직은 하위 레이어에 위임:

  core/schemas.py             — 데이터 스키마 (BusinessInfo, Competitor)
  core/text_processing.py    — 크롤 텍스트 정제
  core/industry_classifier.py — 업종 분류 (LLM 1~2회)
  core/competitor_finder.py   — 경쟁사 도출 + 2단계 검증 (DNS/HEAD → Crawl)

이 파일에서 직접 LLM 호출 / 캐시 키 생성 없음.
"""

from __future__ import annotations

import re
import json
import concurrent.futures
from typing import Optional
from urllib.parse import urlparse

from core.logger import get_logger, CaptureError
from core.cache import get_cache
from core.crawler import crawl, crawl_search
from core.ai_client import call_gpt, call_gemini
from core.text_processing import extract_business_text
from core.industry_classifier import classify_industry
from core.competitor_finder import discover_competitors
from core.schemas import BusinessInfo, Competitor

logger = get_logger("biz_analysis")

# 공개 re-export (기존 import 경로 호환)
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


# ─────────────────────────────────────────────
# 타겟 질문 생성
# ─────────────────────────────────────────────
_QUESTION_SYSTEM = (
    "당신은 GEO(Generative Engine Optimization) 전문가이자 디지털 마케팅 전략가입니다. "
    "완성된 질문만 출력합니다."
)

_CATEGORY_HINTS = {
    "광고/마케팅": (
        "광고주(중소기업 대표, 마케터)가 대행사를 선택할 때 묻는 질문 — "
        "ROAS, CPA, 매체비, 대행수수료, 업종 레퍼런스 위주"
    ),
    "이커머스": "구매자의 배송·가격·신뢰도, 판매자의 입점·수수료 관련 질문",
    "SaaS": "도입 전 데모·연동·보안·가격 플랜, 기존 솔루션 전환 비용 관련 질문",
    "금융": "금리·한도·수수료·안전성, 타 금융사 대비 혜택 관련 질문",
    "교육": "커리큘럼·강사·합격률·환불정책, 취업 연계 관련 질문",
    "의료": "진료 과목·비용·예약, 전문성 관련 질문",
    "게임": "게임성·과금정책·PC/모바일 지원, 경쟁 타이틀 대비 질문",
}

_QUESTION_VERSION = "v4"


def generate_target_questions(
    client_gpt,
    client_gemini,
    url: str,
    engine: str,
    model_gpt: str,
    biz_info: Optional[BusinessInfo] = None,
    use_cache: bool = True,
) -> list[str]:
    """비즈니스 정보 기반 고품질 타겟 질문 5개 생성."""
    try:
        p = urlparse(url if url.startswith("http") else "https://" + url)
        domain = p.netloc.replace("www.", "")
    except Exception:
        domain = url

    if biz_info is None:
        biz_info = BusinessInfo(
            brand_name=domain.split(".")[0].upper(),
            industry="서비스",
            industry_category="기타",
            core_product="서비스",
            target_audience="잠재 고객",
        )

    cache = get_cache()
    cache_key = cache.make_key(
        "questions", _QUESTION_VERSION, url, biz_info.industry, engine, model_gpt
    )
    if use_cache:
        cached = cache.get(cache_key)
        if cached:
            logger.info(f"Cache HIT: questions({domain})")
            return cached

    category_hint = _CATEGORY_HINTS.get(
        biz_info.industry_category,
        f"{biz_info.industry} 분야에서 {biz_info.target_audience}가 실제로 고민하는 핵심 질문",
    )
    services_str = (
        ", ".join(biz_info.key_services) if biz_info.key_services else biz_info.core_product
    )

    prompt = f"""당신은 {biz_info.industry} 분야 10년 경력 마케팅 전략가이자 GEO 전문가입니다.

[분석 대상 서비스 정보 — 내부 참고용, 질문에 직접 노출 금지]
- 업종: {biz_info.industry} ({biz_info.industry_category})
- 핵심 서비스: {services_str}
- 주요 타겟: {biz_info.target_audience}

[질문 방향]
{category_hint}

[핵심 규칙 — 반드시 준수]
1. 실제 사용자가 네이버, 구글, ChatGPT 검색창에 입력하는 방식의 자연스러운 질문
2. 브랜드명, 회사명, 도메인 주소를 질문에 절대 포함하지 말 것
3. "{biz_info.industry}" 카테고리 전체를 대상으로 하는 질문 (특정 브랜드 X)
4. 구매 결정 5단계(인지, 비교, 신뢰, 가격, 전환) 각각 다룰 것
5. {biz_info.industry} 업계 전문 용어와 지표 적극 활용
6. 기초 탐색형 질문 금지 ("무엇인가요?", "소개해주세요" 등)

[좋은 예시]
- "{biz_info.industry} 업체 선택할 때 꼭 확인해야 할 계약 조건은?"
- "{biz_info.target_audience}가 실제로 효과 본 {biz_info.industry} 서비스 어떻게 찾나요?"
- "{biz_info.industry} 비용 대비 성과 잘 내는 곳 비교하는 방법은?"

[나쁜 예시 — 절대 금지]
- 브랜드명이나 회사명이 들어간 질문 일체

번호 없이 질문 5개만 출력. 한 줄에 하나. 물음표(?)로 종결."""

    result_str = ""
    with CaptureError("question_gen", log_level="warning") as ctx:
        if engine == "GPT" and client_gpt:
            result_str = call_gpt(client_gpt, prompt, system=_QUESTION_SYSTEM,
                                  max_tokens=600, model=model_gpt, temperature=0.85)
        elif client_gemini:
            result_str = call_gemini(client_gemini, prompt, max_tokens=600, temperature=0.85)
        elif client_gpt:
            result_str = call_gpt(client_gpt, prompt, system=_QUESTION_SYSTEM,
                                  max_tokens=600, model=model_gpt, temperature=0.85)

    if not result_str and not ctx.ok:
        raise RuntimeError(f"질문 생성 실패: {ctx.error}")

    questions = _parse_questions(result_str)
    if len(questions) < 3:
        questions = _fallback_questions(biz_info)

    result = questions[:5]
    if use_cache:
        cache.set(cache_key, result, namespace="biz")
    return result


def _parse_questions(raw: str) -> list[str]:
    out: list[str] = []
    for ln in raw.split("\n"):
        ln = ln.strip()
        if not ln:
            continue
        clean = re.sub(r'^[\d]+[.)]\s*', '', ln)
        clean = re.sub(r'^[-•*]\s*', '', clean)
        clean = re.sub(r'^\[.*?\]\s*', '', clean)
        clean = re.sub(r'^\*\*.*?\*\*\s*', '', clean).strip()
        if len(clean) > 10:
            if not clean.endswith("?"):
                clean += "?"
            out.append(clean)
    return out


def _fallback_questions(biz: BusinessInfo) -> list[str]:
    is_ad = "광고" in biz.industry or "마케팅" in biz.industry
    if is_ad:
        return [
            f"{biz.industry} 대행사 선택할 때 업종별 ROAS 기준으로 비교하는 방법은?",
            f"광고대행사 계약 전 반드시 확인해야 할 조건과 주의사항은?",
            f"{biz.industry} 집행 매체별 효율 차이와 예산 배분 기준은?",
            f"직접 광고 운영 vs 대행사 위탁 — 비용 구조와 성과 차이 비교",
            f"{biz.industry} 실제 집행 성과 사례와 평균 CPA 수준은 어느 정도인가요?",
        ]
    return [
        f"{biz.industry} 서비스 선택할 때 경쟁사 대비 꼭 확인해야 할 차이점은?",
        f"{biz.target_audience}가 {biz.industry} 도입 후 실제로 얻은 성과 사례는?",
        f"{biz.industry} 계약 및 이용 조건, 비용 구조가 업계 평균과 비교해 어떤가요?",
        f"{biz.industry} 실제 사용자 평가에서 자주 언급되는 불만 사항은?",
        f"{biz.industry} 서비스를 비교할 때 가장 중요한 선택 기준은 무엇인가요?",
    ]


# ─────────────────────────────────────────────
# 전략 분석
# ─────────────────────────────────────────────
_STRATEGY_VERSION = "v4"


def run_strategy_analysis(
    client_gpt,
    client_gemini,
    question: str,
    target_url: str,
    model_gpt: str,
    biz_info: Optional[BusinessInfo] = None,
    market_scope: str = "글로벌",
    use_cache: bool = True,
) -> dict:
    try:
        p = urlparse(target_url if target_url.startswith("http") else "https://" + target_url)
        domain = p.netloc.replace("www.", "")
    except Exception:
        domain = target_url

    cache = get_cache()
    cache_key = cache.make_key(
        "strategy", _STRATEGY_VERSION,
        target_url, question[:50], market_scope, model_gpt,
    )
    if use_cache:
        cached = cache.get(cache_key)
        if cached:
            logger.info(f"Cache HIT: strategy({question[:30]}...)")
            return cached

    biz = biz_info or BusinessInfo(
        brand_name=domain, industry="서비스", industry_category="기타",
        core_product="서비스", target_audience="고객",
    )
    scope_inst = (
        "반드시 대한민국에서 서비스하는 국내 기업만 포함하세요."
        if "국내" in market_scope
        else "국내외 글로벌 기업을 모두 포함하세요."
    )
    _system = (
        "당신은 디지털 마케팅 전략 컨설턴트입니다. "
        "모든 답변은 완성된 문장으로, 중간에 끊기지 않게 서술하세요."
    )

    # 경쟁사·진단·키워드·GEO 4개 완전 병렬
    def _competitors() -> list:
        prompt = f"""질문: "{question}"
이 질문에 답변할 때 AI가 자주 인용할 상위 10개 브랜드를 인용 가능성 순으로 나열하세요.
- 분석 대상: {biz.brand_name} (업종: {biz.industry})
- {scope_inst}
- {domain}도 적절한 순위에 포함
- 반드시 실제 존재하는 브랜드와 도메인만 사용. c1.com, competitor.com 같은 가상 도메인 절대 금지.
JSON 배열만 출력 (다른 텍스트 없이):
[{{"rank":1,"domain":"실제도메인.com","brand_name":"실제브랜드명","reason":"이유 20자 이내","position":"업계1위|신흥강자|틈새전문 중 택1"}}]"""
        raw = ""
        with CaptureError("strategy_comp", log_level="warning"):
            raw = (call_gpt(client_gpt, prompt, system=_system, max_tokens=1200,
                            model=model_gpt, temperature=0.3)
                   if client_gpt else
                   call_gemini(client_gemini, prompt, max_tokens=1200, temperature=0.3))
        with CaptureError("strategy_comp_parse", log_level="warning"):
            m = re.search(r'\[.*\]', raw, re.DOTALL)
            if m:
                parsed = json.loads(m.group())
                real = [
                    c for c in parsed
                    if c.get("domain") and
                    not re.match(r'^(c\d+|competitor\d*|example|test|dummy)\.', str(c.get("domain", "")))
                ]
                if real:
                    return real
        return []

    def _diagnosis() -> list[str]:
        prompt = (
            f'{domain} ({biz.brand_name}, {biz.industry})이 "{question}"에서 '
            f'AI 인용 점유율이 낮은 원인 3가지.\n'
            f'경쟁사 대비 구체적 문제점. 각 항목 50자 이내. 반드시 한국어로. 번호 없이 한 줄씩:'
        )
        with CaptureError("strategy_diag", log_level="warning"):
            r = (call_gpt(client_gpt, prompt, system=_system, max_tokens=600,
                          model=model_gpt, temperature=0.4)
                 if client_gpt else
                 call_gemini(client_gemini, prompt, max_tokens=600, temperature=0.4))
            return [d.strip().lstrip("•-*") for d in r.split("\n") if d.strip()][:3]
        return ["데이터 부족으로 분석 불가"]

    def _keywords() -> list[str]:
        prompt = (
            f'{biz.industry} 분야에서 AI 인용 확률 높은 블루오션 키워드 5개를 한국어로 추천해주세요.\n'
            f'조건: 경쟁이 적고 전문성 높은 틈새 키워드. {scope_inst}\n'
            f'반드시 한국어 키워드만. 영어 금지. 키워드만 한 줄에 하나씩 출력:'
        )
        with CaptureError("strategy_kw", log_level="warning"):
            r = (call_gemini(client_gemini, prompt, max_tokens=600, temperature=0.7)
                 if client_gemini else
                 call_gpt(client_gpt, prompt, system=_system, max_tokens=600,
                          model=model_gpt, temperature=0.7))
            return [k.strip().lstrip("•-*1234567890. ") for k in r.split("\n") if k.strip() and len(k.strip()) > 2][:5]
        return ["분석 중 오류"]

    def _geo() -> list[str]:
        prompt = (
            f'{domain} ({biz.brand_name})이 "{question}"에서 AI에 더 잘 인용되도록 '
            f'홈페이지 개선 방안 3가지.\n'
            f'구체적 문구 수정 또는 구조 변경 제안 포함. 각 항목 2줄 이내. 번호 포함:'
        )
        with CaptureError("strategy_geo", log_level="warning"):
            r = (call_gpt(client_gpt, prompt, system=_system, max_tokens=1000,
                          model=model_gpt, temperature=0.5)
                 if client_gpt else
                 call_gemini(client_gemini, prompt, max_tokens=1000, temperature=0.5))
            return [g.strip() for g in re.split(r'\n(?=\d+\.)', r) if g.strip()][:3]
        return ["분석 중 오류"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        f_comp = ex.submit(_competitors)
        f_diag = ex.submit(_diagnosis)
        f_kw   = ex.submit(_keywords)
        f_geo  = ex.submit(_geo)

        competitors = f_comp.result(timeout=60) or []
        diagnoses   = f_diag.result(timeout=60) or ["데이터 부족으로 분석 불가"]
        keywords    = f_kw.result(timeout=60)   or ["분석 중 오류"]
        geo_guides  = f_geo.result(timeout=60)  or ["분석 중 오류"]

    result = {
        "competitors": competitors,
        "diagnoses":   diagnoses,
        "keywords":    keywords,
        "geo_guides":  geo_guides,
    }

    if use_cache:
        cache.set(cache_key, result, namespace="strategy")

    return result
