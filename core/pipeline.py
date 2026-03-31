"""
pipeline.py — Crawler → Biz → Question 통합 오케스트레이터

핵심 문제:
  App이 crawl() 결과를 버리고 analyze_business()가 내부에서 다시 crawl()을 호출함.
  analyze_business() 결과를 generate_questions()가 crawl 컨텍스트 없이 받음.
  경쟁사 분석이 시뮬레이션 끝난 뒤에 직렬로 실행됨.

해결:
  AnalysisPipeline 단일 진입점으로 통합.
  crawl_result를 pipeline 전체에서 공유.
  경쟁사 분석을 crawl과 병렬로 선제 실행.
  Citation 정확도 검증 레이어 (spot-check).
  Content filter로 AI 생성 질문 품질 게이트.
  Debug 모드: 각 단계 입출력 전부 노출.
"""

from __future__ import annotations

import re
import json
import time
import concurrent.futures as cf
from dataclasses import dataclass, field
from typing import Optional

from .logger import get_logger, CaptureError
from .cache import get_cache
from .crawler import crawl, crawl_search, CrawlResult
from .citation import (
    build_brand_variants, detect_citation, CitationResult, wilson_ci
)
from .ai_client import call_gpt, call_gemini, CostTracker
from .biz_analysis import (
    BusinessInfo, Competitor,
    discover_competitors,
)
from .question_generator import _CATEGORY_HINTS, _QUESTION_SYSTEM
from .industry_classifier import _BIZ_SYSTEM, _build_classify_prompt
from .prompts import BIZ_INDUSTRY_RETRY_TMPL, QUESTION_GEN_AUTO_TMPL
from .schemas import _BAD_INDUSTRIES

# 호환성 래퍼 — pipeline.py가 기대하는 시그니처로 변환
def _build_biz_prompt(domain: str, crawl_result, search_ctx: str) -> str:
    clean_text = crawl_result.body_text if crawl_result else ""
    return _build_classify_prompt(domain, clean_text, search_ctx, "")

logger = get_logger("pipeline")


# ─────────────────────────────────────────────
# 파이프라인 상태 — 전 단계 결과를 단일 객체로 전달
# ─────────────────────────────────────────────
@dataclass
class PipelineState:
    url:            str
    domain:         str
    crawl_result:   Optional[CrawlResult]       = None
    search_ctx:     str                          = ""
    biz_info:       Optional[BusinessInfo]       = None
    competitors:    list[Competitor]             = field(default_factory=list)
    questions:      list[str]                    = field(default_factory=list)
    # citation spot-check 결과
    spot_check:     dict                         = field(default_factory=dict)
    debug_log:      list[dict]                   = field(default_factory=list)
    errors:         list[str]                    = field(default_factory=list)
    timing:         dict[str, float]             = field(default_factory=dict)

    def log(self, stage: str, data: dict):
        self.debug_log.append({"stage": stage, "ts": time.time(), **data})

    def record_time(self, stage: str, elapsed: float):
        self.timing[stage] = round(elapsed, 2)


# ─────────────────────────────────────────────
# Content Filter — 질문 품질 게이트
# ─────────────────────────────────────────────
_WEAK_PATTERNS = [
    r"(?:는|이|가|을|를)\s*무엇인가요",
    r"소개해\s*주세요",
    r"설명해\s*주세요",
    r"어디\s*(?:있|위치)",
    r"역사.*어떻게",
    r"what\s+is\b",
    r"tell\s+me\s+about",
    r"introduce\b",
]

_STRONG_PATTERNS = [
    r"\d+\s*%",              # 수치 포함
    r"(?:비교|대비|vs\.?|versus)",
    r"(?:ROAS|CPA|CTR|ROI|CPM|CPV)",
    r"(?:비용|수수료|가격|요금|단가)",
    r"(?:사례|레퍼런스|후기|리뷰)",
    r"(?:경쟁사|대안|차이점|장단점)",
    r"(?:how\s+much|compare|versus|case\s+study|pricing)",
]


def content_filter(question: str, brand_name: str) -> dict:
    """
    질문 품질 평가.
    반환: {score: 0-100, pass: bool, reason: str, flags: list}
    """
    score = 50
    flags = []

    # 약한 패턴 감점
    for pat in _WEAK_PATTERNS:
        if re.search(pat, question, re.IGNORECASE):
            score -= 20
            flags.append(f"weak_pattern: {pat}")
            break

    # 강한 패턴 가점
    for pat in _STRONG_PATTERNS:
        if re.search(pat, question, re.IGNORECASE):
            score += 15
            flags.append(f"strong_pattern: {pat}")

    # 브랜드명 포함 여부
    if brand_name and brand_name.lower() in question.lower():
        score += 10
        flags.append("brand_included")
    else:
        score -= 10
        flags.append("brand_missing")

    # 길이 체크 (너무 짧은 질문)
    if len(question) < 20:
        score -= 20
        flags.append("too_short")
    elif len(question) > 150:
        score -= 5
        flags.append("too_long")

    # 물음표 있어야 함
    if not question.strip().endswith("?"):
        score -= 10
        flags.append("no_question_mark")

    score = max(0, min(100, score))
    passed = score >= 40

    reason = "pass" if passed else f"low_score({score}): " + ", ".join(flags[:2])
    return {"score": score, "pass": passed, "reason": reason, "flags": flags}


# ─────────────────────────────────────────────
# Citation Spot-Check — 시뮬레이션 전 정확도 검증
# ─────────────────────────────────────────────
def citation_spot_check(
    client_gpt, client_gemini,
    brand_variants: list[str],
    question: str,
    model_gpt: str,
    n_samples: int = 5,
    tracker: Optional[CostTracker] = None,
) -> dict:
    """
    실제 시뮬레이션 전 소규모 spot-check.
    목적:
    1. 브랜드 변형이 false positive를 유발하는지 확인
    2. AI 응답 패턴 사전 파악
    3. 변형 목록 정제 (오탐 유발 변형 제거)

    반환:
    {
      hit_rate: float,          # 초기 추정 점유율
      false_positive_risk: str, # low/medium/high
      suspect_variants: list,   # 오탐 의심 변형
      sample_responses: list,   # 실제 응답 샘플
      refined_variants: list,   # 정제된 변형 목록
    }
    """
    prompt = f"질문: {question}\n\n답변:"
    samples = []
    hits = 0
    false_pos_signals = []

    for i in range(n_samples):
        resp = ""
        with CaptureError(f"spot_gpt_{i}", log_level="debug"):
            if client_gpt:
                resp = call_gpt(client_gpt, prompt, max_tokens=200,
                                model=model_gpt, temperature=0.6, tracker=tracker)
            elif client_gemini:
                resp = call_gemini(client_gemini, prompt, max_tokens=200,
                                   temperature=0.6, tracker=tracker)

        if not resp:
            continue

        result: CitationResult = detect_citation(resp, brand_variants)
        samples.append({
            "response": resp[:300],
            "cited": result.cited,
            "confidence": result.confidence,
            "pattern_type": result.matches[0].pattern_type if result.matches else None,
            "is_negative": result.matches[0].is_negative if result.matches else False,
        })
        if result.cited:
            hits += 1

    hit_rate = hits / max(len(samples), 1) * 100

    # False positive 리스크 평가
    # 낮은 confidence(0.3~0.4)로 hit된 비율
    low_conf_hits = sum(
        1 for s in samples
        if s["cited"] and s.get("confidence", 0) < 0.45
    )
    fp_ratio = low_conf_hits / max(hits, 1) if hits > 0 else 0

    if fp_ratio > 0.5:
        fp_risk = "high"
    elif fp_ratio > 0.2:
        fp_risk = "medium"
    else:
        fp_risk = "low"

    # 오탐 의심 변형 식별: 짧고 일반적인 단어
    suspect = [v for v in brand_variants if len(v) <= 3 or
               v.lower() in {"app", "net", "web", "the", "inc", "co"}]

    # 정제된 변형: suspect 제거
    refined = [v for v in brand_variants if v not in suspect]
    if not refined:
        refined = brand_variants  # 너무 공격적으로 제거하면 안 됨

    return {
        "hit_rate": round(hit_rate, 1),
        "false_positive_risk": fp_risk,
        "suspect_variants": suspect,
        "sample_responses": samples,
        "refined_variants": refined,
        "n_samples": len(samples),
    }


# ─────────────────────────────────────────────
# 핵심: Biz 분석 with CrawlResult 직접 수신
# ─────────────────────────────────────────────
def analyze_business_from_crawl(
    client_gpt, client_gemini,
    state: PipelineState,
    model_gpt: str,
    confirmed_industry: str = "",
) -> BusinessInfo:
    """
    CrawlResult를 직접 받아서 중복 크롤링 없이 AI 분석 수행.
    기존 analyze_business()는 내부에서 crawl()을 또 호출하는 문제가 있었음.
    이 함수는 state.crawl_result를 그대로 사용.
    """
    import re, json
    from urllib.parse import urlparse

    crawl_result = state.crawl_result
    domain       = state.domain
    search_ctx   = state.search_ctx
    stem         = domain.split(".")[0]

    t0 = time.time()

    # ── 크롤 데이터 충분성 평가 ──
    body_len = len(crawl_result.body_text) if crawl_result else 0
    data_quality = "rich" if body_len > 1000 else ("sparse" if body_len > 200 else "empty")

    state.log("biz_input", {
        "domain": domain,
        "crawl_tier": crawl_result.tier_used if crawl_result else 0,
        "body_len": body_len,
        "data_quality": data_quality,
        "has_search_ctx": bool(search_ctx),
    })

    prompt = _build_biz_prompt(domain, crawl_result or CrawlResult(url=domain), search_ctx)
    result_str = ""

    with CaptureError("biz_ai", log_level="warning") as ctx:
        if client_gpt:
            result_str = call_gpt(client_gpt, prompt, system=_BIZ_SYSTEM,
                                   max_tokens=500, model=model_gpt, temperature=0.15)
        elif client_gemini:
            result_str = call_gemini(client_gemini, prompt, max_tokens=500, temperature=0.15)

    if not ctx.ok:
        state.errors.append(f"biz_ai: {ctx.error}")

    biz_dict = {}
    with CaptureError("biz_parse", log_level="warning"):
        m = re.search(r'\{.*\}', result_str, re.DOTALL)
        if m:
            biz_dict = json.loads(m.group())

    # ── 업종 모호 → retry with 크롤 컨텍스트 명시 ──
    if biz_dict:
        industry = biz_dict.get("industry", "")
        is_vague = any(bad in industry.lower() for bad in _BAD_INDUSTRIES)
        _body = crawl_result.body_text if crawl_result else ""
        if is_vague and (_body or search_ctx):
            retry_ctx = (
                f"사이트 본문: {_body[:800]}\n검색 보완: {search_ctx[:500]}"
                if _body else search_ctx[:1000]
            )
            retry_p = BIZ_INDUSTRY_RETRY_TMPL.format(domain=domain, retry_ctx=retry_ctx)
            with CaptureError("biz_industry_retry", log_level="warning"):
                r2 = (call_gpt(client_gpt, retry_p, max_tokens=80, model=model_gpt, temperature=0.1)
                      if client_gpt else
                      call_gemini(client_gemini, retry_p, max_tokens=80, temperature=0.1))
                m2 = re.search(r'\{.*\}', r2, re.DOTALL)
                if m2:
                    ni = json.loads(m2.group()).get("industry", "")
                    if ni and not any(bad in ni.lower() for bad in _BAD_INDUSTRIES):
                        biz_dict["industry"] = ni
                        state.log("biz_industry_retry", {"original": industry, "corrected": ni})

    if not biz_dict:
        state.errors.append("biz_parse: JSON 파싱 실패, 폴백 사용")
        biz_dict = {
            "brand_name": stem.upper(),
            "industry": f"{stem} 서비스",
            "industry_category": "기타",
            "core_product": "서비스",
            "target_audience": "잠재 고객",
            "key_services": [],
            "confidence": "low",
        }

    biz_dict["crawl_tier"] = crawl_result.tier_used if crawl_result else 0

    # 사용자 확정 업종 최우선 반영
    if confirmed_industry.strip():
        biz_dict["industry"] = confirmed_industry.strip()
        biz_dict["confidence"] = "high"
        state.log("biz_user_override", {"industry": confirmed_industry})

    biz = BusinessInfo.from_dict(biz_dict)
    state.record_time("biz_analysis", time.time() - t0)
    state.log("biz_output", biz.to_dict())

    return biz


# ─────────────────────────────────────────────
# 질문 생성 with 크롤 컨텍스트 직접 주입
# ─────────────────────────────────────────────
def generate_questions_from_state(
    client_gpt, client_gemini,
    state: PipelineState,
    model_gpt: str,
    engine: str = "GPT",
) -> list[str]:
    """
    CrawlResult + BusinessInfo를 모두 참조한 질문 생성.
    기존 generate_target_questions()는 biz_info만 받고 크롤 데이터를 무시했음.
    이 함수는 실제 사이트 콘텐츠 키워드를 질문에 반영.
    """
    biz  = state.biz_info
    crawl = state.crawl_result

    if biz is None:
        state.errors.append("question_gen: biz_info 없음")
        return []

    t0 = time.time()

    # ── 크롤 데이터에서 핵심 키워드 추출 ──
    site_keywords = ""
    if crawl and crawl.body_text:
        # 빈도 높은 명사구 추출 (간단 버전: 2~4단어 연속 명사)
        body = crawl.body_text[:2000]
        # 한국어 키워드: 2자 이상 반복 단어
        ko_words = re.findall(r'[가-힣]{2,}', body)
        from collections import Counter
        top_ko = [w for w, _ in Counter(ko_words).most_common(10) if len(w) >= 2]
        # 영문 키워드
        en_words = re.findall(r'[A-Z][a-zA-Z]{3,}', body)
        top_en = list(dict.fromkeys(en_words))[:5]
        site_keywords = ", ".join(top_ko[:8] + top_en[:3])

    category_hint = _CATEGORY_HINTS.get(
        biz.industry_category,
        f"{biz.industry} 분야에서 {biz.target_audience}가 실제로 고민하는 핵심 질문"
    )
    services_str = ", ".join(biz.key_services) if biz.key_services else biz.core_product

    prompt = QUESTION_GEN_AUTO_TMPL.format(
        industry=biz.industry,
        brand_name=biz.brand_name,
        industry_category=biz.industry_category,
        services_str=services_str,
        target_audience=biz.target_audience,
        site_keywords_str=site_keywords if site_keywords else "(크롤 데이터 없음)",
        crawl_tier=biz.crawl_tier,
        confidence=biz.confidence,
        category_hint=category_hint,
    )

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

    if not ctx.ok:
        state.errors.append(f"question_gen: {ctx.error}")

    # 파싱
    lines = [ln.strip() for ln in result_str.split("\n") if ln.strip()]
    raw_questions = []
    for ln in lines:
        clean = re.sub(r'^[\d]+[.)]\s*', '', ln)
        clean = re.sub(r'^[-•*]\s*', '', clean)
        clean = re.sub(r'^\[.*?\]\s*', '', clean)
        clean = re.sub(r'^\*\*.*?\*\*\s*', '', clean).strip()
        if len(clean) > 10:
            if not clean.endswith("?"):
                clean += "?"
            raw_questions.append(clean)

    # ── Content Filter 적용 ──
    filtered = []
    filter_results = []
    for q in raw_questions:
        fr = content_filter(q, biz.brand_name)
        filter_results.append({"question": q, **fr})
        if fr["pass"]:
            filtered.append(q)
        else:
            state.log("question_filtered", {"question": q, "reason": fr["reason"]})

    state.log("question_gen", {
        "raw_count": len(raw_questions),
        "filtered_count": len(filtered),
        "filter_results": filter_results,
        "site_keywords_used": site_keywords,
    })

    questions = filtered[:5]

    # 필터링 후 부족하면 미통과 항목도 추가 (최소 3개 보장)
    if len(questions) < 3:
        for q in raw_questions:
            if q not in questions:
                questions.append(q)
            if len(questions) >= 5:
                break

    # 폴백
    if len(questions) < 3:
        is_ad = "광고" in biz.industry or "마케팅" in biz.industry
        state.errors.append("question_gen: 폴백 질문 사용")
        questions = (
            [
                f"{biz.brand_name}의 퍼포먼스 광고 ROAS가 타 대행사 대비 어떤 수준인가요?",
                f"{biz.brand_name}에 광고를 맡기기 전 확인할 계약 조건과 대행수수료 구조는?",
                f"{biz.brand_name}의 업종별 광고 집행 성공 사례와 실제 CPA 달성치는?",
                f"{biz.brand_name} 광고 직접 운영 대비 ROI 차이가 어느 정도 나나요?",
                f"{biz.brand_name}과 경쟁 광고대행사를 동시 운영해본 마케터의 평가는?",
            ] if is_ad else [
                f"{biz.brand_name}이 {biz.industry}에서 경쟁사 대비 실제로 다른 점은?",
                f"{biz.target_audience}가 {biz.brand_name} 선택 후 6개월 내 실제 성과는?",
                f"{biz.brand_name}의 비용 구조가 동종 업계 대비 어떤 수준인가요?",
                f"{biz.brand_name} 실제 사용자 평가와 주요 불만 사항은?",
                f"{biz.industry}에서 {biz.brand_name}과 직접 비교되는 대안 서비스는?",
            ]
        )

    state.record_time("question_gen", time.time() - t0)
    return questions[:5]


# ─────────────────────────────────────────────
# 메인 파이프라인 실행기
# ─────────────────────────────────────────────
def run_pipeline(
    client_gpt, client_gemini,
    url: str,
    model_gpt: str,
    confirmed_industry: str = "",
    confirmed_brand: str = "",
    q_engine: str = "GPT",
    market_scope: str = "국내 (대한민국)",
    n_competitors: int = 5,
    tracker: Optional[CostTracker] = None,
    use_cache: bool = True,
    debug: bool = False,
    status_callback=None,  # (stage: str, msg: str) → None
) -> PipelineState:
    """
    단일 진입점. 모든 파이프라인 단계를 순서대로 실행.

    단계:
    1. crawl (+ 검색 보완) ← 결과를 state에 저장, 이후 모든 단계가 재사용
    2. biz analysis (crawl_result 직접 수신)
    3. competitor discovery + crawl (병렬)
    4. question generation (crawl + biz 모두 참조)
    5. citation spot-check (시뮬레이션 전 정확도 검증)
    """
    from urllib.parse import urlparse
    try:
        p = urlparse(url if url.startswith("http") else "https://" + url)
        domain = p.netloc.replace("www.", "")
    except Exception:
        domain = url

    state = PipelineState(url=url, domain=domain)
    cache = get_cache()

    def _cb(stage: str, msg: str):
        if status_callback:
            status_callback(stage, msg)
        if debug:
            logger.info(f"[{stage}] {msg}")

    # ──────────────────────────────────────────
    # Step 1: 크롤링 + 검색 보완 (병렬)
    # ──────────────────────────────────────────
    _cb("crawl", f"{domain} 크롤링 중 (3-tier fallback)...")
    t0 = time.time()

    if use_cache:
        key = cache.make_key("pipeline_crawl", url)
        cached_crawl = cache.get(key)
        if cached_crawl:
            from core.crawler import CrawlResult as CR
            state.crawl_result = CR(**cached_crawl["crawl"])
            state.search_ctx   = cached_crawl.get("search_ctx", "")
            _cb("crawl", f"캐시 히트 (Tier{state.crawl_result.tier_used})")
            state.record_time("crawl", 0)
        else:
            cached_crawl = None

    if state.crawl_result is None:
        stem = domain.split(".")[0]

        def _do_crawl():
            return crawl(url, use_cache=False)

        def _do_search():
            ctx = crawl_search(f"{stem} 서비스 업종 소개")
            if not ctx:
                ctx = crawl_search(f"{stem} company overview")
            return ctx or ""

        with cf.ThreadPoolExecutor(max_workers=2) as ex:
            f_crawl  = ex.submit(_do_crawl)
            f_search = ex.submit(_do_search)
            with CaptureError("crawl_future", log_level="warning") as ctx:
                state.crawl_result = f_crawl.result(timeout=25)
            if not ctx.ok:
                state.errors.append(f"crawl: {ctx.error}")
                from core.crawler import CrawlResult as CR
                state.crawl_result = CR(url=url, ok=False, tier_used=0)
            with CaptureError("search_future", log_level="warning"):
                state.search_ctx = f_search.result(timeout=20)

        if use_cache and state.crawl_result.ok:
            cache.set(cache.make_key("pipeline_crawl", url), {
                "crawl": {
                    "url": state.crawl_result.url,
                    "title": state.crawl_result.title,
                    "description": state.crawl_result.description,
                    "body_text": state.crawl_result.body_text,
                    "html_snippet": state.crawl_result.html_snippet,
                    "tier_used": state.crawl_result.tier_used,
                    "ok": state.crawl_result.ok,
                    "error": state.crawl_result.error,
                },
                "search_ctx": state.search_ctx,
            }, namespace="crawl")

    state.record_time("crawl", time.time() - t0)
    state.log("crawl", {
        "tier": state.crawl_result.tier_used,
        "ok": state.crawl_result.ok,
        "body_len": len(state.crawl_result.body_text),
        "title": state.crawl_result.title[:80],
        "search_ctx_len": len(state.search_ctx),
    })
    _cb("crawl", f"완료 (Tier{state.crawl_result.tier_used}, 본문 {len(state.crawl_result.body_text)}자)")

    # ──────────────────────────────────────────
    # Step 2: Biz 분석 + 경쟁사 도출 (병렬)
    # ──────────────────────────────────────────
    _cb("biz", "업종 AI 분석 중...")
    t0 = time.time()

    # biz 캐시 체크
    biz_cache_key = cache.make_key("pipeline_biz", url, confirmed_industry)
    if use_cache:
        cached_biz = cache.get(biz_cache_key)
        if cached_biz:
            state.biz_info = BusinessInfo.from_dict(cached_biz)
            _cb("biz", f"캐시 히트: {state.biz_info.brand_name} | {state.biz_info.industry}")

    def _do_biz():
        return analyze_business_from_crawl(
            client_gpt, client_gemini, state,
            model_gpt=model_gpt,
            confirmed_industry=confirmed_industry,
        )

    def _do_competitors():
        if state.biz_info is None:
            return []  # biz 완료 대기 필요 — 직렬 실행으로 처리
        return discover_competitors(
            client_gpt, client_gemini,
            state.biz_info, url,
            market_scope=market_scope,
            model_gpt=model_gpt,
            n_competitors=n_competitors,
            use_cache=use_cache,
        )

    # biz 완료 후 competitors 실행 (biz 결과 의존성)
    if state.biz_info is None:
        state.biz_info = _do_biz()
        if use_cache:
            cache.set(biz_cache_key, state.biz_info.to_dict(), namespace="biz")

    state.record_time("biz", time.time() - t0)

    # 사용자가 직접 입력한 브랜드명이 있으면 AI 추출값 덮어쓰기
    if confirmed_brand.strip() and state.biz_info:
        state.biz_info.brand_name = confirmed_brand.strip()
        state.log("brand_override", {"brand_name": confirmed_brand.strip()})

    _cb("biz", f"완료: {state.biz_info.brand_name} | {state.biz_info.industry} | {state.biz_info.confidence}")

    # 경쟁사 병렬 실행 (biz 완료 후, question gen과 동시에)
    _cb("competitors", f"[{market_scope}] 경쟁사 분석 중...")

    # ──────────────────────────────────────────
    # Step 3: 질문 생성 + 경쟁사 도출 (병렬)
    # ──────────────────────────────────────────
    _cb("questions", "크롤 데이터 기반 타겟 질문 도출 중...")
    t0 = time.time()

    q_cache_key = cache.make_key(
        "pipeline_questions", url, state.biz_info.industry, q_engine
    )
    if use_cache:
        cached_q = cache.get(q_cache_key)
        if cached_q:
            state.questions = cached_q
            _cb("questions", f"캐시 히트: {len(state.questions)}개")

    comp_future = None
    with cf.ThreadPoolExecutor(max_workers=2) as executor:
        comp_future = executor.submit(_do_competitors)

        if not state.questions:
            state.questions = generate_questions_from_state(
                client_gpt, client_gemini, state,
                model_gpt=model_gpt, engine=q_engine,
            )
            if use_cache and state.questions:
                cache.set(q_cache_key, state.questions, namespace="biz")
    # executor.__exit__ → shutdown(wait=True): comp_future 완료 보장

    state.record_time("question_gen", time.time() - t0)
    _cb("questions", f"완료: {len(state.questions)}개 질문 (content filter 통과)")

    # 경쟁사 결과 수집 (이미 완료된 future에서 즉시 반환)
    with CaptureError("comp_collect", log_level="warning") as ctx:
        state.competitors = comp_future.result(timeout=5) if comp_future else []
    if not ctx.ok:
        state.errors.append(f"competitors: {ctx.error}")
        state.competitors = []
    _cb("competitors", f"완료: {len(state.competitors)}개")

    # ──────────────────────────────────────────
    # Step 4: Citation Spot-Check (첫 번째 질문으로)
    # ──────────────────────────────────────────
    if state.questions and (client_gpt or client_gemini):
        _cb("spot_check", "Citation 정확도 spot-check 중 (5회 샘플)...")
        t0 = time.time()
        brand_variants = build_brand_variants(url, state.biz_info.to_dict())
        first_q = state.questions[0]

        spot_cache_key = cache.make_key(
            "spot_check", url, first_q, ",".join(sorted(brand_variants))
        )
        cached_spot = cache.get(spot_cache_key) if use_cache else None

        if cached_spot:
            state.spot_check = cached_spot
            state.record_time("spot_check", 0)
            _cb("spot_check",
                f"캐시 히트 | 초기 점유율: {cached_spot['hit_rate']}% | FP: {cached_spot['false_positive_risk']}")
        else:
            spot = citation_spot_check(
                client_gpt, client_gemini,
                brand_variants=brand_variants,
                question=first_q,
                model_gpt=model_gpt,
                n_samples=5,
                tracker=tracker,
            )
            state.spot_check = spot
            if use_cache:
                cache.set(spot_cache_key, spot, namespace="spot_check")
            state.record_time("spot_check", time.time() - t0)
            state.log("spot_check", spot)
            _cb("spot_check",
                f"완료 | 초기 점유율: {spot['hit_rate']}% | FP 리스크: {spot['false_positive_risk']}")

    return state


# ─────────────────────────────────────────────
# Debug 패널 렌더링 (app.py에서 호출)
# ─────────────────────────────────────────────
def render_debug_panel(state: PipelineState):
    """Streamlit debug 패널 — 각 단계 입출력 표시"""
    import streamlit as st
    import pandas as pd

    st.markdown("---")
    st.markdown("### 🔬 Debug 패널")

    # 타이밍
    if state.timing:
        cols = st.columns(len(state.timing))
        for i, (k, v) in enumerate(state.timing.items()):
            cols[i].metric(k, f"{v}s")

    # 에러 목록
    if state.errors:
        st.error("**파이프라인 에러:**\n" + "\n".join(f"- {e}" for e in state.errors))

    # 크롤 결과
    with st.expander("🌐 Crawl 결과", expanded=False):
        if state.crawl_result:
            cr = state.crawl_result
            st.json({
                "tier": cr.tier_used,
                "ok": cr.ok,
                "title": cr.title,
                "description": cr.description[:200],
                "body_len": len(cr.body_text),
                "body_preview": cr.body_text[:500],
            })
        else:
            st.warning("크롤 결과 없음")
        if state.search_ctx:
            st.text_area("검색 보완 컨텍스트", value=state.search_ctx[:1000], height=150)

    # Biz 분석 결과
    with st.expander("🏢 Biz 분석 결과", expanded=False):
        if state.biz_info:
            st.json(state.biz_info.to_dict())
        else:
            st.warning("Biz 분석 결과 없음")

    # 질문 Content Filter 결과
    with st.expander("📝 질문 생성 + Content Filter", expanded=False):
        q_log = [l for l in state.debug_log if l["stage"] in ("question_gen", "question_filtered")]
        if q_log:
            for entry in q_log:
                if entry["stage"] == "question_gen" and "filter_results" in entry:
                    rows = []
                    for fr in entry["filter_results"]:
                        rows.append({
                            "질문": fr["question"][:60],
                            "점수": fr["score"],
                            "통과": "✅" if fr["pass"] else "❌",
                            "사유": fr["reason"][:50],
                        })
                    if rows:
                        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                    st.caption(f"사이트 키워드: {entry.get('site_keywords_used', '없음')}")
                elif entry["stage"] == "question_filtered":
                    st.caption(f"❌ 필터링됨: {entry.get('question','')[:50]} — {entry.get('reason','')}")
        else:
            st.info("질문 생성 로그 없음")

    # Citation Spot-Check
    with st.expander("🎯 Citation Spot-Check", expanded=False):
        if state.spot_check:
            sp = state.spot_check
            c1, c2, c3 = st.columns(3)
            c1.metric("초기 점유율 추정", f"{sp['hit_rate']}%")
            c2.metric("FP 리스크", sp["false_positive_risk"])
            c3.metric("샘플 수", sp["n_samples"])
            if sp.get("suspect_variants"):
                st.warning(f"⚠️ 오탐 의심 변형: {sp['suspect_variants']}")
            if sp.get("refined_variants"):
                st.info(f"✅ 정제된 변형 ({len(sp['refined_variants'])}개): "
                        f"{sp['refined_variants']}")
            # 샘플 응답
            for i, s in enumerate(sp.get("sample_responses", [])[:3]):
                color = "✅" if s["cited"] else "❌"
                conf  = s.get("confidence", 0)
                st.markdown(
                    f"**샘플 {i+1}** {color} "
                    f"confidence={conf:.2f} "
                    f"pattern={s.get('pattern_type','—')}"
                )
                st.caption(s["response"][:200])
        else:
            st.info("Spot-check 데이터 없음")

    # 전체 디버그 로그
    with st.expander("📋 전체 파이프라인 로그", expanded=False):
        for entry in state.debug_log:
            stage = entry.get("stage", "?")
            ts    = entry.get("ts", 0)
            rest  = {k: v for k, v in entry.items() if k not in ("stage", "ts")}
            st.markdown(f"**[{stage}]** `{ts:.2f}`")
            st.json(rest)
