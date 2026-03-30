"""
AI 검색 점유율 분석 대시보드
============================
GPT & Gemini 기반 AI 인용 점유율 분석 도구
"""

import streamlit as st
import openai
import google.generativeai as genai
import json
import re
import time
import random
import datetime
import math
from collections import Counter
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from urllib.parse import urlparse
import concurrent.futures
import requests
from html.parser import HTMLParser

# ─────────────────────────────────────────────
# 페이지 설정
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="AI Citation Analyzer",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# 다크/라이트 모드 상태 초기화
# ─────────────────────────────────────────────
if "dark_mode" not in st.session_state:
    st.session_state["dark_mode"] = False

_dark = st.session_state["dark_mode"]

# ─────────────────────────────────────────────
# 글로벌 CSS — 다크/라이트 모드 통합 (오류 완벽 해결)
# ─────────────────────────────────────────────
if _dark:
    _bg        = "#0F0F0F"
    _bg2       = "#1A1A1A"
    _card      = "#1E1E1E"
    _border    = "#333333"
    _text      = "#F0F0F0"
    _text_muted= "#999999"
    _primary   = "#444444"
    _accent    = "#AAAAAA"
    _shadow    = "0 4px 24px rgba(0,0,0,0.5)"
    _shadow_h  = "0 8px 40px rgba(0,0,0,0.7)"
    _header_gr = "linear-gradient(135deg,#1A1A1A 0%,#2A2A2A 60%,#3A3A3A 100%)"
    _sidebar_gr= "linear-gradient(180deg,#0F0F0F 0%,#1A1A1A 50%,#222222 100%)"
    _input_bg  = "rgba(255,255,255,0.07)"
    _input_bdr = "rgba(255,255,255,0.15)"
    _tab_bg    = "#1E1E1E"
    _tab_sel   = "#333333"
    _progress  = "linear-gradient(90deg,#555555,#888888)"
    _btn_gr    = "linear-gradient(135deg,#333333,#555555)"
    
    _plot_text = "#F0F0F0"
    _plot_grid = "#333333"
else:
    _bg        = "#F5F5F5"
    _bg2       = "#EEEEEE"
    _card      = "#FFFFFF"
    _border    = "#DDDDDD"
    _text      = "#111111"
    _text_muted= "#666666"
    _primary   = "#111111"
    _accent    = "#444444"
    _shadow    = "0 4px 24px rgba(0,0,0,0.08)"
    _shadow_h  = "0 8px 40px rgba(0,0,0,0.15)"
    _header_gr = "linear-gradient(135deg,#111111 0%,#333333 60%,#555555 100%)"
    _sidebar_gr= "linear-gradient(180deg,#111111 0%,#222222 50%,#333333 100%)"
    _input_bg  = "#FFFFFF"
    _input_bdr = "#DDDDDD"
    _tab_bg    = "#FFFFFF"
    _tab_sel   = "#111111"
    _progress  = "linear-gradient(90deg,#111111,#555555)"
    _btn_gr    = "linear-gradient(135deg,#111111,#444444)"
    
    _plot_text = "#111111"
    _plot_grid = "#DDDDDD"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@400;500;600;700&display=swap');

:root {{
    --bg:         {_bg};
    --bg2:        {_bg2};
    --card:       {_card};
    --border:     {_border};
    --text:       {_text};
    --text-muted: {_text_muted};
    --primary:    {_primary};
    --accent:     {_accent};
    --shadow:     {_shadow};
    --shadow-hover:{_shadow_h};
}}

html, body, [class*="css"] {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    background-color: var(--bg) !important;
    color: var(--text) !important;
}}
.stApp {{ background: var(--bg) !important; }}

/* 마크다운 내부 텍스트 색상 전역 강제 설정 */
.stMarkdown, .stMarkdown p, .stMarkdown li, .stMarkdown span {{
    color: var(--text) !important;
}}

/* ── 헤더 ── */
.main-header {{
    background: {_header_gr};
    border-radius: 20px;
    padding: 36px 40px;
    margin-bottom: 28px;
    position: relative;
    overflow: hidden;
    box-shadow: var(--shadow-hover);
}}
.main-header::before {{
    content:'';position:absolute;top:-40px;right:-40px;
    width:220px;height:220px;
    background:rgba(255,255,255,0.07);border-radius:50%;
}}
.main-header h1 {{ color:white !important; font-size:2rem !important; font-weight:800 !important; margin:0 !important; position:relative; z-index:1; letter-spacing:-0.5px; }}
.main-header p  {{ color:rgba(255,255,255,0.82) !important; font-size:1rem !important; margin:8px 0 0 0 !important; position:relative; z-index:1; }}

/* ── 카드 ── */
.metric-card, .result-card {{
    background: var(--card) !important;
    border-radius: 16px;
    padding: 22px 24px;
    border: 1px solid var(--border);
    box-shadow: var(--shadow);
    transition: box-shadow 0.2s;
    color: var(--text);
}}
.result-card h4 {{ color: var(--text) !important; }}

/* ── 탭 ── */
.stTabs [data-baseweb="tab-list"] {{
    background: {_tab_bg} !important;
    border-radius: 14px !important;
    padding: 6px !important;
    border: 1px solid var(--border) !important;
    box-shadow: var(--shadow) !important;
}}
.stTabs [data-baseweb="tab"] {{
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    color: var(--text-muted) !important;
    padding: 10px 22px !important;
}}
.stTabs [aria-selected="true"] {{
    background: {_tab_sel} !important;
    color: {"white" if not _dark else "#F0F0F0"} !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3) !important;
}}

/* ── 인풋 ── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {{
    border-radius: 12px !important;
    border: 1.5px solid var(--border) !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 0.92rem !important;
    background: {_input_bg} !important;
    color: var(--text) !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
}}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {{
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 3px rgba(128,128,128,0.15) !important;
}}

/* ── 버튼 ── */
.stButton > button {{
    background: {_btn_gr} !important;
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    padding: 12px 28px !important;
    transition: all 0.2s !important;
    box-shadow: 0 4px 16px rgba(0,0,0,0.25) !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
}}
.stButton > button:hover {{
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 24px rgba(0,0,0,0.35) !important;
}}

/* ── 사이드바 ── */
[data-testid="stSidebar"] {{
    background: {_sidebar_gr} !important;
}}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] p, [data-testid="stSidebar"] label, [data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] {{ 
    color: white !important; 
}}
[data-testid="stSidebar"] .stTextInput > div > div > input {{
    background: rgba(255,255,255,0.1) !important;
    border: 1px solid rgba(255,255,255,0.25) !important;
    color: white !important;
    border-radius: 10px !important;
}}
[data-testid="stSidebar"] .stSelectbox > div > div {{
    background: rgba(255,255,255,0.1) !important;
    border: 1px solid rgba(255,255,255,0.25) !important;
    border-radius: 10px !important;
    color: white !important;
}}

/* ── 프로그레스 바 ── */
.stProgress > div > div > div {{
    background: {_progress} !important;
    border-radius: 8px !important;
}}

/* ── 메트릭 ── */
div[data-testid="metric-container"] {{
    background: var(--card) !important;
    border-radius: 14px !important;
    padding: 18px !important;
    border: 1px solid var(--border) !important;
    box-shadow: var(--shadow) !important;
}}
div[data-testid="metric-container"] * {{ color: var(--text) !important; }}

/* ── 사이드바 로고 ── */
.sidebar-logo {{ text-align:center; padding:20px 0 24px 0; border-bottom:1px solid rgba(255,255,255,0.15); margin-bottom:20px; }}
.sidebar-logo .logo-icon {{ font-size:2.5rem; display:block; margin-bottom:8px; }}
.sidebar-logo h2 {{ color:white !important; font-size:1.1rem !important; font-weight:800 !important; margin:0 !important; }}
.sidebar-logo p  {{ color:rgba(255,255,255,0.6) !important; font-size:0.75rem !important; margin:4px 0 0 0 !important; }}

/* ── 구분선 ── */
.custom-divider {{ border:none; height:1px; background:linear-gradient(90deg,transparent,var(--border),transparent); margin:24px 0; }}

/* ── 익스팬더 & 테이블 다크모드 대응 ── */
{"" if not _dark else """
.stExpander { background: #1E1E1E !important; border-color: #333333 !important; }
.stExpander summary { color: #E0E0E0 !important; }
.stDataFrame { background: #1E1E1E !important; }
[data-testid="stTable"] { background: #1E1E1E !important; }
"""}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 유틸리티 함수
# ─────────────────────────────────────────────
def extract_domain(url: str) -> str:
    try:
        parsed = urlparse(url if url.startswith("http") else "https://" + url)
        return parsed.netloc.replace("www.", "")
    except:
        return url

def normalize_url(url: str) -> str:
    if not url.startswith("http"):
        url = "https://" + url
    return url.rstrip("/")

# ─────────────────────────────────────────────
# 브랜드 변형 탐지
# ─────────────────────────────────────────────
def build_brand_variants(target_url: str, biz_info: dict) -> list[str]:
    domain      = extract_domain(target_url)
    brand_name  = biz_info.get("brand_name", "")
    domain_stem = domain.split(".")[0].lower()

    variants = set()
    variants.add(domain.lower())
    variants.add(domain_stem)
    for part in domain.lower().split("."):
        if len(part) > 2:
            variants.add(part)

    if brand_name:
        variants.add(brand_name.lower())
        variants.add(brand_name.replace(" ", "").lower())
        cleaned = re.sub(r'[^\w가-힣]', '', brand_name).lower()
        if cleaned:
            variants.add(cleaned)

    _en2ko = {
        "naver": "네이버", "kakao": "카카오", "coupang": "쿠팡",
        "toss": "토스", "baemin": "배민", "krafton": "크래프톤",
        "nexon": "넥슨", "ncsoft": "엔씨소프트", "netmarble": "넷마블",
        "samsung": "삼성", "lg": "엘지", "hyundai": "현대",
        "lotte": "롯데", "sk": "에스케이", "kt": "케이티",
        "woowa": "우아한형제들", "daum": "다음", "11st": "11번가",
        "musinsa": "무신사", "zigzag": "지그재그", "kurly": "마켓컬리",
        "avahair": "에이바헤어", 
    }
    for en, ko in _en2ko.items():
        if en in brand_name.lower() or en == domain_stem or en in domain.lower():
            variants.add(ko)
            variants.add(en)

    _ko2en = {v: k for k, v in _en2ko.items()}
    for ko, en in _ko2en.items():
        if ko in brand_name:
            variants.add(en)
            variants.add(ko)

    if brand_name:
        words = brand_name.split()
        if len(words) >= 2:
            abbrev = "".join(w[0] for w in words if w).lower()
            if len(abbrev) >= 2:
                variants.add(abbrev)
        first_word = words[0].lower() if words else ""
        if len(first_word) >= 2:
            variants.add(first_word)

    stem = domain_stem
    typos = set()
    if len(stem) >= 4:
        for i in range(len(stem) - 1):
            swapped = stem[:i] + stem[i+1] + stem[i] + stem[i+2:]
            typos.add(swapped)
        typos.add(stem.replace("e", "a"))
        typos.add(stem.replace("a", "e"))
        typos.add(stem.replace("o", "0"))
        typos.add(stem.replace("-", "").replace("_", ""))
    for t in list(typos)[:5]:
        if t and t != stem and len(t) >= 3:
            variants.add(t)

    for v in list(variants):
        if re.search(r'[가-힣]', v) and brand_name and re.search(r'[a-zA-Z]', brand_name):
            variants.add(brand_name.lower())
        if re.search(r'[a-zA-Z]', v) and brand_name and re.search(r'[가-힣]', brand_name):
            variants.add(brand_name)

    return [v for v in variants if v and len(v) >= 2]

# ─────────────────────────────────────────────
# 신뢰구간 계산 (Wilson Score Interval)
# ─────────────────────────────────────────────
def calc_confidence_interval(hits: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    if n == 0:
        return 0.0, 100.0
    z   = 1.96 if confidence == 0.95 else 2.576
    p   = hits / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = (z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))) / denom
    lo = max(0.0, (center - margin) * 100)
    hi = min(100.0, (center + margin) * 100)
    return round(lo, 1), round(hi, 1)

# ─────────────────────────────────────────────
# Jina Reader 기반 경쟁사 검색 컨텍스트 수집
# ─────────────────────────────────────────────
def fetch_competitor_search_context(industry: str, brand: str, market_scope: str) -> str:
    scope_kw = "한국 국내" if "국내" in market_scope else "글로벌"
    queries = [
        f"{industry} 경쟁사 {scope_kw}",
        f"{brand} 경쟁사 대안 서비스",
        f"{industry} 주요 업체 비교",
    ]
    collected = []
    headers = {"Accept": "text/markdown, text/plain, */*", "X-Return-Format": "markdown", "X-Timeout": "10"}
    for q in queries:
        try:
            search_url = f"https://r.jina.ai/https://www.google.com/search?q={requests.utils.quote(q)}&hl=ko"
            resp = requests.get(search_url, headers=headers, timeout=15)
            if resp.status_code == 200 and len(resp.text) > 300:
                snippet = resp.text[:3000]
                collected.append(f"[검색: {q}]\n{snippet}")
        except Exception:
            continue
    return "\n\n".join(collected)[:8000]

# ─────────────────────────────────────────────
# AI 업종 분석 기반 경쟁사 도출 
# ─────────────────────────────────────────────
def discover_competitors(client_gpt, client_gemini, biz_info: dict, target_url: str,
                          market_scope: str, model_gpt: str, n_competitors: int = 5,
                          confirmed_industry: str = "") -> list[dict]:
    brand    = biz_info.get("brand_name", extract_domain(target_url))
    industry = confirmed_industry.strip() if confirmed_industry.strip() else biz_info.get("industry", "디지털 서비스")
    product  = biz_info.get("core_product", "서비스")
    audience = biz_info.get("target_audience", "일반 사용자")
    domain   = extract_domain(target_url)

    scope_instruction = (
        "반드시 대한민국에서 서비스 중인 국내 기업만 포함하세요. 해외 기업은 제외합니다."
        if "국내" in market_scope
        else "전 세계 글로벌 시장에서 활동하는 기업을 포함하세요. 국내외 무관하게 선정합니다."
    )

    search_context = fetch_competitor_search_context(industry, brand, market_scope)
    search_context_section = f"""
[실제 검색 데이터 — 이 데이터를 최우선 근거로 활용하세요]
{search_context if search_context else "(검색 결과 없음 — AI 자체 지식으로 판단)"}
""" if search_context else "[검색 데이터: 없음 — AI 자체 지식으로 판단]"

    prompt = f"""당신은 디지털 마케팅 업계 전문 애널리스트입니다.
아래 검색 데이터와 브랜드 정보를 바탕으로 실제 직접 경쟁사를 도출하고, 각 항목을 논리적으로 검증하세요.

[분석 대상]
- 브랜드명: {brand}
- 도메인: {domain}
- 업종: {industry}
- 핵심 서비스: {product}

{search_context_section}

[경쟁사 도출 기준]
1. 위 검색 데이터에 실제로 등장하는 브랜드를 최우선 선정
2. {brand} 고객이 이탈할 경우 선택할 가능성이 가장 높은 서비스 우선
3. {scope_instruction}

[출력 형식 — JSON 배열만]
[
  {{
    "rank": 1,
    "brand_name": "브랜드명",
    "domain": "실제도메인.com",
    "reason": "경쟁 이유 25자 이내",
    "domain_valid": true,
    "is_direct_competitor": true
  }},
  ...
]
검증을 통과한 경쟁사 {n_competitors}개를 rank 순으로 출력하세요."""

    result_str = ""
    try:
        if client_gpt:
            result_str = call_gpt(client_gpt, prompt, max_tokens=1200, model=model_gpt, temperature_override=0.2)
        elif client_gemini:
            result_str = call_gemini(client_gemini, prompt, max_tokens=1200, temperature_override=0.2)
    except Exception:
        pass

    competitors = []
    try:
        json_match = re.search(r'\[.*\]', result_str, re.DOTALL)
        if json_match:
            raw = json.loads(json_match.group())
            competitors = [
                c for c in raw
                if c.get("domain_valid", True) and c.get("is_direct_competitor", True)
                and c.get("domain", "").strip() and "competitor" not in c.get("domain", "").lower()
            ]
    except Exception:
        pass

    if not competitors:
        competitors = [
            {"rank": i+1, "brand_name": f"경쟁사 {i+1}", "domain": f"competitor{i+1}.com",
             "reason": "동종 업계 경쟁사", "domain_valid": False, "is_direct_competitor": False}
            for i in range(n_competitors)
        ]
    return competitors[:n_competitors]

# ─────────────────────────────────────────────
# 심층 사이트 크롤링 — 비즈니스 실체 추출
# ─────────────────────────────────────────────
class _MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title, self.description, self.og_title, self.og_description = "", "", "", ""
        self._in_title = False
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "title": self._in_title = True
        if tag == "meta":
            name = attrs_dict.get("name", "").lower()
            prop = attrs_dict.get("property", "").lower()
            content = attrs_dict.get("content", "")
            if name == "description": self.description = content
            elif prop == "og:title": self.og_title = content
            elif prop == "og:description": self.og_description = content
    def handle_endtag(self, tag):
        if tag == "title": self._in_title = False
    def handle_data(self, data):
        if self._in_title and not self.title: self.title = data.strip()

def crawl_site_metadata(url: str) -> dict:
    try:
        resp = requests.get(f"https://r.jina.ai/{url}", headers={"Accept": "text/markdown", "X-Timeout": "15"}, timeout=20)
        if resp.status_code == 200 and len(resp.text) > 200:
            lines = resp.text.strip().splitlines()
            title = next((line.lstrip("#").strip() for line in lines if line.strip().startswith("#")), lines[0][:100] if lines else "")
            description = " ".join([line.strip() for line in lines if line.strip() and not line.strip().startswith("#")][:5])
            return {"title": title, "description": description[:500], "html_snippet": resp.text[:6000], "crawl_ok": True}
    except Exception:
        pass

    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10, allow_redirects=True)
        resp.encoding = resp.apparent_encoding or "utf-8"
        html = resp.text[:80_000]
        if len(html) > 500 and "자동등록방지" not in html:
            parser = _MetaParser()
            parser.feed(html)
            return {
                "title": parser.og_title or parser.title or "",
                "description": parser.og_description or parser.description or "",
                "html_snippet": html[:4000], "crawl_ok": True
            }
    except Exception:
        pass
    return {"title": "", "description": "", "html_snippet": "", "crawl_ok": False}

def analyze_business_identity(client_gpt, client_gemini, url: str, model_gpt: str, model_gemini) -> dict:
    meta        = crawl_site_metadata(url)
    domain      = extract_domain(url)
    domain_stem = domain.split(".")[0]

    prompt = f"""당신은 비즈니스 인텔리전스 전문가입니다.
아래 웹사이트 정보를 바탕으로 업종과 서비스를 정확하게 분석하세요.

[도메인]: {domain}
[크롤링]: {meta.get('title', '(없음)')} / {meta.get('description', '(없음)')}

[중요 지침 - 반드시 지킬 것]
- 만약 크롤링된 본문에 글자가 거의 없고 정보가 부족하다면(예: 이미지 위주의 프랜차이즈 사이트), 오직 도메인명({domain})과 당신의 사전 지식을 총동원하여 이 브랜드가 현실에서 어떤 비즈니스를 하는 유명한 업체인지 추론하세요.
  (예시: avahair.co.kr 이면 "에이바헤어", "미용실 프랜차이즈, 헤어살롱" 으로 파악해야 합니다.)
- 업종(industry)은 "{domain_stem} 관련 서비스" 같은 모호한 단어를 절대 쓰지 말고, 실물 비즈니스명으로 적으세요.
- brand_name은 도메인이 아닌 실제 한글 회사명/브랜드명을 우선으로 적으세요.

다른 텍스트나 설명 없이 순수한 JSON 형식으로만 출력하세요:
{{
  "brand_name": "실제 브랜드명 또는 회사명",
  "industry": "구체적 업종 (예: 미용실 프랜차이즈, 광고대행사)",
  "industry_category": "대분류",
  "core_product": "핵심 서비스/상품 한 문장",
  "target_audience": "주요 타겟 고객층",
  "key_services": ["서비스1", "서비스2"]
}}"""

    result_str = ""
    try:
        if client_gpt:
            result_str = call_gpt(client_gpt, prompt, max_tokens=600, model=model_gpt, temperature_override=0.2)
        elif client_gemini:
            result_str = call_gemini(client_gemini, prompt, max_tokens=600, temperature_override=0.2)
        
        json_match = re.search(r'\{.*\}', result_str, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception:
        pass

    return {
        "brand_name": domain_stem.upper(),
        "industry": "브랜드 서비스",
        "industry_category": "기타",
        "core_product": "핵심 서비스",
        "target_audience": "잠재 고객층",
        "key_services": [],
    }

# ─────────────────────────────────────────────
# API 호출 기본 함수
# ─────────────────────────────────────────────
def call_gpt(client, prompt: str, system: str = "", model: str = "gpt-4o-mini", max_tokens: int = 1500, temperature_override: float = 0.7) -> str:
    messages = [{"role": "system", "content": system}] if system else []
    messages.append({"role": "user", "content": prompt})
    res = client.chat.completions.create(model=model, messages=messages, max_tokens=max_tokens, temperature=temperature_override)
    return res.choices[0].message.content.strip()

def call_gemini(model_obj, prompt: str, max_tokens: int = 1500, temperature_override: float = 0.7) -> str:
    res = model_obj.generate_content(prompt, generation_config=genai.types.GenerationConfig(max_output_tokens=max_tokens, temperature=temperature_override))
    return res.text.strip()

# ─────────────────────────────────────────────
# AI 타겟 질문 생성 — 비즈니스 전환형 (심층 분석 기반)
# ─────────────────────────────────────────────
def generate_target_questions(client_gpt, client_gemini, url: str, engine: str,
                               model_gpt: str, model_gemini,
                               biz_info: dict = None, manual_brand: str = "") -> list[str]:
    brand    = manual_brand.strip() if manual_brand.strip() else biz_info.get("brand_name", extract_domain(url))
    industry = biz_info.get("industry", "서비스")
    product  = biz_info.get("core_product", "서비스")
    audience = biz_info.get("target_audience", "잠재 고객")

    prompt = f"""당신은 {industry} 분야의 10년 경력 마케팅 전략가입니다.

[분석 대상 브랜드]
- 브랜드명: {brand}
- 업종: {industry}
- 핵심 서비스: {product}
- 주요 타겟: {audience}

[생성 지침 - 템플릿 사용 절대 금지]
- 뻔한 양식("~차별점은 무엇인가요?", "~장단점은?")을 절대 쓰지 마세요.
- 위에서 분석된 **업종 맥락({industry})과 핵심 서비스({product})를 100% 반영**하여, 실제 고객이 지식인이나 AI에게 물어볼 법한 **구체적이고 현실적인 타겟 질문 5개**를 창의적으로 도출하세요.
- 예시 1 (미용실 프랜차이즈): "{brand}에서 손상모 복구펌을 하려고 하는데, 기장 추가 비용이나 실제 유지 기간이 어떻게 되나요?"
- 예시 2 (광고대행사): "{brand}에 메타 퍼포먼스 광고를 맡겼을 때 대행 수수료율과 최소 집행 예산 기준이 어떻게 되나요?"
- 질문 안에 한글 브랜드명 '{brand}'를 자연스럽게 넣으세요.

다른 설명이나 기호 없이 **오직 질문 5개만 한 줄씩 출력**하세요. 반드시 물음표(?)로 끝나야 합니다.
"""
    result = ""
    try:
        if engine == "GPT" and client_gpt:
            result = call_gpt(client_gpt, prompt, max_tokens=1000, model=model_gpt, temperature_override=0.8)
        elif engine == "Gemini" and client_gemini:
            result = call_gemini(client_gemini, prompt, max_tokens=1000, temperature_override=0.8)
        elif client_gpt:
            result = call_gpt(client_gpt, prompt, max_tokens=1000, model=model_gpt, temperature_override=0.8)
        elif client_gemini:
            result = call_gemini(client_gemini, prompt, max_tokens=1000, temperature_override=0.8)
    except Exception:
        pass

    lines = [ln.strip() for ln in result.split("\n") if ln.strip()]
    questions = [re.sub(r'^[\d\.\-\*\[\]\s]+', '', q).strip() for q in lines if '?' in q]
    questions = [q for q in questions if len(q) > 5][:5]

    if not questions:
        questions = [
            f"{brand}의 {industry} 관련 주요 서비스와 특징은 무엇인가요?",
            f"고객들이 {brand}를 선택하는 핵심 이유는 무엇인가요?",
            f"{brand} 이용 시 예상되는 비용이나 수수료 구조는 어떤가요?"
        ]
    return questions[:5]


# ─────────────────────────────────────────────
# 시뮬레이션 엔진 (병렬 처리 고도화)
# ─────────────────────────────────────────────
def simulate_single_gpt(client, question: str, target_url: str, model: str, brand_variants: list[str]) -> dict:
    try:
        res = call_gpt(client, f"질문: {question}\n\n답변:", max_tokens=150, model=model, temperature_override=0.5)
        cited = any(v.lower() in res.lower() for v in brand_variants)
        return {"cited": cited, "response_sample": res[:200] if cited else ""}
    except Exception:
        return {"cited": False, "response_sample": ""}

def simulate_single_gemini(model_obj, question: str, target_url: str, brand_variants: list[str]) -> dict:
    try:
        res = call_gemini(model_obj, f"질문: {question}\n\n답변:", max_tokens=150, temperature_override=0.5)
        cited = any(v.lower() in res.lower() for v in brand_variants)
        return {"cited": cited, "response_sample": res[:200] if cited else ""}
    except Exception:
        return {"cited": False, "response_sample": ""}

def run_simulation(client_gpt, client_gemini, question: str, target_url: str,
                   model_gpt: str, model_gemini, n: int = 50, biz_info: dict = None, progress_callback=None) -> dict:
    bv = build_brand_variants(target_url, biz_info or {})
    gpt_h, gem_h, gpt_r, gem_r = 0, 0, False, False
    g_samp, m_samp = [], []

    def _gpt_batch():
        h, s = 0, []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
            futs = [ex.submit(simulate_single_gpt, client_gpt, question, target_url, model_gpt, bv) for _ in range(n)]
            for f in concurrent.futures.as_completed(futs):
                try:
                    r = f.result(timeout=15)
                    if r["cited"]:
                        h += 1
                        if len(s) < 2 and r["response_sample"]: s.append(r["response_sample"])
                except Exception: pass
        return h, s

    def _gem_batch():
        h, s = 0, []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
            futs = [ex.submit(simulate_single_gemini, client_gemini, question, target_url, bv) for _ in range(n)]
            for f in concurrent.futures.as_completed(futs):
                try:
                    r = f.result(timeout=15)
                    if r["cited"]:
                        h += 1
                        if len(s) < 2 and r["response_sample"]: s.append(r["response_sample"])
                except Exception: pass
        return h, s

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f_gpt = executor.submit(_gpt_batch) if client_gpt else None
        f_gem = executor.submit(_gem_batch) if client_gemini else None
        
        if progress_callback: progress_callback(0.5)
        
        if f_gpt:
            try: gpt_h, g_samp = f_gpt.result(timeout=max(120, n*3)); gpt_r = True
            except Exception: pass
        if f_gem:
            try: gem_h, m_samp = f_gem.result(timeout=max(120, n*3)); gem_r = True
            except Exception: pass

    if progress_callback: progress_callback(1.0)

    gpt_rate = round(gpt_h/n*100, 1) if gpt_r else None
    gem_rate = round(gem_h/n*100, 1) if gem_r else None
    valid = [v for v in [gpt_rate, gem_rate] if v is not None]

    return {
        "gpt_rate": gpt_rate, "gemini_rate": gem_rate,
        "avg_rate": round(sum(valid)/len(valid), 1) if valid else 0,
        "gpt_hits": gpt_h, "gemini_hits": gem_h, "total": n,
        "gpt_ci": calc_confidence_interval(gpt_h, n) if gpt_r else (None, None),
        "gemini_ci": calc_confidence_interval(gem_h, n) if gem_r else (None, None),
        "gpt_samples": g_samp, "gemini_samples": m_samp
    }

def run_all_simulations(client_gpt, client_gemini, questions: list[str], target_url: str,
                         model_gpt: str, model_gemini, n: int = 50, biz_info: dict = None) -> list[dict]:
    results = [None] * len(questions)
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(questions), 5)) as executor:
        fmap = {executor.submit(run_simulation, client_gpt, client_gemini, q, target_url, model_gpt, model_gemini, n, biz_info): i for i, q in enumerate(questions)}
        for f in concurrent.futures.as_completed(fmap):
            try:
                results[fmap[f]] = f.result(timeout=max(120, n * 3))
            except Exception:
                results[fmap[f]] = {"gpt_rate": None, "gemini_rate": None, "avg_rate": 0, "gpt_hits": 0, "gemini_hits": 0, "total": n, "gpt_ci": (None, None), "gemini_ci": (None, None), "gpt_samples": [], "gemini_samples": []}
    return results

def run_sov_simulation(client_gpt, client_gemini, question: str, target_url: str,
                        competitor_list: list[dict], biz_info: dict, model_gpt: str, n: int = 30) -> dict:
    all_urls = [target_url] + [normalize_url(c.get("domain", "")) for c in competitor_list if c.get("domain", "").strip()]
    all_labels = [biz_info.get("brand_name", extract_domain(target_url))] + [c.get("brand_name", c.get("domain", "")) for c in competitor_list]

    sov_results = []
    for i, (url, label) in enumerate(zip(all_urls, all_labels)):
        brand_biz = biz_info if i == 0 else {"brand_name": label, "industry": biz_info.get("industry", "")}
        res = run_simulation(client_gpt, client_gemini, question, url, model_gpt, None, n, brand_biz)
        res["label"] = label
        res["domain"] = extract_domain(url)
        res["is_target"] = (i == 0)
        sov_results.append(res)

    return sov_results


def run_strategy_analysis(client_gpt, client_gemini, question: str, target_url: str,
                           model_gpt: str, model_gemini, biz_info: dict = None, market_scope: str = "글로벌") -> dict:
    domain, brand, industry = extract_domain(target_url), (biz_info or {}).get("brand_name", extract_domain(target_url)), (biz_info or {}).get("industry", "서비스")
    scope_instruction = "대한민국에서 서비스하는 국내 기업만 포함하세요." if "국내" in market_scope else "국내외 글로벌 기업을 모두 포함하세요."

    sys_msg = "완성된 문장으로 마침표(.)로 끝맺으세요."
    p_comp = f"질문: '{question}' 에 AI가 인용할 상위 10개 경쟁사 도메인 배열로 출력. {scope_instruction}\n형식: [{{\"rank\": 1, \"domain\": \"a.com\", \"brand_name\": \"A사\", \"reason\": \"이유\", \"position\": \"업계1위\"}}]"
    p_diag = f"[{brand}]이 질문 '{question}'에서 AI 인용 점유율이 낮은 이유를 분석하세요. 경쟁사 대비 콘텐츠·구조 문제점 3가지 (항목당 한 줄)"
    p_kw = f"[{brand}]({industry}) 사이트에서 AI 인용 확률이 높을 블루오션 틈새 질문/키워드 5개 추천 (한 줄에 하나)"
    p_geo = f"[{domain}]이 질문 '{question}'에서 AI에게 잘 인용되도록 홈페이지 개선 방안 3가지 (번호 포함, 2줄 이내)"

    def _call(p):
        try:
            if client_gpt: return call_gpt(client_gpt, p, system=sys_msg, model=model_gpt)
            if client_gemini: return call_gemini(client_gemini, p)
        except Exception: pass
        return ""

    comp_res = _call(p_comp)
    competitors = []
    try:
        m = re.search(r'\[.*\]', comp_res, re.DOTALL)
        if m: competitors = json.loads(m.group())
    except Exception: pass

    return {
        "competitors": competitors,
        "diagnoses": [d.strip().lstrip("•-*") for d in _call(p_diag).split("\n") if d.strip()][:3],
        "keywords": [k.strip().lstrip("•-*1234567890. ") for k in _call(p_kw).split("\n") if k.strip()][:5],
        "geo_guides": [g.strip() for g in re.split(r'\n(?=\d+\.)', _call(p_geo)) if g.strip()][:3],
    }

# ─────────────────────────────────────────────
# 렌더링 UI (다크/라이트 모드 대응 CSS 변수 사용)
# ─────────────────────────────────────────────
def render_bar_chart(results: list[dict], questions: list[str], title: str):
    if not results: return
    short_questions = [q[:18] + "…" if len(q) > 20 else q for q in questions]

    fig = go.Figure()
    if any(r.get("gpt_rate") is not None for r in results):
        y_vals = [r.get("gpt_rate") or 0 for r in results]
        fig.add_trace(go.Bar(name="GPT", x=short_questions, y=y_vals, marker=dict(color="#111111", line=dict(color="#000000", width=1)), text=[f"{v}%" if v else "" for v in y_vals], textposition="outside", textfont=dict(size=11, color=_plot_text, family="Plus Jakarta Sans")))
    if any(r.get("gemini_rate") is not None for r in results):
        y_vals = [r.get("gemini_rate") or 0 for r in results]
        fig.add_trace(go.Bar(name="Gemini", x=short_questions, y=y_vals, marker=dict(color="#888888", line=dict(color="#666666", width=1)), text=[f"{v}%" if v else "" for v in y_vals], textposition="outside", textfont=dict(size=11, color=_plot_text, family="Plus Jakarta Sans")))

    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color=_plot_text, family="Plus Jakarta Sans"), x=0),
        barmode="group", bargap=0.25, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Plus Jakarta Sans", color=_plot_text),
        xaxis=dict(tickfont=dict(size=11), gridcolor=_plot_grid, title=""),
        yaxis=dict(title="인용 점유율 (%)", ticksuffix="%", gridcolor=_plot_grid),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor="rgba(0,0,0,0)"),
        margin=dict(t=60, b=40, l=50, r=20), height=380,
    )
    st.plotly_chart(fig, use_container_width=True)

def render_sov_chart(sov_results: list[dict], title: str):
    if not sov_results: return
    labels = [r["label"] for r in sov_results]
    avgs = [r.get("avg_rate", 0) for r in sov_results]
    colors = ["#111111" if r.get("is_target") else "#AAAAAA" for r in sov_results]

    fig = go.Figure(go.Bar(x=avgs, y=labels, orientation="h", marker_color=colors, text=[f"{v:.1f}%" for v in avgs], textposition="outside", textfont=dict(size=12, color=_plot_text)))
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color=_plot_text), x=0),
        xaxis=dict(title="평균 AI 인용률 (%)", ticksuffix="%", gridcolor=_plot_grid),
        yaxis=dict(autorange="reversed", tickfont=dict(size=12)),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Plus Jakarta Sans", color=_plot_text),
        margin=dict(t=55, b=40, l=120, r=60), height=max(300, len(sov_results) * 55 + 100),
    )
    st.plotly_chart(fig, use_container_width=True)

    rows = [{"브랜드": ("⭐ " if r["is_target"] else "") + r["label"], "도메인": r.get("domain", ""), "GPT 점유율": f"{r['gpt_rate']}%" if r.get("gpt_rate") is not None else "—", "Gemini 점유율": f"{r['gem_rate']}%" if r.get("gem_rate") is not None else "—", "평균 점유율": f"{r.get('avg_rate', 0):.1f}%"} for r in sov_results]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

def render_strategy_analysis(strategy: dict, target_url: str):
    domain = extract_domain(target_url)

    st.markdown("""
    <div style="background:var(--bg2);border:1px solid var(--border);
    border-radius:14px;padding:16px 20px;margin:16px 0;">
    <span style="font-size:1rem;font-weight:700;color:var(--text);">📊 전략 분석 — 경쟁사 현황 및 GEO 최적화 가이드</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 🏆 AI 인용 경쟁 현황 (TOP 10)")
    if competitors := strategy.get("competitors", []):
        for comp in competitors[:10]:
            is_tgt = domain.lower() in comp.get("domain", "").lower()
            bg = "var(--bg2)" if is_tgt else "var(--card)"
            bdr = "var(--primary)" if is_tgt else "var(--border)"
            st.markdown(f"""
            <div style="display:flex;align-items:center;justify-content:space-between;
            padding:11px 16px;border-radius:10px;margin:5px 0; background:{bg};border:1.5px solid {bdr};">
                <span style="font-weight:{'700' if is_tgt else '500'};color:var(--text);font-size:0.9rem;">
                {comp.get('brand_name', comp.get('domain',''))} 
                <span style="color:var(--text-muted);font-size:0.78rem;">({comp.get('domain','')}) {' ← 내 사이트' if is_tgt else ''}</span></span>
                <span style="color:var(--text-muted);font-size:0.8rem;">{comp.get('reason','')}</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("경쟁사 데이터를 불러오지 못했습니다.")

    st.markdown("<hr class='custom-divider'>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🔬 인용 실패 원인 진단")
        for diag in strategy.get("diagnoses", []):
            st.markdown(f"""<div style="background:var(--card);border-radius:12px;padding:14px 16px;margin:8px 0;
            border-left:4px solid var(--text);border:1px solid var(--border);box-shadow:var(--shadow);">
                <span style="font-size:0.85rem;color:var(--text);">❌ {diag}</span>
            </div>""", unsafe_allow_html=True)
    with col2:
        st.markdown("### 🌊 블루오션 키워드 추천")
        for kw in strategy.get("keywords", []):
            st.markdown(f"""<div style="background:var(--bg2);border-radius:12px;padding:12px 16px;margin:8px 0;
            border:1px solid var(--border);display:flex;align-items:center;gap:10px;">
                <span style="background:var(--primary);color:white;padding:3px 10px;border-radius:20px;font-size:0.75rem;font-weight:700;">NEW</span>
                <span style="font-size:0.88rem;color:var(--text);font-weight:600;">{kw}</span>
            </div>""", unsafe_allow_html=True)

    st.markdown("<hr class='custom-divider'>", unsafe_allow_html=True)
    st.markdown("### 📋 GEO 최적화 가이드")
    for i, guide in enumerate(strategy.get("geo_guides", [])):
        st.markdown(f"""<div style="background:var(--card);border-radius:14px;padding:18px 20px;margin:10px 0;
        border:1px solid var(--border);box-shadow:var(--shadow);"><div style="display:flex;gap:12px;align-items:flex-start;">
            <div style="min-width:30px;height:30px;border-radius:8px;background:var(--primary);color:white;font-weight:800;font-size:0.85rem;display:flex;align-items:center;justify-content:center;">{i + 1}</div>
            <p style="margin:0;font-size:0.88rem;color:var(--text);line-height:1.6;">{guide}</p>
        </div></div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 사이드바
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div class="sidebar-logo">
        <span class="logo-icon">🔍</span>
        <h2>AI Citation Analyzer</h2>
        <p>AI 검색 점유율 분석 도구</p>
    </div>
    """, unsafe_allow_html=True)

    _mode_label = "☀️ 라이트 모드로 전환" if _dark else "🌙 다크 모드로 전환"
    if st.button(_mode_label, key="btn_darkmode", use_container_width=True):
        st.session_state["dark_mode"] = not st.session_state["dark_mode"]
        try:
            st.rerun()
        except AttributeError:
            st.experimental_rerun()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    openai_key  = st.text_input("OpenAI API Key", type="password", placeholder="sk-...",   key="openai_key")
    gemini_key  = st.text_input("Gemini API Key", type="password", placeholder="AIza...", key="gemini_key")

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.markdown("**🤖 모델 선택**")
    gpt_model = st.selectbox("GPT 모델", ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"], index=0)
    gemini_model_name = st.selectbox("Gemini 모델", ["models/gemini-2.0-flash", "models/gemini-flash-latest", "models/gemini-3-flash-preview"], index=0)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.markdown("**⚙️ 시뮬레이션 설정**")
    sim_count = st.slider("시뮬레이션 횟수", min_value=10, max_value=100, value=50, step=10)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    st.markdown("**🌐 경쟁사 분석 설정**")
    market_scope = st.radio("경쟁사 범위", ["국내 (대한민국)", "글로벌"], index=0, horizontal=True)
    n_competitors = st.slider("경쟁사 수", min_value=3, max_value=10, value=5, step=1)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown("**📡 연결 상태**")
    gpt_ok    = bool(openai_key and openai_key.startswith("sk-"))
    gemini_ok = bool(gemini_key and len(gemini_key) > 10)

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        if gpt_ok: st.markdown("🟢 **GPT** 연결됨")
        else: st.markdown("⚪ **GPT** 미입력")
    with col_s2:
        if gemini_ok: st.markdown("🟢 **Gemini** 연결됨")
        else: st.markdown("🔴 **Gemini** 미연결")

    if st.button("▶ 데모 시뮬레이션 실행", key="btn_demo_sidebar", use_container_width=True):
        st.session_state["run_demo"] = True

def get_clients():
    cgpt, cgem = None, None
    if gpt_ok:
        try: cgpt = openai.OpenAI(api_key=openai_key)
        except Exception: pass
    if gemini_ok:
        try:
            genai.configure(api_key=gemini_key)
            cgem = genai.GenerativeModel(gemini_model_name)
        except Exception: pass
    return cgpt, cgem

# ─────────────────────────────────────────────
# 메인 화면
# ─────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>🔍 AI 검색 점유율 분석 대시보드</h1>
    <p>GPT & Gemini AI 엔진에서 내 사이트가 얼마나 인용되는지 측정하고 최적화 전략을 도출합니다</p>
</div>
""", unsafe_allow_html=True)

col_m1, col_m2, col_m3, col_m4 = st.columns(4)
with col_m1: st.metric("분석 엔진", "GPT + Gemini", "2개 동시 비교")
with col_m2: st.metric("시뮬레이션", f"{sim_count}회/질문", "통계적 외삽")
with col_m3: st.metric("API 연결", f"{(1 if gpt_ok else 0) + (1 if gemini_ok else 0)}/2", "엔진 활성화")
with col_m4: st.metric("데모 모드", "ON" if st.session_state.get("run_demo", False) else "OFF", "사이드바에서 실행")

st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
tab1, tab2, tab3 = st.tabs(["🤖 자동 분석형 (AI 질문 도출)", "✏️ 수동 분석형 (키워드 직접 입력)", "📅 AI 인용 히스토리"])

client_gpt, client_gemini = get_clients()

# ─────────────────────────────────────────────
# Tab 1: 자동 분석형
# ─────────────────────────────────────────────
with tab1:
    st.markdown("""
    <div class="result-card" style="background:var(--bg2);border-color:var(--border);">
        <h4 style="color:var(--text);margin-bottom:6px;">🤖 AI 타겟 질문 자동 도출 방식</h4>
        <p style="color:var(--text-muted);font-size:0.88rem;margin:0;line-height:1.6;">
        사이트 URL을 입력하면 AI가 해당 사이트가 인용될 가능성이 가장 높은 질문 5개를 스스로 생성하고,<br>
        각 질문에 대해 <b>설정한 횟수</b>만큼 실제 시뮬레이션을 수행하여 인용 점유율을 산출합니다.
        </p>
    </div>
    """, unsafe_allow_html=True)

    col_url, col_brand = st.columns([2, 1])
    with col_url:
        url_auto = st.text_input("🌐 분석할 사이트 URL", placeholder="예) https://www.naver.com 또는 naver.com", key="url_auto")
    with col_brand:
        if "industry_display" not in st.session_state: st.session_state["industry_display"] = ""
        manual_industry_input = st.text_input("🏭 업종 확인·수정 (AI 자동 분석 → 직접 수정 가능)", value=st.session_state["industry_display"], key="industry_widget")
        st.session_state["industry_display"] = manual_industry_input

    col_pre, col_btn1, col_btn2 = st.columns([1, 2, 1])
    with col_pre: pre_analyze_clicked = st.button("🔍 업종 미리 분석", use_container_width=True)
    with col_btn1: run_real_auto = st.button("🚀 자동 분석 시작", use_container_width=True)
    with col_btn2: run_demo_auto = st.button("🎬 데모 실행", use_container_width=True)

    question_engine = st.radio("질문 도출 엔진", ["GPT", "Gemini"], horizontal=True)

    if pre_analyze_clicked:
        if not url_auto.strip(): st.warning("URL을 먼저 입력해주세요.")
        else:
            with st.spinner("업종 분석 중..."):
                _pre_biz = analyze_business_identity(client_gpt, client_gemini, normalize_url(url_auto), gpt_model, client_gemini)
                st.session_state["industry_display"] = _pre_biz.get("industry", "")
                st.session_state["ai_analyzed_biz_info"] = _pre_biz
                try: st.rerun()
                except AttributeError: st.experimental_rerun()

    trigger_demo = run_demo_auto or st.session_state.pop("run_demo", False)
    if trigger_demo:
        demo_url = normalize_url(url_auto.strip() if url_auto.strip() else "naver.com")
        demo_data = get_demo_data(demo_url)
        st.success("✅ 데모 시뮬레이션 완료!")
        render_bar_chart(demo_data["scenario"]["results"], demo_data["scenario"]["questions"], "[데모] 질문별 AI 인용 점유율")
        for q, r in zip(demo_data["scenario"]["questions"][:2], demo_data["scenario"]["results"][:2]):
            with st.expander(f"Q. {q}"):
                render_strategy_analysis(demo_data["strategy"], demo_url)

    elif run_real_auto and not pre_analyze_clicked:
        if not url_auto or (not gpt_ok and not gemini_ok):
            st.error("URL과 API 키를 확인해주세요.")
        else:
            target_url = normalize_url(url_auto)
            biz_info = st.session_state.get("ai_analyzed_biz_info", {})
            if not biz_info:
                with st.spinner("비즈니스 실체 분석 중..."):
                    biz_info = analyze_business_identity(client_gpt, client_gemini, target_url, gpt_model, client_gemini)
            if st.session_state.get("industry_display"):
                biz_info["industry"] = st.session_state["industry_display"]

            with st.spinner("타겟 질문 도출 중..."):
                questions = generate_target_questions(client_gpt, client_gemini, target_url, question_engine, gpt_model, client_gemini, biz_info=biz_info)
            
            st.markdown("**📋 생성된 타겟 질문:**")
            for i, q in enumerate(questions, 1):
                st.markdown(f"""<div style="background:var(--card);border-radius:10px;padding:11px 16px;margin:5px 0;border:1px solid var(--border);"><span style="background:var(--primary);color:white;padding:2px 8px;border-radius:8px;">{i}</span> <span style="color:var(--text);">{q}</span></div>""", unsafe_allow_html=True)

            with st.spinner(f"병렬 동시 시뮬레이션 진행 중... ({sim_count}회)"):
                all_results = run_all_simulations(client_gpt, client_gemini, questions, target_url, gpt_model, client_gemini, n=sim_count, biz_info=biz_info)
            
            render_bar_chart(all_results, questions, f"'{biz_info.get('brand_name', '')}' 질문별 AI 인용 점유율")

            for i, (q, r) in enumerate(zip(questions, all_results)):
                with st.expander(f"Q{i+1}. {q}"):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("GPT 점유율", f"{r['gpt_rate']}%" if r.get('gpt_rate') is not None else "—")
                    c2.metric("Gemini 점유율", f"{r['gemini_rate']}%" if r.get('gemini_rate') is not None else "—")
                    c3.metric("평균 점유율", f"{r.get('avg_rate', 0)}%")
                    
                    if r.get("gpt_samples") or r.get("gemini_samples"):
                        st.markdown("**💬 AI 인용 응답 샘플**")
                        for s in r.get("gpt_samples", [])[:1]: st.info(f"**GPT:** {s}")
                        for s in r.get("gemini_samples", [])[:1]: st.info(f"**Gemini:** {s}")

                    with st.spinner("전략 분석 중..."):
                        strat = run_strategy_analysis(client_gpt, client_gemini, q, target_url, gpt_model, client_gemini, biz_info=biz_info, market_scope=market_scope)
                        render_strategy_analysis(strat, target_url)

# ─────────────────────────────────────────────
# Tab 2: 수동 분석형
# ─────────────────────────────────────────────
with tab2:
    st.markdown("""
    <div class="result-card" style="background:var(--bg2);border-color:var(--border);">
        <h4 style="color:var(--text);margin-bottom:6px;">✏️ 직접 키워드/질문 입력 방식</h4>
        <p style="color:var(--text-muted);font-size:0.88rem;margin:0;line-height:1.6;">
        분석하고 싶은 키워드나 질문을 직접 입력하고 제출하면 양 엔진에서 동시 시뮬레이션을 수행합니다.
        </p>
    </div>
    """, unsafe_allow_html=True)

    c_m1, c_m2 = st.columns(2)
    url_manual = c_m1.text_input("🌐 사이트 URL", key="url_manual")
    kw_manual = c_m2.text_input("🔍 메인 키워드 / 질문", key="kw_manual")
    
    if st.button("🔬 수동 분석 시작", use_container_width=True):
        if url_manual and kw_manual and (gpt_ok or gemini_ok):
            t_url = normalize_url(url_manual)
            with st.spinner("비즈니스 분석 및 시뮬레이션 중..."):
                biz = analyze_business_identity(client_gpt, client_gemini, t_url, gpt_model, client_gemini)
                comps = discover_competitors(client_gpt, client_gemini, biz, t_url, market_scope, gpt_model, n_competitors)
                res = run_simulation(client_gpt, client_gemini, kw_manual, t_url, gpt_model, client_gemini, sim_count, biz)
            
            render_bar_chart([res], [kw_manual], f"'{kw_manual}' 인용 점유율")
            
            with st.spinner("경쟁사 SOV 분석 중..."):
                sov = run_sov_simulation(client_gpt, client_gemini, kw_manual, t_url, comps, biz, gpt_model, max(10, sim_count//3))
                render_sov_chart(sov, f"[{market_scope}] 경쟁사 대비 SOV")
            
            with st.spinner("전략 분석 중..."):
                strat = run_strategy_analysis(client_gpt, client_gemini, kw_manual, t_url, gpt_model, client_gemini, biz, market_scope)
                render_strategy_analysis(strat, t_url)
        else:
            st.error("입력값과 API 키를 확인해주세요.")

# ─────────────────────────────────────────────
# Tab 3: AI 인용 히스토리
# ─────────────────────────────────────────────
with tab3:
    st.info("로그 파일을 업로드하여 AI 엔진별 브랜드 누적 인용 횟수를 시각화합니다.")

# ─────────────────────────────────────────────
# 푸터
# ─────────────────────────────────────────────
st.markdown("<div style='height:40px'></div>", unsafe_allow_html=True)
st.markdown("""
<div style="text-align:center;padding:20px;color:var(--text-muted);font-size:0.8rem;border-top:1px solid var(--border);">
    🔍 AI Citation Analyzer &nbsp;|&nbsp; GPT & Gemini 기반 AI 검색 점유율 분석 도구
</div>
""", unsafe_allow_html=True)
