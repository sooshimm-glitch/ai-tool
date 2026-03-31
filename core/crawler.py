"""
3단계 Fallback 크롤러
Tier 1: Jina Reader (JS 렌더링, 봇차단 우회)
Tier 2: requests + BeautifulSoup (직접 크롤링)
Tier 3: Jina Search (검색 결과 기반 메타데이터 추론)

각 단계 실패 시 다음 단계로 자동 폴백.
외부 의존성 장애 시에도 전체 기능 유지.
"""

import re
import time
import requests
from urllib.parse import urlparse, quote
from html.parser import HTMLParser
from dataclasses import dataclass, field
from typing import Optional

from .logger import get_logger, CaptureError
from .cache import get_cache

logger = get_logger("crawler")


# ── 결과 스키마 ──
@dataclass
class CrawlResult:
    url: str
    title: str = ""
    description: str = ""
    body_text: str = ""       # 주요 본문 (AI 분석용)
    html_snippet: str = ""    # 원본 HTML 일부
    tier_used: int = 0        # 성공한 티어 (1/2/3/0=실패)
    ok: bool = False
    error: str = ""

    def summary(self, max_len: int = 3000) -> str:
        """AI 프롬프트에 주입할 컨텍스트 문자열"""
        parts = []
        if self.title:
            parts.append(f"[제목] {self.title}")
        if self.description:
            parts.append(f"[설명] {self.description}")
        if self.body_text:
            parts.append(f"[본문]\n{self.body_text[:max_len]}")
        return "\n".join(parts)


# ── HTML 메타 파서 ──
class MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.description = ""
        self.og_title = ""
        self.og_description = ""
        self.keywords = ""
        self._in_title = False
        self._body_text_parts: list[str] = []
        self._skip_tags = {"script", "style", "noscript", "svg", "head"}
        self._current_skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._skip_tags:
            self._current_skip += 1
        if tag == "title":
            self._in_title = True
        a = dict(attrs)
        name = a.get("name", "").lower()
        prop = a.get("property", "").lower()
        content = a.get("content", "")
        if name == "description":
            self.description = content
        elif name == "keywords":
            self.keywords = content
        elif prop == "og:title":
            self.og_title = content
        elif prop == "og:description":
            self.og_description = content

    def handle_endtag(self, tag):
        if tag in self._skip_tags:
            self._current_skip = max(0, self._current_skip - 1)
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title and not self.title:
            self.title = data.strip()
        if self._current_skip == 0:
            text = data.strip()
            if len(text) > 15:
                self._body_text_parts.append(text)

    @property
    def body_text(self) -> str:
        return " ".join(self._body_text_parts)[:5000]


_HEADERS_PC = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_JINA_HEADERS = {
    "Accept": "text/markdown, text/plain, */*",
    "X-Return-Format": "markdown",
    "X-Timeout": "12",
}


def _extract_domain(url: str) -> str:
    try:
        p = urlparse(url if url.startswith("http") else "https://" + url)
        return p.netloc.replace("www.", "")
    except Exception:
        return url


def _normalize(url: str) -> str:
    if not url.startswith("http"):
        url = "https://" + url
    return url.rstrip("/")


# ─────────────────────────────────────────────
# Tier 1: Jina Reader
# ─────────────────────────────────────────────
def _tier1_jina_reader(url: str) -> Optional[CrawlResult]:
    jina_url = f"https://r.jina.ai/{url}"
    with CaptureError("tier1_jina", log_level="info") as ctx:
        resp = requests.get(jina_url, headers=_JINA_HEADERS, timeout=18)
        if resp.status_code != 200:
            raise ValueError(f"Jina HTTP {resp.status_code}")
        md = resp.text.strip()
        if len(md) < 300:
            raise ValueError("Jina 응답 너무 짧음")

        # 제목 파싱 (첫 번째 # 헤딩)
        title = ""
        for line in md.splitlines():
            line = line.strip()
            if line.startswith("#"):
                title = line.lstrip("#").strip()
                break
            elif line:
                title = line[:120]
                break

        # 설명: 첫 단락
        desc = ""
        for line in md.splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                if desc:
                    break
                continue
            desc += s + " "
            if len(desc) > 400:
                break

        return CrawlResult(
            url=url,
            title=title,
            description=desc.strip()[:400],
            body_text=md[:5000],
            tier_used=1,
            ok=True,
        )
    if not ctx.ok:
        logger.info(f"Tier1 실패 ({url}): {ctx.error}")
    return None


# ─────────────────────────────────────────────
# Tier 2: requests + BeautifulSoup
# ─────────────────────────────────────────────
def _tier2_requests_bs(url: str) -> Optional[CrawlResult]:
    with CaptureError("tier2_requests", log_level="info") as ctx:
        resp = requests.get(url, headers=_HEADERS_PC, timeout=12, allow_redirects=True)
        resp.encoding = resp.apparent_encoding or "utf-8"
        html = resp.text

        # 봇차단 감지
        bot_signals = [
            "자동등록방지", "captcha", "access denied",
            "prove that you are human", "cloudflare", "ddos-guard"
        ]
        if any(s in html.lower() for s in bot_signals):
            raise ValueError("봇차단 감지")

        if len(html) < 500:
            raise ValueError("응답 너무 짧음")

        parser = MetaParser()
        parser.feed(html[:120_000])

        title = parser.og_title or parser.title or ""
        desc  = parser.og_description or parser.description or ""
        body  = parser.body_text

        # 본문 노이즈 제거: 2단어 미만 토큰 제거
        body_cleaned = re.sub(r'\s{3,}', '  ', body)[:4000]

        return CrawlResult(
            url=url,
            title=title,
            description=desc[:400],
            body_text=body_cleaned,
            html_snippet=html[:2000],
            tier_used=2,
            ok=True,
        )
    if not ctx.ok:
        logger.info(f"Tier2 실패 ({url}): {ctx.error}")
    return None


# ─────────────────────────────────────────────
# Tier 3: Jina Search (검색 결과 기반 추론)
# ─────────────────────────────────────────────
def _tier3_jina_search(url: str) -> Optional[CrawlResult]:
    domain = _extract_domain(url)
    stem   = domain.split(".")[0]
    queries = [
        f"{stem} 서비스 소개 업종",
        f"site:{domain} 서비스",
        f"{stem} company overview",
    ]
    with CaptureError("tier3_jina_search", log_level="info") as ctx:
        for q in queries:
            search_url = f"https://s.jina.ai/{quote(q)}"
            r = requests.get(
                search_url,
                headers={**_JINA_HEADERS, "X-Timeout": "10"},
                timeout=15,
            )
            if r.status_code == 200 and len(r.text) > 200:
                body = r.text[:4000]
                # 첫 번째 비어있지 않은 줄을 제목으로
                title = next(
                    (ln.strip().lstrip("#") for ln in body.splitlines() if ln.strip()),
                    stem.upper()
                )
                return CrawlResult(
                    url=url,
                    title=title,
                    description=body[:300],
                    body_text=body,
                    tier_used=3,
                    ok=True,
                )
    if not ctx.ok:
        logger.warning(f"Tier3 실패 ({url}): {ctx.error}")
    return None


# ─────────────────────────────────────────────
# 공개 API
# ─────────────────────────────────────────────
def crawl(url: str, use_cache: bool = True) -> CrawlResult:
    """
    3단계 fallback 크롤러.
    캐시 히트 시 즉시 반환 (비용 0).
    """
    url = _normalize(url)
    cache = get_cache()

    if use_cache:
        key = cache.make_key("crawl", url)
        cached = cache.get(key)
        if cached:
            logger.info(f"Cache HIT: crawl({url})")
            return CrawlResult(**cached)

    result = None
    for tier_fn in [_tier1_jina_reader, _tier2_requests_bs, _tier3_jina_search]:
        result = tier_fn(url)
        if result and result.ok:
            logger.info(f"Crawl OK Tier{result.tier_used}: {url}")
            break

    if result is None:
        logger.warning(f"All crawl tiers failed: {url}")
        domain = _extract_domain(url)
        result = CrawlResult(
            url=url,
            title=domain,
            description="",
            body_text="",
            tier_used=0,
            ok=False,
            error="All tiers failed",
        )

    if use_cache and result.ok:
        key = cache.make_key("crawl", url)
        cache.set(key, {
            "url": result.url,
            "title": result.title,
            "description": result.description,
            "body_text": result.body_text,
            "html_snippet": result.html_snippet,
            "tier_used": result.tier_used,
            "ok": result.ok,
            "error": result.error,
        }, namespace="crawl")

    return result


def crawl_search(query: str, use_cache: bool = True) -> str:
    """
    Jina Search API로 검색 결과 마크다운 반환.
    경쟁사 도출, 업종 검증에 사용.
    """
    cache = get_cache()
    if use_cache:
        key = cache.make_key("crawl_search", query)
        cached = cache.get(key)
        if cached:
            return cached

    with CaptureError("crawl_search", log_level="warning") as ctx:
        search_url = f"https://s.jina.ai/{quote(query)}"
        r = requests.get(
            search_url,
            headers={**_JINA_HEADERS, "X-Timeout": "12"},
            timeout=18,
        )
        if r.status_code == 200 and len(r.text) > 200:
            result = r.text[:5000]
            if use_cache:
                key = cache.make_key("crawl_search", query)
                cache.set(key, result, namespace="crawl")
            return result

    return ""
