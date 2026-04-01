"""
strategy_analyzer.py — 전략 분석 전담 모듈

경쟁사 분석 · 인용 실패 진단 · 블루오션 키워드 · GEO 가이드 4개 병렬 실행.
기존 biz_analysis.py에서 run_strategy_analysis() 분리.
"""

from __future__ import annotations

import re
import json
import concurrent.futures
from typing import Optional
from urllib.parse import urlparse

from .logger import get_logger, CaptureError
from .cache import get_cache
from .ai_client import call_gpt, call_gemini
from .schemas import BusinessInfo
from .prompts import (
    STRATEGY_SYSTEM,
    STRATEGY_COMP_TMPL,
    STRATEGY_DIAG_TMPL,
    STRATEGY_KW_TMPL,
    STRATEGY_GEO_TMPL,
)

logger = get_logger("strategy_analyzer")

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
    """
    경쟁사·진단·키워드·GEO 가이드 4개를 병렬로 생성해 반환.

    반환:
    {
        "competitors": list[dict],
        "diagnoses":   list[str],
        "keywords":    list[str],
        "geo_guides":  list[str],
    }
    """
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

    # ── 4개 서브태스크 정의 ──────────────────────
    def _competitors() -> list:
        prompt = STRATEGY_COMP_TMPL.format(
            question=question,
            brand_name=biz.brand_name,
            industry=biz.industry,
            scope_inst=scope_inst,
            domain=domain,
        )
        raw = ""
        with CaptureError("strategy_comp", log_level="warning"):
            raw = (
                call_gpt(client_gpt, prompt, system=STRATEGY_SYSTEM,
                         max_tokens=1200, model=model_gpt, temperature=0.3)
                if client_gpt else
                call_gemini(client_gemini, prompt, max_tokens=1200, temperature=0.3)
            )
        if raw:
            with CaptureError("strategy_comp_parse", log_level="warning"):
                m = re.search(r'\[.*\]', raw, re.DOTALL)
                if m:
                    parsed = json.loads(m.group())
                    real = [
                        c for c in parsed
                        if c.get("domain") and
                        not re.match(
                            r'^(c\d+|competitor\d*|example|test|dummy)\.',
                            str(c.get("domain", ""))
                        )
                    ]
                    if real:
                        return real
        return []

    def _diagnosis() -> list[str]:
        prompt = STRATEGY_DIAG_TMPL.format(
            domain=domain,
            brand_name=biz.brand_name,
            industry=biz.industry,
            question=question,
        )
        with CaptureError("strategy_diag", log_level="warning") as ctx:
            r = (
                call_gpt(client_gpt, prompt, system=STRATEGY_SYSTEM,
                         max_tokens=600, model=model_gpt, temperature=0.4)
                if client_gpt else
                call_gemini(client_gemini, prompt, max_tokens=600, temperature=0.4)
            )
            items = [d.strip().lstrip("•-*") for d in r.split("\n") if d.strip()][:3]
            if items:
                return items
        return ["데이터 부족으로 분석 불가"]

    def _keywords() -> list[str]:
        prompt = STRATEGY_KW_TMPL.format(
            industry=biz.industry,
            scope_inst=scope_inst,
        )
        with CaptureError("strategy_kw", log_level="warning") as ctx:
            r = (
                call_gemini(client_gemini, prompt, max_tokens=600, temperature=0.7)
                if client_gemini else
                call_gpt(client_gpt, prompt, system=STRATEGY_SYSTEM,
                         max_tokens=600, model=model_gpt, temperature=0.7)
            )
            items = [
                k.strip().lstrip("•-*1234567890. ")
                for k in r.split("\n")
                if k.strip() and len(k.strip()) > 2
            ][:5]
            if items:
                return items
        return ["분석 중 오류"]

    def _geo() -> list[str]:
        prompt = STRATEGY_GEO_TMPL.format(
            domain=domain,
            brand_name=biz.brand_name,
            question=question,
        )
        with CaptureError("strategy_geo", log_level="warning") as ctx:
            r = (
                call_gpt(client_gpt, prompt, system=STRATEGY_SYSTEM,
                         max_tokens=1000, model=model_gpt, temperature=0.5)
                if client_gpt else
                call_gemini(client_gemini, prompt, max_tokens=1000, temperature=0.5)
            )
            items = [g.strip() for g in re.split(r'\n(?=\d+\.)', r) if g.strip()][:3]
            if items:
                return items
        return ["분석 중 오류"]

    # ── 4개 병렬 실행 ──────────────────────────
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        f_comp = ex.submit(_competitors)
        f_diag = ex.submit(_diagnosis)
        f_kw   = ex.submit(_keywords)
        f_geo  = ex.submit(_geo)

    # with 블록 종료 후 결과 수집 — timeout 예외가 다른 Future에 영향 안 줌
    def _safe_result(future, fallback, timeout=60):
        try:
            return future.result(timeout=timeout) or fallback
        except Exception:
            return fallback

    competitors = _safe_result(f_comp, [])
    diagnoses   = _safe_result(f_diag, ["데이터 부족으로 분석 불가"])
    keywords    = _safe_result(f_kw,   ["분석 중 오류"])
    geo_guides  = _safe_result(f_geo,  ["분석 중 오류"])

    result = {
        "competitors": competitors,
        "diagnoses":   diagnoses,
        "keywords":    keywords,
        "geo_guides":  geo_guides,
    }

    if use_cache:
        cache.set(cache_key, result, namespace="strategy")

    return result
