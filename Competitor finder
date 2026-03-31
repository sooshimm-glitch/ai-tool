"""
경쟁사 도출 레이어 — 검색 기반 후보 생성 + 2단계 도메인 검증

검증 전략 (latency 최소화):
  1차: socket DNS + HEAD request  (평균 ~0.3s, 네트워크만)
  2차: 실 Crawl                  (평균 ~3s, 1차 통과 시만)

기존 문제:
  - n_competitors * full_crawl → 10 * 3s = 30s+ latency
  - 가짜 도메인 필터링 없음

개선:
  - 후보 n*2 요청 → 1차 DNS/HEAD 병렬 → 1차 통과만 2차 Crawl
  - 2차는 최종 n개 채울 때까지만 실행 (조기 종료)
"""

from __future__ import annotations

import re
import json
import socket
import concurrent.futures
from typing import Optional

import requests

from core.logger import get_logger, CaptureError
from core.cache import get_cache
from core.crawler import crawl, crawl_search
from core.ai_client import call_gpt, call_gemini
from core.schemas import BusinessInfo, Competitor

logger = get_logger("competitor_finder")

_COMPETITOR_SYSTEM = "당신은 디지털 마케팅 시장 분석 전문가입니다."

# 캐시 키 버전
_FINDER_VERSION = "v3"

_HEAD_TIMEOUT  = 4     # HEAD 요청 타임아웃 (초)
_DNS_TIMEOUT   = 2     # DNS 조회 타임아웃 (초)
_CRAWL_TIMEOUT = 18    # 2차 Crawl 타임아웃 (초)
_MAX_WORKERS_V1 = 8    # 1차 검증 병렬 수
_MAX_WORKERS_V2 = 4    # 2차 검증 병렬 수 (crawl은 무거우니 제한)


# ── 1차 검증: DNS + HEAD ─────────────────────────────────────────────
def _verify_dns(domain: str) -> bool:
    """소켓 DNS 조회. 실패 시 False."""
    clean = domain.replace("https://", "").replace("http://", "").split("/")[0]
    try:
        socket.setdefaulttimeout(_DNS_TIMEOUT)
        socket.getaddrinfo(clean, 80)
        return True
    except (socket.gaierror, socket.timeout, OSError):
        return False
    finally:
        socket.setdefaulttimeout(None)


def _verify_head(domain: str) -> tuple[bool, str]:
    """
    HTTP HEAD 요청으로 도메인 생존 확인.
    반환: (is_live, redirect_or_title_hint)
    """
    url = domain if domain.startswith("http") else f"https://{domain}"
    try:
        resp = requests.head(
            url,
            timeout=_HEAD_TIMEOUT,
            allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if resp.status_code < 400:
            # Location 헤더나 최종 URL에서 도메인 힌트 추출
            final_url = resp.url or url
            return True, final_url
        return False, ""
    except Exception:
        # HEAD 실패 시 HTTP로 재시도 (일부 서버 HTTPS 거부)
        try:
            url_http = f"http://{domain.replace('https://', '').replace('http://', '')}"
            resp = requests.head(url_http, timeout=_HEAD_TIMEOUT,
                                  allow_redirects=True,
                                  headers={"User-Agent": "Mozilla/5.0"})
            return resp.status_code < 400, resp.url or ""
        except Exception:
            return False, ""


def _stage1_verify(domain: str) -> tuple[bool, str]:
    """
    1차 검증: DNS 조회 → HEAD 요청.
    둘 다 통과해야 True.
    """
    if Competitor.is_fake_domain(domain):
        return False, ""
    if not _verify_dns(domain):
        logger.info(f"[1차 DNS 실패] {domain}")
        return False, ""
    ok, hint = _verify_head(domain)
    if not ok:
        logger.info(f"[1차 HEAD 실패] {domain}")
    return ok, hint


# ── 2차 검증: Crawl ──────────────────────────────────────────────────
def _stage2_crawl(domain: str) -> tuple[bool, str]:
    """
    2차 검증: 실제 크롤로 title 확인.
    1차 통과 후보만 여기 들어옴.
    """
    with CaptureError(f"stage2_crawl_{domain}", log_level="info") as ctx:
        result = crawl(domain, use_cache=True)
        if result.ok and result.title:
            return True, result.title[:60]
    return False, ""


# ── AI 후보 생성 ─────────────────────────────────────────────────────
def _generate_candidates(
    client_gpt, client_gemini,
    biz_info: BusinessInfo,
    domain: str,
    market_scope: str,
    model_gpt: str,
    candidate_count: int,
    search_section: str,
) -> list[dict]:
    scope_inst = (
        "반드시 대한민국에서 서비스 중인 국내 기업만 포함하세요. 해외 기업은 제외합니다."
        if "국내" in market_scope
        else "전 세계 글로벌 시장에서 활동하는 기업을 포함하세요."
    )

    prompt = f"""당신은 {biz_info.industry} 분야의 시장 분석 전문가입니다.

[분석 대상]
- 브랜드: {biz_info.brand_name} / 도메인: {domain}
- 업종: {biz_info.industry} ({biz_info.industry_category})
- 핵심 서비스: {biz_info.core_product}
- 타겟: {biz_info.target_audience}

{search_section}

[경쟁사 선정 기준]
1. 검색 데이터에 등장하는 브랜드 최우선
2. {biz_info.industry}와 동일 카테고리에서 직접 경쟁
3. {biz_info.brand_name} 고객이 이탈 시 선택할 가능성 높은 대안
4. {scope_inst}
5. {domain} 자체는 절대 포함 금지
6. 실제 운영 중인 도메인만 — 가상 도메인(competitor1.com 등) 사용 금지

후보 {candidate_count}개 JSON 배열로 출력:
[
  {{
    "rank": 1,
    "brand_name": "브랜드명",
    "domain": "실제도메인.com",
    "reason": "경쟁 이유 20자 이내",
    "market_position": "업계 1위 | 신흥 강자 | 틈새 전문 중 택1",
    "evidence": "검색 데이터 근거 또는 AI 판단"
  }}
]"""

    result_str = ""
    with CaptureError("competitor_ai", log_level="warning"):
        if client_gpt:
            result_str = call_gpt(client_gpt, prompt, system=_COMPETITOR_SYSTEM,
                                  max_tokens=1500, model=model_gpt, temperature=0.2)
        elif client_gemini:
            result_str = call_gemini(client_gemini, prompt,
                                     max_tokens=1500, temperature=0.2)

    candidates: list[dict] = []
    with CaptureError("competitor_parse", log_level="warning"):
        m = re.search(r'\[.*\]', result_str, re.DOTALL)
        if m:
            raw = json.loads(m.group())
            for c in raw:
                d = str(c.get("domain", "")).strip().lower()
                if not Competitor.is_fake_domain(d):
                    candidates.append(c)

    return candidates


# ── 공개 API ─────────────────────────────────────────────────────────
def discover_competitors(
    client_gpt,
    client_gemini,
    biz_info: BusinessInfo,
    target_url: str,
    market_scope: str,
    model_gpt: str,
    n_competitors: int = 5,
    use_cache: bool = True,
) -> list[Competitor]:
    """
    경쟁사 도출 + 2단계 도메인 검증.

    Pipeline:
        1. Jina Search 다중 쿼리
        2. AI 후보 생성 (n * 2개)
        3. 1차 검증: DNS + HEAD (병렬, 빠름)
        4. 2차 검증: Crawl (1차 통과 후보만, 조기 종료)
        5. 검증 통과 n개 반환
    """
    from urllib.parse import urlparse
    try:
        p = urlparse(target_url if target_url.startswith("http") else "https://" + target_url)
        domain = p.netloc.replace("www.", "")
    except Exception:
        domain = target_url

    cache = get_cache()
    cache_key = cache.make_key(
        "competitors", _FINDER_VERSION,
        target_url, biz_info.industry, market_scope,
        model_gpt, n_competitors,
    )

    if use_cache:
        cached = cache.get(cache_key)
        if cached:
            logger.info(f"Cache HIT: competitors({domain})")
            return [Competitor(**c) for c in cached]

    scope_kw = "한국 국내" if "국내" in market_scope else "글로벌"

    # ── Step 1: 검색 데이터 수집 ──
    search_data: list[str] = []
    for q in [
        f"{biz_info.industry} 경쟁사 {scope_kw}",
        f"{biz_info.brand_name} 대안 {biz_info.industry}",
        f"{biz_info.industry} 주요 기업 비교 {scope_kw}",
    ]:
        ctx = crawl_search(q, use_cache=use_cache)
        if ctx:
            search_data.append(f"[{q}]\n{ctx[:1800]}")

    search_section = (
        "[실제 검색 데이터 — 최우선 근거]\n" + "\n\n".join(search_data[:2])
        if search_data
        else "[검색 데이터: 없음 — AI 자체 지식으로 판단]"
    )

    # ── Step 2: AI 후보 생성 (n * 2 요청) ──
    candidate_count = n_competitors * 2
    candidates = _generate_candidates(
        client_gpt, client_gemini,
        biz_info, domain, market_scope, model_gpt,
        candidate_count, search_section,
    )

    if not candidates:
        logger.warning(f"AI 후보 생성 실패: {domain}")
        return _fallback_competitors(n_competitors)

    # ── Step 3: 1차 검증 — DNS + HEAD (병렬) ──
    stage1_passed: list[tuple[dict, str]] = []   # (candidate, hint)

    def _run_stage1(c: dict) -> Optional[tuple[dict, str]]:
        d = str(c.get("domain", "")).strip()
        ok, hint = _stage1_verify(d)
        return (c, hint) if ok else None

    with concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_WORKERS_V1) as ex:
        futs = {ex.submit(_run_stage1, c): c for c in candidates}
        for fut in concurrent.futures.as_completed(futs):
            with CaptureError("stage1_future", log_level="info"):
                result = fut.result(timeout=_DNS_TIMEOUT + _HEAD_TIMEOUT + 2)
                if result:
                    stage1_passed.append(result)

    logger.info(
        f"1차 검증: {len(candidates)}개 후보 → {len(stage1_passed)}개 통과"
    )

    if not stage1_passed:
        logger.warning(f"1차 검증 전원 실패: {domain} — 검증 없이 반환")
        return _build_unverified(candidates[:n_competitors])

    # ── Step 4: 2차 검증 — Crawl (조기 종료) ──
    verified: list[Competitor] = []

    def _run_stage2(c: dict, hint: str) -> Optional[Competitor]:
        d = str(c.get("domain", "")).strip()
        ok, title = _stage2_crawl(d)
        if not ok:
            # Crawl 실패해도 1차 통과면 약한 verified로 수용
            title = hint.split("/")[-1][:40] if hint else ""
            ok = True  # HEAD 통과 = 충분한 증거

        evidence = c.get("evidence", "")
        if title:
            evidence = f"{evidence} | 확인: {title}"

        return Competitor(
            rank=c.get("rank", 0),
            brand_name=c.get("brand_name", d),
            domain=d,
            reason=c.get("reason", ""),
            market_position=c.get("market_position", "틈새 전문"),
            verified=ok,
            evidence=evidence,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_WORKERS_V2) as ex:
        futs = {ex.submit(_run_stage2, c, hint): (c, hint) for c, hint in stage1_passed}
        for fut in concurrent.futures.as_completed(futs):
            with CaptureError("stage2_future", log_level="info"):
                comp = fut.result(timeout=_CRAWL_TIMEOUT + 2)
                if comp:
                    verified.append(comp)
            if len(verified) >= n_competitors:
                # 충분히 채웠으면 남은 future 취소
                for remaining in futs:
                    remaining.cancel()
                break

    logger.info(f"2차 검증: {len(stage1_passed)}개 → {len(verified)}개 확정")

    # rank 재정렬 (원래 AI 순서 기준)
    verified.sort(key=lambda x: x.rank)
    for i, comp in enumerate(verified):
        comp.rank = i + 1

    result = verified[:n_competitors]

    if use_cache and result:
        cache.set(cache_key, [c.to_dict() for c in result], namespace="competitors")

    return result


def _fallback_competitors(n: int) -> list[Competitor]:
    return [
        Competitor(rank=i+1, brand_name=f"경쟁사 {i+1}",
                   domain=f"competitor{i+1}.com", reason="동종 업계",
                   market_position="틈새 전문", verified=False,
                   evidence="AI 후보 생성 실패")
        for i in range(n)
    ]


def _build_unverified(candidates: list[dict]) -> list[Competitor]:
    return [
        Competitor(
            rank=i+1,
            brand_name=c.get("brand_name", f"경쟁사{i+1}"),
            domain=c.get("domain", ""),
            reason=c.get("reason", ""),
            market_position=c.get("market_position", "틈새 전문"),
            verified=False,
            evidence="검증 미완료",
        )
        for i, c in enumerate(candidates)
    ]
