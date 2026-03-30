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
# 글로벌 CSS — 다크/라이트 모드 통합
# ─────────────────────────────────────────────
if _dark:
    _bg        = "#0F0F0F"
    _bg2       = "#1A1A1A"
    _card      = "#1E1E1E"
    _border    = "#333333"
    _text      = "#F0F0F0"
    _text_muted= "#999999"
    _primary   = "#E0E0E0"
    _accent    = "#AAAAAA"
    _shadow    = "0 4px 24px rgba(0,0,0,0.5)"
    _shadow_h  = "0 8px 40px rgba(0,0,0,0.7)"
    _header_gr = "linear-gradient(135deg,#1A1A1A 0%,#2A2A2A 60%,#3A3A3A 100%)"
    _sidebar_gr= "linear-gradient(180deg,#0F0F0F 0%,#1A1A1A 50%,#222222 100%)"
    _metric_bg = "#252525"
    _input_bg  = "rgba(255,255,255,0.07)"
    _input_bdr = "rgba(255,255,255,0.15)"
    _tab_bg    = "#1E1E1E"
    _tab_sel   = "#333333"
    _progress  = "linear-gradient(90deg,#555555,#888888)"
    _btn_gr    = "linear-gradient(135deg,#333333,#555555)"
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
    _metric_bg = "#FFFFFF"
    _input_bg  = "#FFFFFF"
    _input_bdr = "#DDDDDD"
    _tab_bg    = "#FFFFFF"
    _tab_sel   = "#111111"
    _progress  = "linear-gradient(90deg,#111111,#555555)"
    _btn_gr    = "linear-gradient(135deg,#111111,#444444)"

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

/* ── 헤더 ── */
.main-header {{
    background: {_header_gr};
    border-radius: 20px;
    padding: 36px 40px;
    margin-bottom: 28px;
    position: relative;
    overflow: hidden;
    box-shadow: {_shadow_h};
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
[data-testid="stSidebar"] * {{ color: white !important; }}
[data-testid="stSidebar"] .stTextInput > div > div > input {{
    background: {_input_bg if _dark else 'rgba(255,255,255,0.12)'} !important;
    border: 1px solid {_input_bdr if _dark else 'rgba(255,255,255,0.25)'} !important;
    color: white !important;
    border-radius: 10px !important;
}}
[data-testid="stSidebar"] .stSelectbox > div > div {{
    background: rgba(255,255,255,0.12) !important;
    border: 1px solid rgba(255,255,255,0.25) !important;
    border-radius: 10px !important;
}}
[data-testid="stSidebar"] label {{
    color: rgba(255,255,255,0.85) !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
}}

/* ── 프로그레스 바 ── */
.stProgress > div > div > div {{
    background: {_progress} !important;
    border-radius: 8px !important;
}}

/* ── 메트릭 ── */
div[data-testid="metric-container"] {{
    background: {_metric_bg} !important;
    border-radius: 14px !important;
    padding: 18px !important;
    border: 1px solid var(--border) !important;
    box-shadow: var(--shadow) !important;
}}
div[data-testid="metric-container"] * {{ color: var(--text) !important; }}

/* ── 배지 ── */
.share-badge-high {{ display:inline-block; background:linear-gradient(135deg,#10B981,#059669); color:white; padding:4px 12px; border-radius:20px; font-size:0.85rem; font-weight:700; }}
.share-badge-mid  {{ display:inline-block; background:linear-gradient(135deg,#F59E0B,#D97706); color:white; padding:4px 12px; border-radius:20px; font-size:0.85rem; font-weight:700; }}
.share-badge-low  {{ display:inline-block; background:linear-gradient(135deg,#EF4444,#DC2626); color:white; padding:4px 12px; border-radius:20px; font-size:0.85rem; font-weight:700; }}

/* ── 사이드바 로고 ── */
.sidebar-logo {{ text-align:center; padding:20px 0 24px 0; border-bottom:1px solid rgba(255,255,255,0.15); margin-bottom:20px; }}
.sidebar-logo .logo-icon {{ font-size:2.5rem; display:block; margin-bottom:8px; }}
.sidebar-logo h2 {{ color:white !important; font-size:1.1rem !important; font-weight:800 !important; margin:0 !important; }}
.sidebar-logo p  {{ color:rgba(255,255,255,0.6) !important; font-size:0.75rem !important; margin:4px 0 0 0 !important; }}

/* ── 섹션 헤더 ── */
.section-header {{ display:flex; align-items:center; gap:10px; margin:24px 0 16px 0; }}
.section-header h3 {{ color:var(--text); font-size:1.05rem; font-weight:700; margin:0; }}

/* ── 구분선 ── */
.custom-divider {{ border:none; height:1px; background:linear-gradient(90deg,transparent,var(--border),transparent); margin:24px 0; }}

/* ── 경쟁사 행 ── */
.competitor-row {{ display:flex; align-items:center; justify-content:space-between; padding:12px 16px; border-radius:10px; margin:6px 0; background:var(--bg2); border:1px solid var(--border); }}

/* ── 다크모드 추가 보완 ── */
{"" if not _dark else """
.stMarkdown, .stMarkdown p, .stMarkdown li { color: #E0E0E0 !important; }
.stExpander { background: #1E1E1E !important; border-color: #333333 !important; }
.stExpander summary { color: #E0E0E0 !important; }
.stDataFrame { background: #1E1E1E !important; }
[data-testid="stTable"] { background: #1E1E1E !important; }
.stSelectbox > div > div { background: #252525 !important; border-color: #444 !important; color: #E0E0E0 !important; }
.stSlider > div > div > div { background: #444 !important; }
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
# 브랜드 변형 탐지 — 한글명·약칭·도메인 모두 커버
# ─────────────────────────────────────────────
def build_brand_variants(target_url: str, biz_info: dict) -> list[str]:
    """
    도메인·브랜드명·한글명·영문명·약칭·혼용표기·도메인 오타 등
    다양한 변형을 포함한 탐지 변형 목록을 반환한다.
    AI 답변 내 인용 여부를 최대한 정확히 체크하기 위해 폭넓게 수집.
    """
    domain      = extract_domain(target_url)
    brand_name  = biz_info.get("brand_name", "")
    domain_stem = domain.split(".")[0].lower()

    variants = set()

    # ── 1. 도메인 기반 ──
    variants.add(domain.lower())
    variants.add(domain_stem)
    for part in domain.lower().split("."):
        if len(part) > 2:
            variants.add(part)

    # ── 2. 브랜드명 기본 ──
    if brand_name:
        variants.add(brand_name.lower())
        variants.add(brand_name.replace(" ", "").lower())
        cleaned = re.sub(r'[^\w가-힣]', '', brand_name).lower()
        if cleaned:
            variants.add(cleaned)

    # ── 3. 영문 → 한글 발음 근사 매핑 ──
    _en2ko = {
        "naver": "네이버", "kakao": "카카오", "coupang": "쿠팡",
        "toss": "토스", "baemin": "배민", "krafton": "크래프톤",
        "nexon": "넥슨", "ncsoft": "엔씨소프트", "netmarble": "넷마블",
        "samsung": "삼성", "lg": "엘지", "hyundai": "현대",
        "lotte": "롯데", "sk": "에스케이", "kt": "케이티",
        "line": "라인", "nhn": "엔에이치엔", "melon": "멜론",
        "woowa": "우아한형제들", "daum": "다음", "11st": "11번가",
        "gmarket": "지마켓", "auction": "옥션", "interpark": "인터파크",
        "yes24": "예스이십사", "kyobo": "교보", "ridibooks": "리디북스",
        "hybe": "하이브", "smtown": "에스엠", "jyp": "제이와이피",
        "krafton": "크래프톤", "ncsoft": "엔씨", "nexon": "넥슨",
        "kakaopay": "카카오페이", "kakaotalk": "카카오톡",
        "navershopping": "네이버쇼핑", "naverblog": "네이버블로그",
        "musinsa": "무신사", "zigzag": "지그재그", "kurly": "마켓컬리",
        "bamin": "배민", "yogiyo": "요기요", "coupangeats": "쿠팡이츠",
    }
    for en, ko in _en2ko.items():
        if en in brand_name.lower() or en == domain_stem or en in domain.lower():
            variants.add(ko)
            variants.add(en)

    # ── 4. 한글 → 영문 역방향 매핑 ──
    _ko2en = {v: k for k, v in _en2ko.items()}
    for ko, en in _ko2en.items():
        if ko in brand_name:
            variants.add(en)
            variants.add(ko)

    # ── 5. 브랜드 약칭 생성 ──
    if brand_name:
        words = brand_name.split()
        if len(words) >= 2:
            abbrev = "".join(w[0] for w in words if w).lower()
            if len(abbrev) >= 2:
                variants.add(abbrev)
        first_word = words[0].lower() if words else ""
        if len(first_word) >= 2:
            variants.add(first_word)

    # ── 6. 도메인 오타 변형 ──
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

    # ── 7. 한글/영문 혼용 표기 ──
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
def fetch_competitor_search_context(industry: str, brand: str) -> str:
    queries = [
        f"{industry} 주요 경쟁사",
        f"{brand} 경쟁사 대안 서비스",
        f"{industry} 업체 비교",
    ]
    collected = []
    headers = {
        "Accept": "text/markdown, text/plain, */*",
        "X-Return-Format": "markdown",
        "X-Timeout": "10",
    }
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
# AI 업종 분석 기반 경쟁사 도출 (Jina 강화 + 검증 포함)
# ─────────────────────────────────────────────
def discover_competitors(client_gpt, client_gemini,
                          biz_info: dict, target_url: str,
                          model_gpt: str,
                          n_competitors: int = 5,
                          confirmed_industry: str = "") -> list[dict]:
    brand    = biz_info.get("brand_name", extract_domain(target_url))
    industry = confirmed_industry.strip() if confirmed_industry.strip() else biz_info.get("industry", "디지털 서비스")
    product  = biz_info.get("core_product", "서비스")
    audience = biz_info.get("target_audience", "일반 사용자")
    domain   = extract_domain(target_url)

    search_context = fetch_competitor_search_context(industry, brand)
    search_context_section = f"""
[실제 검색 데이터 — 이 데이터를 최우선 근거로 활용하세요]
{search_context if search_context else "(검색 결과 없음 — AI 자체 지식으로 판단)"}
""" if search_context else "[검색 데이터: 없음 — AI 자체 지식으로 판단]"

    prompt = f"""당신은 디지털 마케팅 업계 전문 애널리스트입니다.
아래 검색 데이터와 브랜드 정보를 바탕으로 실제 직접 경쟁사를 도출하고, 각 항목을 논리적으로 검증하세요.

[분석 대상 — 사용자가 직접 확정한 업종 정보]
- 브랜드명: {brand}
- 도메인: {domain}
- 업종 (확정값): {industry}
- 핵심 서비스: {product}
- 주요 타겟: {audience}

{search_context_section}

[경쟁사 도출 기준]
1. 위 검색 데이터에 실제로 등장하는 브랜드/사이트를 최우선 선정
2. 확정 업종 "{industry}"와 정확히 동일한 카테고리에서 경쟁하는 기업만 포함
3. {brand} 고객이 이탈할 경우 선택할 가능성이 가장 높은 대안 서비스 우선
4. 분석 대상 브랜드({brand})의 주 서비스 지역과 언어를 스스로 파악하여, 해당 시장에서 실제로 경쟁하는 기업을 도출하세요.
5. {brand} 자체({domain})는 절대 포함하지 마세요

[검증 기준 — 각 경쟁사를 반드시 아래 기준으로 검토 후 출력]
- domain_valid: 해당 도메인이 실제 존재하고 운영 중인 서비스인가? (가상·예시 도메인 제외)
- is_direct_competitor: {brand}와 동일 업종에서 동일 고객을 두고 직접 경쟁하는가?
- 두 조건 모두 true인 항목만 최종 출력에 포함

[출력 형식 — JSON 배열만, 다른 텍스트 없음]
[
  {{
    "rank": 1,
    "brand_name": "브랜드명 (한글 또는 영문)",
    "domain": "실제존재하는도메인.com",
    "reason": "경쟁 관계 이유 25자 이내",
    "market_position": "업계 1위 / 신흥 강자 / 틈새 전문 중 택1",
    "domain_valid": true,
    "is_direct_competitor": true,
    "evidence": "검색 데이터 또는 AI 지식 중 근거 출처"
  }},
  ...
]

검증을 통과한 경쟁사 {n_competitors}개를 rank 순으로 출력하세요."""

    result_str = ""
    try:
        if client_gpt:
            result_str = call_gpt(client_gpt, prompt, max_tokens=1200, model=model_gpt,
                                   temperature_override=0.2)
        elif client_gemini:
            result_str = call_gemini(client_gemini, prompt, max_tokens=1200,
                                      temperature_override=0.2)
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
                and c.get("domain", "").strip()
                and "competitor" not in c.get("domain", "").lower()
            ]
    except Exception:
        pass

    if not competitors:
        competitors = [
            {"rank": i+1, "brand_name": f"경쟁사 {i+1}", "domain": f"competitor{i+1}.com",
             "reason": "동종 업계 경쟁사", "market_position": "시장 참여자",
             "domain_valid": False, "is_direct_competitor": False, "evidence": "폴백"}
            for i in range(n_competitors)
        ]
    return competitors[:n_competitors]


# ─────────────────────────────────────────────
# 경쟁사 포함 SOV(Share of Voice) 시뮬레이션
# ─────────────────────────────────────────────
def run_sov_simulation(client_gpt, client_gemini,
                        question: str,
                        target_url: str,
                        competitor_list: list[dict],
                        biz_info: dict,
                        model_gpt: str,
                        n: int = 30) -> dict:
    all_urls = [target_url] + [
        normalize_url(c.get("domain", "")) for c in competitor_list
        if c.get("domain", "").strip()
    ]
    all_labels = [biz_info.get("brand_name", extract_domain(target_url))] + [
        c.get("brand_name", c.get("domain", "")) for c in competitor_list
    ]

    def _sim_one_brand(url: str, brand_variants: list[str]) -> dict:
        gpt_hits = 0
        gem_hits = 0
        gpt_ran  = False
        gem_ran  = False

        def _gpt_batch():
            h = 0
            for _ in range(n):
                try:
                    res = call_gpt(
                        client_gpt,
                        f"질문: {question}\n\n답변:",
                        max_tokens=150, model=model_gpt,
                        temperature_override=0.5
                    )
                    if any(v in res.lower() for v in brand_variants):
                        h += 1
                except Exception:
                    pass
            return h

        def _gem_batch():
            h = 0
            for _ in range(n):
                try:
                    res = call_gemini(
                        client_gemini,
                        f"질문: {question}\n\n답변:",
                        max_tokens=150,
                        temperature_override=0.5
                    )
                    if any(v in res.lower() for v in brand_variants):
                        h += 1
                except Exception:
                    pass
            return h

        futures = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            if client_gpt:
                futures["gpt"] = ex.submit(_gpt_batch)
            if client_gemini:
                futures["gem"] = ex.submit(_gem_batch)
            if "gpt" in futures:
                try:
                    gpt_hits = futures["gpt"].result(timeout=max(120, n*3))
                    gpt_ran  = True
                except Exception:
                    pass
            if "gem" in futures:
                try:
                    gem_hits = futures["gem"].result(timeout=max(120, n*3))
                    gem_ran  = True
                except Exception:
                    pass

        gpt_rate = round(gpt_hits / n * 100, 1) if gpt_ran else None
        gem_rate = round(gem_hits / n * 100, 1) if gem_ran else None
        avg      = round(
            sum(v for v in [gpt_rate, gem_rate] if v is not None) /
            max(1, sum(1 for v in [gpt_rate, gem_rate] if v is not None)), 1
        )
        ci_lo, ci_hi = calc_confidence_interval(
            (gpt_hits if gpt_ran else 0) + (gem_hits if gem_ran else 0),
            (n if gpt_ran else 0) + (n if gem_ran else 0)
        )
        return {
            "gpt_rate": gpt_rate, "gem_rate": gem_rate,
            "avg_rate": avg, "ci_lo": ci_lo, "ci_hi": ci_hi,
            "gpt_hits": gpt_hits if gpt_ran else None,
            "gem_hits": gem_hits if gem_ran else None,
            "n": n,
        }

    sov_results = []
    for i, (url, label) in enumerate(zip(all_urls, all_labels)):
        brand_biz = {"brand_name": label, "industry": biz_info.get("industry", "")}
        if i == 0:
            brand_biz = biz_info
        bv = build_brand_variants(url, brand_biz)
        res = _sim_one_brand(url, bv)
        res["label"]    = label
        res["domain"]   = extract_domain(url)
        res["is_target"] = (i == 0)
        sov_results.append(res)

    return sov_results


# ─────────────────────────────────────────────
# 심층 사이트 크롤링 — 비즈니스 실체 추출
# ─────────────────────────────────────────────
class _MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.description = ""
        self.og_title = ""
        self.og_description = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            name = attrs_dict.get("name", "").lower()
            prop = attrs_dict.get("property", "").lower()
            content = attrs_dict.get("content", "")
            if name == "description":
                self.description = content
            elif prop == "og:title":
                self.og_title = content
            elif prop == "og:description":
                self.og_description = content

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title and not self.title:
            self.title = data.strip()


def crawl_site_metadata(url: str) -> dict:
    jina_url = f"https://r.jina.ai/{url}"
    headers = {
        "Accept": "text/markdown, text/plain, */*",
        "X-Return-Format": "markdown",
        "X-Timeout": "15",
    }
    try:
        resp = requests.get(jina_url, headers=headers, timeout=20)
        if resp.status_code != 200:
            raise ValueError(f"Jina status {resp.status_code}")
        markdown_text = resp.text.strip()
        if len(markdown_text) < 200:
            raise ValueError("Jina returned too little content")

        title = ""
        for line in markdown_text.splitlines():
            line = line.strip()
            if line.startswith("#"):
                title = line.lstrip("#").strip()
                break
            elif line:
                title = line[:100]
                break

        description = ""
        in_content = False
        for line in markdown_text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                if description:
                    break
                continue
            description += stripped + " "
            in_content = True
            if len(description) > 300:
                break

        return {
            "title": title,
            "description": description.strip()[:500],
            "html_snippet": markdown_text[:6000],
            "crawl_ok": True,
        }
    except Exception:
        ua_list = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        ]
        for ua in ua_list:
            try:
                resp = requests.get(
                    url,
                    headers={"User-Agent": ua, "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8"},
                    timeout=10, allow_redirects=True
                )
                resp.encoding = resp.apparent_encoding or "utf-8"
                html = resp.text[:80_000]
                if len(html) < 500 or "자동등록방지" in html or "prove that you are human" in html.lower():
                    continue
                parser = _MetaParser()
                parser.feed(html)
                return {
                    "title": parser.og_title or parser.title or "",
                    "description": parser.og_description or parser.description or "",
                    "html_snippet": html[:4000],
                    "crawl_ok": True,
                }
            except Exception:
                continue
    return {"title": "", "description": "", "html_snippet": "", "crawl_ok": False}


def web_search_business_info(domain: str) -> str:
    queries = [
        f"{domain} 회사 업종 서비스 소개",
        f"site:{domain} OR \"{domain.split('.')[0]}\" 광고 마케팅 쇼핑 서비스",
    ]
    snippets = []
    headers = {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1)"}
    for q in queries[:1]:
        try:
            resp = requests.get(
                "https://www.bing.com/search",
                params={"q": q, "setlang": "ko"},
                headers=headers, timeout=8
            )
            text = re.sub(r'<[^>]+>', ' ', resp.text)
            text = re.sub(r'\s+', ' ', text)
            idx = text.lower().find(domain.split(".")[0].lower())
            if idx > 0:
                snippets.append(text[max(0, idx-100):idx+400])
        except Exception:
            pass
    return " ".join(snippets)[:2000]


def analyze_business_identity(client_gpt, client_gemini, url: str,
                               model_gpt: str, model_gemini) -> dict:
    meta        = crawl_site_metadata(url)
    domain      = extract_domain(url)
    domain_stem = domain.split(".")[0]

    jina_biz_context = ""
    try:
        biz_query = f"https://r.jina.ai/https://www.google.com/search?q={requests.utils.quote(domain_stem + ' 업종 서비스 소개')}&hl=ko"
        r = requests.get(biz_query, headers={"Accept": "text/markdown", "X-Timeout": "10"}, timeout=15)
        if r.status_code == 200 and len(r.text) > 200:
            jina_biz_context = r.text[:3000]
    except Exception:
        pass

    web_context = ""
    if not meta["crawl_ok"] or (not meta["title"] and not meta["description"]):
        web_context = web_search_business_info(domain)

    combined_context = "\n".join(filter(None, [jina_biz_context, web_context]))[:4000]

    prompt = f"""당신은 비즈니스 인텔리전스 전문가입니다.
아래 웹사이트 정보를 바탕으로 업종과 서비스를 **정확하고 구체적으로** 분석하세요.

[도메인]
{domain}

[크롤링 데이터]
제목: {meta.get('title', '(없음)')}
설명: {meta.get('description', '(없음)')}
본문: {meta.get('html_snippet', '')[:2000]}

[사이트명 + 업종 검색 보완 정보]
{combined_context if combined_context else '(없음)'}

[분석 지침]
- 업종은 반드시 실제 구체적인 카테고리로 작성
- "디지털 서비스", "IT 서비스", "온라인 서비스" 같은 포괄적이고 모호한 업종명 절대 금지
- 정보가 부족해도 도메인명과 검색 맥락에서 추론하여 가장 그럴듯한 구체적 업종을 제시할 것
- 광고/마케팅 관련 키워드(대행사, 퍼포먼스, IMC, 바이럴 등)가 있으면 반드시 광고대행사 계열로 분류
- brand_name은 도메인이 아닌 실제 회사명/브랜드명 (한글 우선)

다른 설명 없이 JSON만 출력:
{{
  "brand_name": "실제 브랜드명 또는 회사명",
  "industry": "구체적 업종 (예: 퍼포먼스 마케팅 광고대행사)",
  "industry_category": "대분류 (예: 광고/마케팅, 이커머스, SaaS, 금융, 교육, 의료, 부동산, 제조, 물류 등)",
  "core_product": "핵심 서비스/상품 한 문장",
  "target_audience": "주요 타겟 고객층 (구체적으로)",
  "key_services": ["서비스1", "서비스2", "서비스3"]
}}"""

    result_str = ""
    try:
        if client_gpt:
            result_str = call_gpt(client_gpt, prompt, max_tokens=600, model=model_gpt,
                                   temperature_override=0.2)
        elif client_gemini:
            result_str = call_gemini(client_gemini, prompt, max_tokens=600,
                                      temperature_override=0.2)
    except Exception:
        pass

    try:
        json_match = re.search(r'\{.*\}', result_str, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            industry = parsed.get("industry", "")
            bad_industries = ["디지털 서비스", "IT 서비스", "온라인 서비스",
                              "인터넷 서비스", "웹 서비스", "소프트웨어"]
            if any(bad in industry for bad in bad_industries) and combined_context:
                retry_prompt = f"""도메인 {domain}의 업종을 검색 정보 기반으로 정확히 분류하세요.

[검색 정보]
{combined_context[:2000]}

가장 구체적인 업종명을 JSON으로만 출력 (예: {{"industry": "퍼포먼스 마케팅 광고대행사"}}):"""
                try:
                    r2 = call_gpt(client_gpt, retry_prompt, max_tokens=100, model=model_gpt,
                                   temperature_override=0.1) if client_gpt else \
                         call_gemini(client_gemini, retry_prompt, max_tokens=100,
                                      temperature_override=0.1)
                    m2 = re.search(r'\{.*\}', r2, re.DOTALL)
                    if m2:
                        parsed["industry"] = json.loads(m2.group()).get("industry", industry)
                except Exception:
                    pass
            parsed.pop("confidence", None)
            return parsed
    except Exception:
        pass

    return {
        "brand_name": domain_stem.upper(),
        "industry": f"{domain_stem} 관련 서비스",
        "industry_category": "기타",
        "core_product": f"{domain} 서비스",
        "target_audience": "잠재 고객",
        "key_services": [],
    }


def get_badge_class(rate: float) -> str:
    if rate >= 30:
        return "share-badge-high"
    elif rate >= 10:
        return "share-badge-mid"
    else:
        return "share-badge-low"


# ─────────────────────────────────────────────
# 데모 데이터 생성 (API 키 없이 보고용)
# ─────────────────────────────────────────────
DEMO_SCENARIOS = {
    "naver.com": {
        "questions": [
            "국내 최고의 포털 사이트는 어디인가요?",
            "한국에서 뉴스 검색하기 좋은 사이트는?",
            "네이버 쇼핑과 쿠팡 중 어디가 더 편리한가요?",
            "블로그 만들기 좋은 플랫폼 추천해주세요",
            "한국어 지도 서비스 어디가 제일 정확한가요?",
        ],
        "results": [
            {"gpt_rate": 58.3, "gemini_rate": 62.1, "gpt_hits": 58, "gemini_hits": 62, "total": 100},
            {"gpt_rate": 44.7, "gemini_rate": 51.2, "gpt_hits": 45, "gemini_hits": 51, "total": 100},
            {"gpt_rate": 31.5, "gemini_rate": 27.8, "gpt_hits": 32, "gemini_hits": 28, "total": 100},
            {"gpt_rate": 22.0, "gemini_rate": 18.4, "gpt_hits": 22, "gemini_hits": 18, "total": 100},
            {"gpt_rate": 39.6, "gemini_rate": 43.3, "gpt_hits": 40, "gemini_hits": 43, "total": 100},
        ],
    },
    "coupang.com": {
        "questions": [
            "한국에서 가장 빠른 배송 쇼핑몰은?",
            "로켓배송으로 당일 받을 수 있는 쇼핑몰은?",
            "쿠팡과 네이버쇼핑 가격 비교해주세요",
            "쿠팡 로켓와우 멤버십 혜택은?",
            "신선식품 새벽배송 어디가 좋나요?",
        ],
        "results": [
            {"gpt_rate": 71.2, "gemini_rate": 68.5, "gpt_hits": 71, "gemini_hits": 69, "total": 100},
            {"gpt_rate": 65.8, "gemini_rate": 59.3, "gpt_hits": 66, "gemini_hits": 59, "total": 100},
            {"gpt_rate": 38.4, "gemini_rate": 42.1, "gpt_hits": 38, "gemini_hits": 42, "total": 100},
            {"gpt_rate": 52.7, "gemini_rate": 48.9, "gpt_hits": 53, "gemini_hits": 49, "total": 100},
            {"gpt_rate": 29.1, "gemini_rate": 33.6, "gpt_hits": 29, "gemini_hits": 34, "total": 100},
        ],
    },
    "default": {
        "questions": [
            "이 서비스의 주요 특징은 무엇인가요?",
            "비슷한 경쟁 서비스와 비교했을 때 장점은?",
            "초보자도 쉽게 사용할 수 있나요?",
            "가격 정책과 요금제는 어떻게 되나요?",
            "고객 지원 및 문의는 어떻게 하나요?",
        ],
        "results": [
            {"gpt_rate": 7.2,  "gemini_rate": 5.4,  "gpt_hits": 7,  "gemini_hits": 5,  "total": 100},
            {"gpt_rate": 4.8,  "gemini_rate": 8.1,  "gpt_hits": 5,  "gemini_hits": 8,  "total": 100},
            {"gpt_rate": 12.3, "gemini_rate": 9.7,  "gpt_hits": 12, "gemini_hits": 10, "total": 100},
            {"gpt_rate": 3.1,  "gemini_rate": 6.5,  "gpt_hits": 3,  "gemini_hits": 7,  "total": 100},
            {"gpt_rate": 15.6, "gemini_rate": 11.2, "gpt_hits": 16, "gemini_hits": 11, "total": 100},
        ],
    },
}

DEMO_STRATEGY = {
    "competitors": [
        {"rank": 1, "domain": "wikipedia.org",    "reason": "중립적 참조 정보 풍부"},
        {"rank": 2, "domain": "namu.wiki",         "reason": "한국어 위키 전문"},
        {"rank": 3, "domain": "tistory.com",       "reason": "SEO 최적화 블로그"},
        {"rank": 4, "domain": "brunch.co.kr",      "reason": "전문가 롱폼 콘텐츠"},
        {"rank": 5, "domain": "target-site.com",   "reason": "← 내 사이트"},
        {"rank": 6, "domain": "medium.com",        "reason": "영문 고품질 아티클"},
        {"rank": 7, "domain": "velog.io",          "reason": "개발자 기술 블로그"},
        {"rank": 8, "domain": "inflearn.com",      "reason": "학습 플랫폼 권위"},
        {"rank": 9, "domain": "wanted.co.kr",      "reason": "직종별 정보 DB"},
        {"rank": 10, "domain": "blog.naver.com",   "reason": "포털 연계 트래픽"},
    ],
    "diagnoses": [
        "구조화 데이터(Schema.org) 마크업이 없어 AI가 콘텐츠 맥락을 파악하기 어려움",
        "FAQ 섹션 부재 — AI는 Q&A 형태 콘텐츠를 인용 우선순위로 처리함",
        "핵심 키워드 밀도가 경쟁사 대비 40% 낮아 관련성 점수에서 불이익 발생",
    ],
    "keywords": [
        "AI 인용 최적화 전략 2025",
        "GEO(Generative Engine Optimization) 적용 방법",
        "챗봇 검색에서 브랜드 노출 높이는 법",
        "LLM 친화적 콘텐츠 구조 만들기",
        "AI 답변 출처로 선택되는 사이트 조건",
    ],
    "geo_guides": [
        "1. FAQ 블록 추가\n홈페이지 하단에 '자주 묻는 질문' 섹션을 추가하고, 질문·답변 형식으로 핵심 서비스를 설명하세요. AI는 Q&A 구조를 높은 신뢰도 콘텐츠로 인식합니다.",
        "2. 구조화 데이터 마크업 적용\n<script type='application/ld+json'>으로 Organization, WebSite, FAQPage 스키마를 삽입하면 AI 크롤러가 사이트를 명확하게 분류합니다.",
        "3. 핵심 가치 제안을 첫 문단에 배치\n'저희 서비스는 ~입니다' 형태의 명확한 정의 문장을 페이지 최상단에 위치시켜 AI가 사이트를 특정 주제의 권위 있는 출처로 인식하게 합니다.",
    ],
}


def get_demo_data(url: str) -> dict:
    domain = extract_domain(url).lower()
    for key in DEMO_SCENARIOS:
        if key != "default" and key in domain:
            scenario = DEMO_SCENARIOS[key].copy()
            strategy = DEMO_STRATEGY.copy()
            for comp in strategy["competitors"]:
                if "target-site" in comp["domain"]:
                    comp["domain"] = domain
            return {"scenario": scenario, "strategy": strategy}
    scenario = DEMO_SCENARIOS["default"].copy()
    strategy = DEMO_STRATEGY.copy()
    for comp in strategy["competitors"]:
        if "target-site" in comp["domain"]:
            comp["domain"] = extract_domain(url) if url else "your-site.com"
    return {"scenario": scenario, "strategy": strategy}


# ─────────────────────────────────────────────
# GPT API 호출
# ─────────────────────────────────────────────
def call_gpt(client, prompt: str, system: str = "", model: str = "gpt-4o-mini",
             max_tokens: int = 1500, temperature_override: float = None) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    temp = temperature_override if temperature_override is not None else 0.7
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temp,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise RuntimeError(f"GPT API 오류: {e}")


# ─────────────────────────────────────────────
# Gemini API 호출
# ─────────────────────────────────────────────
def call_gemini(model_obj, prompt: str, max_tokens: int = 1500,
                temperature_override: float = None) -> str:
    temp = temperature_override if temperature_override is not None else 0.7
    try:
        response = model_obj.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temp,
            )
        )
        return response.text.strip()
    except Exception as e:
        raise RuntimeError(f"Gemini API 오류: {e}")


# ─────────────────────────────────────────────
# AI 타겟 질문 생성 — 비즈니스 전환형 (심층 분석 기반)
# ─────────────────────────────────────────────
def generate_target_questions(client_gpt, client_gemini, url: str, engine: str,
                               model_gpt: str, model_gemini,
                               biz_info: dict = None,
                               manual_brand: str = "") -> list[str]:
    if not biz_info:
        biz_info = {
            "brand_name": extract_domain(url).split(".")[0].upper(),
            "industry": "서비스",
            "industry_category": "기타",
            "core_product": "서비스",
            "target_audience": "잠재 고객",
            "key_services": [],
        }

    brand    = manual_brand.strip() if manual_brand.strip() else biz_info.get("brand_name", "해당 브랜드")
    industry = biz_info.get("industry", "서비스")
    category = biz_info.get("industry_category", "")
    product  = biz_info.get("core_product", "서비스")
    audience = biz_info.get("target_audience", "잠재 고객")
    services = biz_info.get("key_services", [])
    services_str = ", ".join(services) if services else product
    domain_clean = extract_domain(url).replace("www.", "")
    confidence = biz_info.get("confidence", "medium")

    category_hints = {
        "광고/마케팅": "광고주(중소기업 대표, 마케터)가 광고대행사를 선택할 때 실제로 묻는 질문 — 수익률(ROAS), 집행 매체, 성과 보고, 계약 조건, 업종 레퍼런스 위주",
        "이커머스": "구매자 입장의 배송·가격·신뢰도·반품 관련 질문, 판매자 입장의 입점·수수료·마케팅 지원 질문",
        "SaaS": "도입 전 데모·트라이얼·연동·보안·가격 플랜, 기존 솔루션 대비 전환 비용 관련 질문",
        "금융": "금리·한도·수수료·안전성·가입 조건, 타 금융사 대비 실질 혜택 관련 질문",
        "교육": "커리큘럼·강사·합격률·환불정책, 취업/자격증 연계 관련 질문",
        "의료": "진료 과목·의사 경력·비용·예약, 타 병원 대비 전문성 관련 질문",
        "부동산": "매물·가격·수수료·계약 절차, 지역 시세 및 투자 관련 질문",
    }
    angle_hint = category_hints.get(category, f"{industry} 분야에서 {audience}가 실제로 고민하는 핵심 질문")

    prompt = f"""당신은 {industry} 분야의 10년 경력 마케팅 전략가이자 GEO(Generative Engine Optimization) 전문가입니다.

[분석 대상 브랜드 — 이 정보를 질문에 반드시 반영할 것]
- 브랜드명: {brand}  ← 질문 안에 반드시 이 브랜드명을 자연스럽게 포함할 것 (도메인 주소 절대 금지)
- 업종: {industry} ({category})
- 핵심 서비스: {services_str}
- 주요 타겟: {audience}
- 도메인(참고용, 질문에 사용 금지): {domain_clean}
- 분석 신뢰도: {confidence}

[업종 맞춤 질문 방향]
{angle_hint}

[생성 규칙 — 반드시 준수]
1. 실제 {audience}가 "{brand}"를 검색하거나 도입·계약·구매를 결정할 때 AI 챗봇에 입력하는 **현실적인 질문**만 생성
2. 각 질문은 완전히 다른 구매 결정 단계(인지→비교→신뢰→가격→전환)를 다룰 것
3. "{brand}" 브랜드명을 질문 안에 자연스럽게 포함 (단, 너무 억지스럽지 않게)
4. {industry} 업계 고유의 전문 용어·지표·관행을 적극 활용 (예: 광고대행사라면 ROAS, CPA, 퍼포먼스, 매체비, 대행수수료 등)
5. "~는 무엇인가요?", "~를 소개해주세요", "~의 위치는 어디인가요?" 같은 정보 탐색형 기초 질문 절대 금지
6. 구체적인 상황·수치·비교 대상이 포함된 깊이 있는 질문 작성

[Few-Shot 예시 — 이 톤앤매너를 반드시 따를 것]

✅ GOOD 예시 (이런 질문을 만들어야 한다):
- "{brand}의 퍼포먼스 마케팅 집행 시 타 대행사 대비 평균 ROAS 달성 수치와 성공 사례는?"
- "{brand} 가맹점 창업 시 실질적인 원가율과 본사 지원 혜택은?"
- "{brand}를 도입한 중소기업이 6개월 내 실제로 달성한 전환율 개선 수치와 도입 비용 대비 ROI는?"
- "{brand}와 경쟁사 A·B를 동시에 운영해본 마케터 입장에서 CPA·CTR 차이가 실제로 얼마나 나나요?"
- "{brand}의 월 최소 광고비 기준과 대행수수료 구조가 업계 평균 대비 어떤 수준인지 비교해주세요?"

❌ BAD 예시 (절대 이런 질문을 만들면 안 된다):
- "{brand}는 무엇을 하는 곳인가요?" (너무 기초적)
- "{brand}의 위치는 어디인가요?" (무관한 정보)
- "{brand}를 소개해주세요" (정보 탐색형, 구매 결정과 무관)
- "{brand}의 역사는 어떻게 되나요?" (구매 전환과 무관)

[출력]
번호, 라벨, 설명 없이 질문 5개만 출력. 한 줄에 하나. 반드시 물음표(?)로 종결. 도메인 주소 포함 금지.

질문 5개:"""

    result = ""
    try:
        if engine == "GPT" and client_gpt:
            result = call_gpt(client_gpt, prompt, max_tokens=1000, model=model_gpt,
                              temperature_override=0.8)
        elif engine == "Gemini" and client_gemini:
            result = call_gemini(client_gemini, prompt, max_tokens=1000,
                                  temperature_override=0.8)
        elif client_gemini:
            result = call_gemini(client_gemini, prompt, max_tokens=1000,
                                  temperature_override=0.8)
        elif client_gpt:
            result = call_gpt(client_gpt, prompt, max_tokens=1000, model=model_gpt,
                              temperature_override=0.8)
        else:
            raise RuntimeError("사용 가능한 API 클라이언트가 없습니다.")
    except Exception as e:
        raise RuntimeError(str(e))

    lines = [ln.strip() for ln in result.split("\n") if ln.strip()]
    questions = []
    for ln in lines:
        clean = re.sub(r'^[\d]+[.)]\s*', '', ln)
        clean = re.sub(r'^[-•*]\s*', '', clean)
        clean = re.sub(r'^\[.*?\]\s*', '', clean)
        clean = re.sub(r'^\*\*.*?\*\*\s*', '', clean)
        clean = clean.strip()
        if len(clean) > 10 and clean.endswith("?"):
            questions.append(clean)

    if len(questions) < 3:
        questions = []
        for ln in lines:
            clean = re.sub(r'^[\d]+[.)]\s*', '', ln)
            clean = re.sub(r'^[-•*]\s*', '', clean)
            clean = re.sub(r'^\[.*?\]\s*', '', clean)
            clean = clean.strip()
            if len(clean) > 12:
                if not clean.endswith("?"):
                    clean += "?"
                questions.append(clean)

    questions = questions[:5]

    if len(questions) < 3:
        ad_agency_questions = [
            f"{brand}의 업종별 광고 집행 ROAS가 타 대행사 대비 어느 수준인가요?",
            f"{audience}가 {brand}에 광고를 맡기기 전에 확인해야 할 계약 조건은?",
            f"{brand}의 네이버·카카오·메타 공식 파트너 여부와 집행 가능한 매체 범위는?",
            f"{industry}에서 {brand}를 쓰면 직접 운영 대비 대행수수료 구조가 어떻게 되나요?",
            f"{brand}의 실제 광고주 성과 사례와 평균 CPA·CTR 수준은 어떻게 되나요?",
        ]
        generic_questions = [
            f"{brand}가 {industry} 시장에서 경쟁사 대비 실제로 다른 점은 무엇인가요?",
            f"{audience}가 {brand}를 선택한 후 실제로 얻은 성과나 변화는?",
            f"{brand}의 계약·이용 조건과 비용 구조가 동종 업계 대비 어떤 수준인가요?",
            f"{brand}에 대한 실제 사용자 평가와 주요 불만 사항은?",
            f"{industry} 분야에서 {brand}와 직접 비교되는 대안 서비스는 무엇인가요?",
        ]
        questions = ad_agency_questions if "광고" in industry or "마케팅" in industry else generic_questions

    return questions[:5]


# ─────────────────────────────────────────────
# 단일 쿼리 시뮬레이션 (GPT)
# ─────────────────────────────────────────────
def simulate_single_gpt(client, question: str, target_url: str, model: str,
                         brand_variants: list[str] = None) -> dict:
    if brand_variants is None:
        domain = extract_domain(target_url)
        brand_variants = [domain, domain.split(".")[0]]

    prompt = f"질문: {question}\n\n답변:"
    try:
        result = call_gpt(client, prompt, max_tokens=200, model=model,
                          temperature_override=0.5)
        cited = any(v.lower() in result.lower() for v in brand_variants if v)
        return {"cited": cited, "response_sample": result[:300] if cited else ""}
    except Exception:
        return {"cited": False, "response_sample": ""}


# ─────────────────────────────────────────────
# 단일 쿼리 시뮬레이션 (Gemini)
# ─────────────────────────────────────────────
def simulate_single_gemini(model_obj, question: str, target_url: str,
                            brand_variants: list[str] = None) -> dict:
    if brand_variants is None:
        domain = extract_domain(target_url)
        brand_variants = [domain, domain.split(".")[0]]

    prompt = f"질문: {question}\n\n답변:"
    try:
        result = call_gemini(model_obj, prompt, max_tokens=200,
                             temperature_override=0.5)
        cited = any(v.lower() in result.lower() for v in brand_variants if v)
        return {"cited": cited, "response_sample": result[:300] if cited else ""}
    except Exception:
        return {"cited": False, "response_sample": ""}


# ─────────────────────────────────────────────
# ── 점유율 계산 — GPT/Gemini 독립 처리 + 신뢰구간 + 응답 샘플
# ─────────────────────────────────────────────
def run_simulation(client_gpt, client_gemini, question: str, target_url: str,
                   model_gpt: str, model_gemini, n: int = 50,
                   biz_info: dict = None,
                   progress_callback=None) -> dict:

    actual_n = n
    brand_variants = build_brand_variants(target_url, biz_info or {})

    gpt_hits, gem_hits   = 0, 0
    gpt_ran,  gem_ran    = False, False
    gpt_samples, gem_samples = [], []

    def _run_gpt_batch():
        h = 0
        samples = []
        for _ in range(actual_n):
            try:
                r = simulate_single_gpt(client_gpt, question, target_url,
                                        model_gpt, brand_variants)
                if r["cited"]:
                    h += 1
                    if len(samples) < 3 and r["response_sample"]:
                        samples.append(r["response_sample"])
            except Exception:
                pass
        return h, samples

    def _run_gemini_batch():
        h = 0
        samples = []
        for _ in range(actual_n):
            try:
                r = simulate_single_gemini(client_gemini, question, target_url,
                                           brand_variants)
                if r["cited"]:
                    h += 1
                    if len(samples) < 3 and r["response_sample"]:
                        samples.append(r["response_sample"])
            except Exception:
                pass
        return h, samples

    futures = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        if client_gpt:
            futures["gpt"] = executor.submit(_run_gpt_batch)
        if client_gemini:
            futures["gemini"] = executor.submit(_run_gemini_batch)

        if progress_callback:
            progress_callback(0.5)

        timeout_sec = max(120, actual_n * 3)
        if "gpt" in futures:
            try:
                gpt_hits, gpt_samples = futures["gpt"].result(timeout=timeout_sec)
                gpt_ran = True
            except Exception:
                pass
        if "gemini" in futures:
            try:
                gem_hits, gem_samples = futures["gemini"].result(timeout=timeout_sec)
                gem_ran = True
            except Exception:
                pass

    if progress_callback:
        progress_callback(1.0)

    def _rate(hits, ran):
        return round(hits / actual_n * 100, 1) if ran else None

    gpt_rate = _rate(gpt_hits, gpt_ran)
    gem_rate = _rate(gem_hits, gem_ran)

    gpt_ci  = calc_confidence_interval(gpt_hits, actual_n) if gpt_ran else (None, None)
    gem_ci  = calc_confidence_interval(gem_hits, actual_n) if gem_ran else (None, None)

    valid_rates = [v for v in [gpt_rate, gem_rate] if v is not None]
    avg_rate = round(sum(valid_rates) / len(valid_rates), 1) if valid_rates else None

    return {
        "gpt_rate":    gpt_rate,
        "gemini_rate": gem_rate,
        "avg_rate":    avg_rate,
        "gpt_hits":    gpt_hits  if gpt_ran else None,
        "gemini_hits": gem_hits  if gem_ran else None,
        "total":       actual_n,
        "gpt_ci":      gpt_ci,
        "gemini_ci":   gem_ci,
        "gpt_samples":    gpt_samples,
        "gemini_samples": gem_samples,
    }


# ─────────────────────────────────────────────
# [고성능] 전체 질문 병렬 시뮬레이션 — 500% 속도 향상
# ─────────────────────────────────────────────
def run_all_simulations(client_gpt, client_gemini,
                         questions: list[str], target_url: str,
                         model_gpt: str, model_gemini,
                         n: int = 50,
                         biz_info: dict = None) -> list[dict]:
    def _sim_one(question: str) -> dict:
        try:
            return run_simulation(
                client_gpt, client_gemini, question, target_url,
                model_gpt, model_gemini, n=n, biz_info=biz_info,
            )
        except Exception:
            return {
                "gpt_rate": None, "gemini_rate": None, "avg_rate": None,
                "gpt_hits": None, "gemini_hits": None, "total": n,
                "gpt_ci": (None, None), "gemini_ci": (None, None),
                "gpt_samples": [], "gemini_samples": [],
            }

    results = [None] * len(questions)
    max_workers = min(len(questions), 5)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(_sim_one, q): i for i, q in enumerate(questions)}
        for future in concurrent.futures.as_completed(future_map):
            idx = future_map[future]
            try:
                results[idx] = future.result(timeout=max(120, n * 3))
            except Exception:
                results[idx] = {
                    "gpt_rate": None, "gemini_rate": None, "avg_rate": None,
                    "gpt_hits": None, "gemini_hits": None, "total": n,
                    "gpt_ci": (None, None), "gemini_ci": (None, None),
                    "gpt_samples": [], "gemini_samples": [],
                }
    return results


def run_strategy_analysis(client_gpt, client_gemini, question: str, target_url: str,
                           model_gpt: str, model_gemini,
                           biz_info: dict = None) -> dict:
    domain   = extract_domain(target_url)
    brand    = (biz_info or {}).get("brand_name", domain)
    industry = (biz_info or {}).get("industry", "디지털 서비스")
    audience = (biz_info or {}).get("target_audience", "일반 사용자")

    competitor_prompt = f"""당신은 디지털 마케팅 전문 애널리스트입니다.

질문: "{question}"

이 질문에 답변할 때 AI(ChatGPT, Gemini 등)가 자주 인용할 것으로 예상되는 상위 10개 웹사이트·브랜드를 인용 가능성 높은 순으로 나열하세요.

[조건]
- 분석 대상 브랜드: {brand} (업종: {industry}, 타겟: {audience})
- 분석 대상 브랜드의 언어와 서비스 지역을 자동 판별하여 해당 시장의 주요 경쟁사를 포함하세요.
- {domain}도 포함시키되 적절한 순위에 배치하세요.
- 각 도메인에 대해 인용 이유와 경쟁 포지션을 명시하세요.

형식 (JSON 배열만 출력, 다른 텍스트 없음):
[
  {{"rank": 1, "domain": "example.com", "brand_name": "브랜드명", "reason": "이유 20자 이내", "position": "업계1위/신흥강자/틈새전문 중 택1"}},
  ...
]"""

    competitor_result = ""
    _strategy_system = (
        "당신은 디지털 마케팅 전략 전문 컨설턴트입니다. "
        "모든 답변은 반드시 완성된 문장으로 마침표(.)로 끝맺음하세요. "
        "중간에 답변이 끊기지 않도록 완성된 기획서 형태로 서술하세요."
    )
    try:
        if client_gpt:
            competitor_result = call_gpt(client_gpt, competitor_prompt,
                                          max_tokens=1500, model=model_gpt,
                                          temperature_override=0.3,
                                          system=_strategy_system)
        elif client_gemini:
            competitor_result = call_gemini(client_gemini, competitor_prompt,
                                             max_tokens=1500, temperature_override=0.3)
    except Exception:
        pass

    competitors = []
    try:
        json_match = re.search(r'\[.*\]', competitor_result, re.DOTALL)
        if json_match:
            competitors = json.loads(json_match.group())
    except Exception:
        competitors = [
            {"rank": i+1, "domain": f"competitor{i+1}.com",
             "brand_name": f"경쟁사{i+1}", "reason": "관련 전문 사이트",
             "position": "시장 참여자"}
            for i in range(5)
        ]

    diagnosis_prompt = f"""웹사이트 {domain} ({brand}, 업종: {industry})이
질문 "{question}"에서 AI 인용 점유율이 낮은 이유를 분석하세요.

경쟁사 대비 콘텐츠·구조 문제점 3가지를 구체적으로 진단하세요. 각 항목 50자 이내.

형식 (번호 없이, 항목당 한 줄):"""

    diagnosis_result = ""
    try:
        if client_gpt:
            diagnosis_result = call_gpt(client_gpt, diagnosis_prompt,
                                         max_tokens=1200, model=model_gpt,
                                         temperature_override=0.4,
                                         system=_strategy_system)
        elif client_gemini:
            diagnosis_result = call_gemini(client_gemini, diagnosis_prompt,
                                            max_tokens=1200, temperature_override=0.4)
    except Exception:
        pass

    diagnoses = [d.strip().lstrip("•-*") for d in diagnosis_result.split("\n") if d.strip()][:3]

    keyword_prompt = f"""{brand} ({industry}) 사이트에서
현재 AI 인용 확률이 높을 것으로 예상되는 블루오션 키워드/질문 5개를 추천하세요.
경쟁이 적고 해당 사이트의 전문성이 높은 틈새 키워드 위주로 작성하세요.

형식 (키워드만, 한 줄에 하나):"""

    keyword_result = ""
    try:
        if client_gemini:
            keyword_result = call_gemini(client_gemini, keyword_prompt,
                                          max_tokens=1000, temperature_override=0.7)
        elif client_gpt:
            keyword_result = call_gpt(client_gpt, keyword_prompt,
                                       max_tokens=1000, model=model_gpt,
                                       temperature_override=0.7,
                                       system=_strategy_system)
    except Exception:
        pass

    keywords = [k.strip().lstrip("•-*1234567890. ") for k in keyword_result.split("\n") if k.strip()][:5]

    geo_prompt = f"""{domain} ({brand})이 질문 "{question}"에서
AI에게 더 잘 인용되도록 홈페이지 개선 방안 3가지를 제시하세요.
구체적인 문구 수정 또는 구조 변경 제안 포함. 각 항목 2줄 이내.

형식 (번호 포함):"""

    geo_result = ""
    try:
        if client_gpt:
            geo_result = call_gpt(client_gpt, geo_prompt, max_tokens=1500,
                                   model=model_gpt, temperature_override=0.5,
                                   system=_strategy_system)
        elif client_gemini:
            geo_result = call_gemini(client_gemini, geo_prompt, max_tokens=1500,
                                      temperature_override=0.5)
    except Exception:
        pass

    geo_guides = [g.strip() for g in re.split(r'\n(?=\d+\.)', geo_result) if g.strip()][:3]

    return {
        "competitors": competitors,
        "diagnoses":   diagnoses,
        "keywords":    keywords,
        "geo_guides":  geo_guides,
    }


# ─────────────────────────────────────────────
# 결과 시각화
# ─────────────────────────────────────────────
def render_bar_chart(results: list[dict], questions: list[str], title: str = "AI 엔진별 인용 점유율"):
    if not results:
        return

    short_questions = []
    for q in questions:
        if len(q) > 20:
            short_questions.append(q[:18] + "…")
        else:
            short_questions.append(q)

    gpt_rates    = [r.get("gpt_rate")    for r in results]
    gemini_rates = [r.get("gemini_rate") for r in results]

    has_gpt    = any(v is not None for v in gpt_rates)
    has_gemini = any(v is not None for v in gemini_rates)

    fig = go.Figure()

    if has_gpt:
        fig.add_trace(go.Bar(
            name="GPT",
            x=short_questions,
            y=[v if v is not None else 0 for v in gpt_rates],
            marker=dict(color="#111111", line=dict(color="#000000", width=1)),
            text=[f"{v:.1f}%" if v is not None else "" for v in gpt_rates],
            textposition="outside",
            textfont=dict(size=11, color="#111111", family="Plus Jakarta Sans"),
        ))

    if has_gemini:
        fig.add_trace(go.Bar(
            name="Gemini",
            x=short_questions,
            y=[v if v is not None else 0 for v in gemini_rates],
            marker=dict(color="#888888", line=dict(color="#666666", width=1)),
            text=[f"{v:.1f}%" if v is not None else "" for v in gemini_rates],
            textposition="outside",
            textfont=dict(size=11, color="#666666", family="Plus Jakarta Sans"),
        ))

    all_vals = [v for v in gpt_rates + gemini_rates if v is not None]

    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color="#111111", family="Plus Jakarta Sans"), x=0),
        barmode="group",
        bargap=0.25,
        bargroupgap=0.1,
        plot_bgcolor="rgba(245,245,245,0.8)",
        paper_bgcolor="white",
        font=dict(family="Plus Jakarta Sans", color="#111111"),
        xaxis=dict(tickfont=dict(size=11), gridcolor="#DDDDDD", title=""),
        yaxis=dict(
            title="인용 점유율 (%)",
            ticksuffix="%",
            gridcolor="#DDDDDD",
            range=[0, max(max(all_vals, default=0) + 15, 20)],
        ),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            bgcolor="rgba(255,255,255,0.8)",
            bordercolor="#DDDDDD",
            borderwidth=1,
            font=dict(size=12),
        ),
        margin=dict(t=60, b=40, l=50, r=20),
        height=380,
    )

    st.plotly_chart(fig, use_container_width=True)


# ─────────────────────────────────────────────
# SOV(Share of Voice) 차트 — 경쟁사 비교
# ─────────────────────────────────────────────
def render_sov_chart(sov_results: list[dict], title: str = "경쟁사 대비 AI 인용 점유율 (SOV)"):
    if not sov_results:
        return

    labels    = [r["label"] for r in sov_results]
    avgs      = [r.get("avg_rate", 0) or 0 for r in sov_results]
    ci_los    = [r.get("ci_lo", 0) or 0 for r in sov_results]
    ci_his    = [r.get("ci_hi", 0) or 0 for r in sov_results]
    is_target = [r.get("is_target", False) for r in sov_results]

    colors = ["#111111" if t else "#AAAAAA" for t in is_target]
    error_plus  = [max(0, h - a) for h, a in zip(ci_his, avgs)]
    error_minus = [max(0, a - l) for a, l in zip(avgs, ci_los)]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=avgs,
        y=labels,
        orientation="h",
        marker_color=colors,
        error_x=dict(
            type="data",
            symmetric=False,
            array=error_plus,
            arrayminus=error_minus,
            color="#555555",
            thickness=2,
            width=6,
        ),
        text=[f"{v:.1f}%" for v in avgs],
        textposition="outside",
        textfont=dict(size=12, color="#111111"),
    ))

    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color="#111111"), x=0),
        xaxis=dict(title="평균 AI 인용률 (%)", ticksuffix="%",
                   gridcolor="#EEEEEE", range=[0, max(avgs + [10]) + 20]),
        yaxis=dict(autorange="reversed", tickfont=dict(size=12)),
        plot_bgcolor="rgba(245,245,245,0.8)",
        paper_bgcolor="white",
        font=dict(family="Plus Jakarta Sans", color="#111111"),
        margin=dict(t=55, b=40, l=120, r=60),
        height=max(300, len(sov_results) * 55 + 100),
    )
    st.plotly_chart(fig, use_container_width=True)

    rows = []
    for r in sov_results:
        rows.append({
            "브랜드":        ("⭐ " if r["is_target"] else "") + r["label"],
            "도메인":        r.get("domain", ""),
            "GPT 점유율":   f"{r['gpt_rate']}%" if r.get("gpt_rate") is not None else "—",
            "Gemini 점유율":f"{r['gem_rate']}%" if r.get("gem_rate") is not None else "—",
            "평균 점유율":   f"{r.get('avg_rate', 0):.1f}%",
            "95% 신뢰구간": f"{r.get('ci_lo', 0):.1f}% ~ {r.get('ci_hi', 0):.1f}%",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

def render_strategy_analysis(strategy: dict, target_url: str):
    domain = extract_domain(target_url)

    st.markdown("""
    <div style="background:linear-gradient(135deg,#F0F0F0,#E8E8E8);border:1px solid #AAAAAA;
    border-radius:14px;padding:16px 20px;margin:16px 0;">
    <span style="font-size:1rem;font-weight:700;color:#111111;">📊 전략 분석 — 경쟁사 현황 및 GEO 최적화 가이드</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 🏆 AI 인용 경쟁 현황 (TOP 10)")
    competitors = strategy.get("competitors", [])
    if competitors:
        position_colors = {
            "업계1위": "#10B981", "업계 1위": "#10B981",
            "신흥강자": "#F59E0B", "신흥 강자": "#F59E0B",
            "틈새전문": "#6366F1", "틈새 전문": "#6366F1",
        }
        for comp in competitors[:10]:
            rank        = comp.get("rank", "?")
            comp_domain = comp.get("domain", "")
            brand_nm    = comp.get("brand_name", comp_domain)
            reason      = comp.get("reason", "")
            position    = comp.get("position", "")
            is_target   = domain.lower() in comp_domain.lower()
            bg     = "linear-gradient(135deg,#EEEEEE,#E0E0E0)" if is_target else "#F8F8F8"
            border = "#111111" if is_target else "#DDDDDD"
            label  = " ← 내 사이트" if is_target else ""
            pos_color = position_colors.get(position, "#888888")
            pos_badge = (f'<span style="background:{pos_color};color:white;'
                         f'padding:2px 8px;border-radius:20px;font-size:0.72rem;'
                         f'font-weight:700;margin-left:8px;">{position}</span>'
                         if position else "")
            st.markdown(f"""
            <div style="display:flex;align-items:center;justify-content:space-between;
            padding:11px 16px;border-radius:10px;margin:5px 0;
            background:{bg};border:1.5px solid {border};">
                <div style="display:flex;align-items:center;gap:12px;">
                    <div style="width:28px;height:28px;border-radius:8px;
                    background:{'linear-gradient(135deg,#111111,#444444)' if is_target else '#CCCCCC'};
                    color:white;font-weight:700;font-size:0.8rem;
                    display:flex;align-items:center;justify-content:center;">{rank}</div>
                    <span style="font-weight:{'700' if is_target else '500'};color:#111111;font-size:0.9rem;">
                    {brand_nm} <span style="color:#888;font-size:0.78rem;">({comp_domain})</span>
                    {label}{pos_badge}</span>
                </div>
                <span style="color:#666666;font-size:0.8rem;">{reason}</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("경쟁사 데이터를 불러오지 못했습니다.")

    st.markdown("<hr class='custom-divider'>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 🔬 인용 실패 원인 진단")
        diagnoses = strategy.get("diagnoses", [])
        colors = ["#111111", "#555555", "#888888"]
        icons  = ["❌", "⚡", "🔧"]
        for i, diag in enumerate(diagnoses):
            color = colors[i % len(colors)]
            icon  = icons[i % len(icons)]
            st.markdown(f"""
            <div style="background:white;border-radius:12px;padding:14px 16px;margin:8px 0;
            border-left:4px solid {color};border:1px solid #E2E8F0;
            box-shadow:0 2px 8px rgba(0,0,0,0.04);">
                <span style="font-size:0.85rem;color:#374151;">{icon} {diag}</span>
            </div>
            """, unsafe_allow_html=True)

    with col2:
        st.markdown("### 🌊 블루오션 키워드 추천")
        keywords = strategy.get("keywords", [])
        for i, kw in enumerate(keywords):
            st.markdown(f"""
            <div style="background:linear-gradient(135deg,#F5F5F5,#EEEEEE);
            border-radius:12px;padding:12px 16px;margin:8px 0;
            border:1px solid #CCCCCC;display:flex;align-items:center;gap:10px;">
                <span style="background:linear-gradient(135deg,#111111,#444444);
                color:white;padding:3px 10px;border-radius:20px;font-size:0.75rem;font-weight:700;">
                NEW</span>
                <span style="font-size:0.88rem;color:#111111;font-weight:600;">{kw}</span>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<hr class='custom-divider'>", unsafe_allow_html=True)

    st.markdown("### 📋 GEO 최적화 가이드")
    geo_guides = strategy.get("geo_guides", [])
    for i, guide in enumerate(geo_guides):
        st.markdown(f"""
        <div style="background:white;border-radius:14px;padding:18px 20px;margin:10px 0;
        border:1px solid #E2E8F0;box-shadow:0 2px 12px rgba(37,99,235,0.06);">
            <div style="display:flex;gap:12px;align-items:flex-start;">
                <div style="min-width:30px;height:30px;border-radius:8px;
                background:linear-gradient(135deg,#111111,#444444);
                color:white;font-weight:800;font-size:0.85rem;
                display:flex;align-items:center;justify-content:center;">{i + 1}</div>
                <p style="margin:0;font-size:0.88rem;color:#374151;line-height:1.6;">{guide}</p>
            </div>
        </div>
        """, unsafe_allow_html=True)


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
        st.rerun()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    openai_key  = st.text_input("OpenAI API Key", type="password", placeholder="sk-...",   key="openai_key")
    gemini_key  = st.text_input("Gemini API Key", type="password", placeholder="AIza...", key="gemini_key")

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.markdown("**🤖 모델 선택**")

    gpt_model = st.selectbox(
        "GPT 모델",
        ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
        index=0,
        help="gpt-4o-mini: 고속 정밀 분석, gpt-4o: 최고성능 심층 분석"
    )

    gemini_model_name = st.selectbox(
        "Gemini 모델",
        ["models/gemini-2.0-flash", "models/gemini-flash-latest", "models/gemini-3-flash-preview"],
        index=0,
        help="gemini-2.0-flash: 기본 권장"
    )

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.markdown("**⚙️ 시뮬레이션 설정**")
    sim_count = st.slider("시뮬레이션 횟수", min_value=10, max_value=100, value=50, step=10,
                          help="정밀 분석 모드: 설정 횟수만큼 병렬 API를 호출하여 인용 점유율을 산출합니다. 횟수가 높을수록 통계 신뢰도(95% Wilson CI)가 향상됩니다.")

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    st.markdown("**🌐 경쟁사 수 설정**")

    n_competitors = st.slider(
        "경쟁사 수",
        min_value=3, max_value=10, value=5, step=1,
        help="AI가 업종 분석 후 자동 도출할 경쟁사 수. 많을수록 SOV 분석이 풍부해지지만 시간이 소요됩니다.",
        key="n_competitors"
    )

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown("**📡 연결 상태**")

    gpt_ok    = bool(openai_key and openai_key.startswith("sk-"))
    gemini_ok = bool(gemini_key and len(gemini_key) > 10)

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        if gpt_ok:
            st.markdown("🟢 **GPT** 연결됨")
        else:
            st.markdown("⚪ **GPT** 미입력")
    with col_s2:
        if gemini_ok:
            st.markdown("🟢 **Gemini** 연결됨")
        else:
            st.markdown("🔴 **Gemini** 미연결")

    if gemini_ok and not gpt_ok:
        st.markdown("""
        <div style="background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.2);
        border-radius:8px;padding:10px 12px;margin-top:8px;font-size:0.75rem;color:rgba(255,255,255,0.75);">
        ℹ️ Gemini 단독으로 분석 가능합니다.<br>GPT 결과는 공란으로 표시됩니다.
        </div>
        """, unsafe_allow_html=True)
    elif not gemini_ok and gpt_ok:
        st.markdown("""
        <div style="background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.2);
        border-radius:8px;padding:10px 12px;margin-top:8px;font-size:0.75rem;color:rgba(255,255,255,0.75);">
        ℹ️ GPT 단독으로 분석 가능합니다.<br>Gemini 결과는 공란으로 표시됩니다.
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("""
    <div style="color:rgba(255,255,255,0.9);font-size:0.82rem;font-weight:700;margin-bottom:6px;">
    🎬 보고용 데모 모드
    </div>
    <div style="color:rgba(255,255,255,0.55);font-size:0.73rem;line-height:1.5;margin-bottom:10px;">
    API 키 없이 샘플 결과를 미리 확인합니다
    </div>
    """, unsafe_allow_html=True)

    if st.button("▶ 데모 시뮬레이션 실행", key="btn_demo_sidebar", use_container_width=True):
        st.session_state["run_demo"] = True
        st.session_state["demo_tab"] = "auto"
        st.session_state["run_demo_history"] = True


# ─────────────────────────────────────────────
# API 클라이언트 초기화
# ─────────────────────────────────────────────
def get_clients():
    client_gpt    = None
    client_gemini = None

    if openai_key and openai_key.startswith("sk-"):
        try:
            client_gpt = openai.OpenAI(api_key=openai_key)
        except Exception as e:
            st.sidebar.error(f"GPT 초기화 실패: {e}")

    if gemini_key and len(gemini_key) > 10:
        try:
            genai.configure(api_key=gemini_key)
            client_gemini = genai.GenerativeModel(gemini_model_name)
        except Exception as e:
            st.sidebar.error(f"Gemini 초기화 실패: {e}")

    return client_gpt, client_gemini


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
with col_m1:
    st.metric("분석 엔진", "GPT + Gemini", "2개 동시 비교")
with col_m2:
    st.metric("시뮬레이션", f"{sim_count}회/질문", "통계적 외삽")
with col_m3:
    api_count = (1 if gpt_ok else 0) + (1 if gemini_ok else 0)
    st.metric("API 연결", f"{api_count}/2", "엔진 활성화")
with col_m4:
    demo_active = st.session_state.get("run_demo", False)
    st.metric("데모 모드", "ON" if demo_active else "OFF", "사이드바에서 실행")

st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["🤖 자동 분석형 (AI 질문 도출)", "✏️ 수동 분석형 (키워드 직접 입력)", "📅 AI 인용 히스토리"])

client_gpt, client_gemini = get_clients()


# ─────────────────────────────────────────────
# Tab 1: 자동 분석형
# ─────────────────────────────────────────────
with tab1:
    st.markdown("""
    <div class="result-card" style="background:linear-gradient(135deg,#F5F5F5,#EEEEEE);border-color:#CCCCCC;">
        <h4 style="color:#111111;margin-bottom:6px;">🤖 AI 타겟 질문 자동 도출 방식</h4>
        <p style="color:#475569;font-size:0.88rem;margin:0;line-height:1.6;">
        사이트 URL을 입력하면 AI가 해당 사이트가 인용될 가능성이 가장 높은 질문 5개를 스스로 생성하고,<br>
        각 질문에 대해 <b>설정한 횟수(기본 50회)</b>만큼 실제 시뮬레이션을 수행하여 인용 점유율을 산출합니다.
        </p>
    </div>
    """, unsafe_allow_html=True)

    _pending_pre = st.session_state.pop("_do_pre_analyze", False)

    col_url, col_brand = st.columns([2, 1])
    with col_url:
        url_auto = st.text_input(
            "🌐 분석할 사이트 URL",
            placeholder="예) https://www.naver.com 또는 naver.com",
            key="url_auto"
        )
    with col_brand:
        if "industry_display" not in st.session_state:
            st.session_state["industry_display"] = ""
        manual_industry_input = st.text_input(
            "🏭 업종 확인·수정 (AI 자동 분석 → 직접 수정 가능)",
            value=st.session_state["industry_display"],
            placeholder="예) 퍼포먼스 마케팅 광고대행사",
            key="industry_widget",
            help="[업종 미리 분석] 버튼으로 AI가 자동으로 채워줍니다. 틀리면 직접 수정하세요."
        )
        st.session_state["industry_display"] = manual_industry_input

    col_pre, col_btn1, col_btn2 = st.columns([1, 2, 1])
    with col_pre:
        pre_analyze_clicked = st.button("🔍 업종 미리 분석", key="btn_pre_analyze",
                                        help="URL을 먼저 분석하여 업종을 자동으로 채워줍니다",
                                        use_container_width=True)
    with col_btn1:
        run_real_auto = st.button("🚀 자동 분석 시작", key="btn_auto", use_container_width=True)
    with col_btn2:
        run_demo_auto = st.button("🎬 데모 실행", key="btn_demo_auto", use_container_width=True,
                                  help="API 키 없이 샘플 결과를 확인합니다")

    question_engine = st.radio(
        "질문 도출 엔진",
        ["GPT", "Gemini"],
        horizontal=True,
        help="타겟 질문을 생성할 AI 엔진 선택"
    )

    if pre_analyze_clicked:
        if not url_auto.strip():
            st.warning("URL을 먼저 입력해주세요.")
        elif not gpt_ok and not gemini_ok:
            st.warning("API 키가 없으면 업종 미리 분석을 사용할 수 없습니다.")
        else:
            _pre_url = normalize_url(url_auto.strip())
            with st.spinner(f"🔎 {extract_domain(_pre_url)} 업종 분석 중..."):
                try:
                    _pre_biz = analyze_business_identity(
                        client_gpt, client_gemini, _pre_url, gpt_model, client_gemini
                    )
                    _detected_industry = _pre_biz.get("industry", "")
                    st.session_state["industry_display"] = _detected_industry
                    st.session_state["ai_analyzed_industry"] = _detected_industry
                    st.session_state["ai_analyzed_biz_info"] = _pre_biz
                    st.session_state["ai_analyzed_url"] = _pre_url
                    st.success(
                        f"✅ 업종 자동 분석 완료: **{_detected_industry}** "
                        f"(브랜드: {_pre_biz.get('brand_name','—')})"
                    )
                    st.info("업종이 맞지 않으면 위 입력창에서 직접 수정 후 [자동 분석 시작]을 누르세요.")
                    st.rerun()
                except Exception as e:
                    st.error(f"업종 분석 실패: {e}")

    trigger_demo = run_demo_auto or st.session_state.get("run_demo", False)
    if pre_analyze_clicked:
        pass
    elif trigger_demo:
        st.session_state["run_demo"] = False
        demo_url = url_auto.strip() if url_auto.strip() else "naver.com"
        target_url_d = normalize_url(demo_url)
        domain_d = extract_domain(target_url_d)
        demo_data = get_demo_data(target_url_d)
        questions_d = demo_data["scenario"]["questions"]
        results_d   = demo_data["scenario"]["results"]

        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#F5F5F5,#EEEEEE);border:1.5px dashed #AAAAAA;
        border-radius:14px;padding:14px 20px;margin:12px 0;display:flex;align-items:center;gap:10px;">
            <span style="font-size:1.2rem;">🎬</span>
            <div>
                <span style="font-weight:700;color:#333333;font-size:0.9rem;">데모 모드 — 샘플 데이터 표시 중</span><br>
                <span style="color:#555555;font-size:0.78rem;">실제 API를 호출하지 않습니다. 분석 대상: <b>{domain_d}</b></span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        prog = st.progress(0)
        stat = st.empty()
        for i, q in enumerate(questions_d):
            stat.markdown(f"⏳ 질문 {i+1}/{len(questions_d)} 시뮬레이션 중: *{q[:40]}...*")
            prog.progress((i + 1) / len(questions_d))
        prog.progress(1.0)
        stat.success("✅ 데모 시뮬레이션 완료!")

        st.markdown("**📝 타겟 질문 TOP 5 (샘플)**")
        for i, q in enumerate(questions_d, 1):
            st.markdown(f"""
            <div style="background:white;border-radius:10px;padding:11px 16px;margin:5px 0;
            border:1px solid #E2E8F0;display:flex;align-items:center;gap:12px;
            box-shadow:0 2px 8px rgba(37,99,235,0.05);">
                <span style="background:linear-gradient(135deg,#333333,#666666);color:white;
                min-width:26px;height:26px;border-radius:8px;font-weight:700;font-size:0.8rem;
                display:flex;align-items:center;justify-content:center;">{i}</span>
                <span style="font-size:0.9rem;color:#111111;font-weight:500;">{q}</span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        render_bar_chart(results_d, questions_d, f"[데모] '{domain_d}' 질문별 AI 인용 점유율")

        st.markdown("### 📋 질문별 상세 결과")
        for i, (q, r) in enumerate(zip(questions_d, results_d)):
            avg_rate = (r["gpt_rate"] + r["gemini_rate"]) / 2
            with st.expander(f"Q{i+1}. {q[:50]}{'...' if len(q)>50 else ''}", expanded=(i == 0)):
                c1, c2, c3 = st.columns(3)
                c1.metric("GPT 점유율",    f"{r['gpt_rate']}%",    f"{r['gpt_hits']}회/{r['total']}회")
                c2.metric("Gemini 점유율", f"{r['gemini_rate']}%", f"{r['gemini_hits']}회/{r['total']}회")
                c3.metric("평균 점유율",   f"{avg_rate:.1f}%")
                render_strategy_analysis(demo_data["strategy"], target_url_d)

    elif run_real_auto and not pre_analyze_clicked:
        if not url_auto:
            st.error("사이트 URL을 입력해주세요.")
        elif not gpt_ok and not gemini_ok:
            st.error("좌측 사이드바에서 최소 하나의 API 키(GPT 또는 Gemini)를 입력해주세요.")
        elif question_engine == "GPT" and not gpt_ok:
            st.warning("⚠️ GPT API 키가 없습니다. Gemini로 질문을 도출합니다.")
        else:
            target_url = normalize_url(url_auto)
            domain     = extract_domain(target_url)

            biz_info = {}
            with st.spinner(f"🔎 {domain} 비즈니스 실체 분석 중..."):
                st.markdown("**🔎 Step 0 — 사이트 심층 크롤링 및 비즈니스 실체 파악 중...**")
                try:
                    _cached_biz = st.session_state.get("ai_analyzed_biz_info", {})
                    _cached_url = st.session_state.get("ai_analyzed_url", "")
                    if _cached_biz and _cached_url == target_url:
                        biz_info = _cached_biz
                        st.info("ℹ️ 미리 분석된 비즈니스 정보를 재사용합니다.")
                    else:
                        biz_info = analyze_business_identity(
                            client_gpt, client_gemini, target_url, gpt_model, client_gemini
                        )
                        st.session_state["ai_analyzed_url"] = target_url

                    _user_industry = st.session_state.get("industry_display", "").strip()
                    if _user_industry:
                        biz_info["industry"] = _user_industry

                    st.success("✅ 비즈니스 분석 완료")
                    col_b1, col_b2, col_b3 = st.columns(3)
                    col_b1.metric("브랜드명", biz_info.get("brand_name", "—"),
                                  "🤖 AI 분석")
                    col_b2.metric("업종",     biz_info.get("industry", "—"),
                                  "✏️ 사용자 확정" if _user_industry else "🤖 AI 분석")
                    col_b3.metric("분류",     biz_info.get("industry_category", "—"))
                    if biz_info.get("key_services"):
                        st.caption("📋 주요 서비스: " + " · ".join(biz_info["key_services"][:5]))
                    st.markdown("<div style=\'height:10px\'></div>", unsafe_allow_html=True)
                except Exception as e:
                    st.warning(f"사이트 분석 일부 실패 (기본값으로 진행): {e}")
                    _user_industry = st.session_state.get("industry_display", "").strip()
                    if _user_industry:
                        biz_info["industry"] = _user_industry

            questions = []
            with st.spinner(f"{domain} 타겟 질문 도출 중..."):
                st.markdown("**📝 Step 2 — 브랜드·업종 맥락 기반 타겟 질문 도출 중...**")
                try:
                    questions = generate_target_questions(
                        client_gpt, client_gemini, target_url,
                        question_engine, gpt_model, client_gemini,
                        biz_info=biz_info,
                        manual_brand=biz_info.get("brand_name", ""),
                    )
                    st.success(f"✅ TOP {len(questions)}개 질문 도출 완료")
                except Exception as e:
                    st.error(f"질문 도출 실패: {e}")

            if questions:
                st.markdown("**📋 생성된 타겟 질문:**")
                for i, q in enumerate(questions, 1):
                    st.markdown(f"""
                    <div style="background:white;border-radius:10px;padding:11px 16px;margin:5px 0;
                    border:1px solid #E2E8F0;display:flex;align-items:center;gap:12px;
                    box-shadow:0 2px 8px rgba(37,99,235,0.05);">
                        <span style="background:linear-gradient(135deg,#111111,#444444);color:white;
                        min-width:26px;height:26px;border-radius:8px;font-weight:700;font-size:0.8rem;
                        display:flex;align-items:center;justify-content:center;">{i}</span>
                        <span style="font-size:0.9rem;color:#111111;font-weight:500;">{q}</span>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

                _active_engines = (1 if client_gpt else 0) + (1 if client_gemini else 0)
                _est_sec_per_q  = sim_count * 0.6 * _active_engines
                _est_total_sec  = int(_est_sec_per_q * len(questions))
                _est_str = (
                    f"{_est_total_sec}초" if _est_total_sec < 60
                    else f"{_est_total_sec // 60}분 {_est_total_sec % 60}초"
                )
                st.markdown(
                    f"**📊 Step 3 — 질문 {len(questions)}개 병렬 동시 시뮬레이션** "
                    f"<span style='color:#888;font-size:0.82rem;'>⚡ 정밀 분석 모드 — 전체 질문 동시 실행 "
                    f"({sim_count}회 × {len(questions)}개 질문 × {_active_engines}개 엔진 | 예상: ~{max(15, sim_count // 3)}초)</span>",
                    unsafe_allow_html=True
                )

                progress_bar = st.progress(0)
                status_text  = st.empty()
                time_text    = st.empty()
                _sim_start   = time.time()

                status_text.markdown(
                    f"🚀 **정밀 분석 모드** — {len(questions)}개 질문을 병렬 동시 실행 중... "
                    f"({sim_count}회 × {_active_engines}개 엔진)"
                )
                progress_bar.progress(0.1)

                all_results = run_all_simulations(
                    client_gpt, client_gemini, questions, target_url,
                    gpt_model, client_gemini, n=sim_count, biz_info=biz_info,
                )

                _total_elapsed = int(time.time() - _sim_start)
                _tel_str = f"{_total_elapsed}초" if _total_elapsed < 60 else f"{_total_elapsed // 60}분 {_total_elapsed % 60}초"
                status_text.success(f"✅ 전체 시뮬레이션 완료! (실제 소요: {_tel_str})")
                time_text.empty()
                progress_bar.progress(1.0)

                render_bar_chart(all_results, questions,
                                 f"'{biz_info.get('brand_name', domain)}' 질문별 AI 인용 점유율")

                st.markdown("### 📋 질문별 상세 결과")
                for i, (q, r) in enumerate(zip(questions, all_results)):
                    gpt_val    = f"{r['gpt_rate']}%"    if r.get('gpt_rate')    is not None else "—"
                    gemini_val = f"{r['gemini_rate']}%" if r.get('gemini_rate') is not None else "—"
                    gpt_delta    = f"{r['gpt_hits']}회/{r['total']}회"    if r.get('gpt_hits')    is not None else "미측정"
                    gemini_delta = f"{r['gemini_hits']}회/{r['total']}회" if r.get('gemini_hits') is not None else "미측정"
                    valid_rates  = [v for v in [r.get('gpt_rate'), r.get('gemini_rate')] if v is not None]
                    avg_rate     = sum(valid_rates) / len(valid_rates) if valid_rates else 0

                    gpt_ci  = r.get("gpt_ci",    (None, None))
                    gem_ci  = r.get("gemini_ci", (None, None))
                    ci_text = ""
                    if gpt_ci and gpt_ci[0] is not None:
                        ci_text += f"GPT: {gpt_ci[0]}%~{gpt_ci[1]}%  "
                    if gem_ci and gem_ci[0] is not None:
                        ci_text += f"Gemini: {gem_ci[0]}%~{gem_ci[1]}%"

                    with st.expander(f"Q{i+1}. {q[:55]}{'...' if len(q)>55 else ''}", expanded=(i == 0)):
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("GPT 점유율",    gpt_val,    gpt_delta)
                        c2.metric("Gemini 점유율", gemini_val, gemini_delta)
                        c3.metric("평균 점유율",   f"{avg_rate:.1f}%")
                        c4.metric("95% 신뢰구간",  ci_text if ci_text else "—")

                        gpt_samp = r.get("gpt_samples", [])
                        gem_samp = r.get("gemini_samples", [])
                        if gpt_samp or gem_samp:
                            with st.expander("💬 AI 인용 응답 샘플 보기", expanded=False):
                                if gpt_samp:
                                    st.markdown("**GPT 인용 응답 예시:**")
                                    for s in gpt_samp[:2]:
                                        st.markdown(f"""
                                        <div style="background:#F5F5F5;border-radius:8px;padding:10px 14px;
                                        margin:4px 0;font-size:0.82rem;color:#374151;line-height:1.6;
                                        border-left:3px solid #111111;">{s}</div>
                                        """, unsafe_allow_html=True)
                                if gem_samp:
                                    st.markdown("**Gemini 인용 응답 예시:**")
                                    for s in gem_samp[:2]:
                                        st.markdown(f"""
                                        <div style="background:#F5F5F5;border-radius:8px;padding:10px 14px;
                                        margin:4px 0;font-size:0.82rem;color:#374151;line-height:1.6;
                                        border-left:3px solid #888888;">{s}</div>
                                        """, unsafe_allow_html=True)

                        if client_gpt or client_gemini:
                            with st.spinner("전략 분석 중..."):
                                try:
                                    strategy = run_strategy_analysis(
                                        client_gpt, client_gemini, q, target_url,
                                        gpt_model, client_gemini,
                                        biz_info=biz_info,
                                    )
                                    render_strategy_analysis(strategy, target_url)
                                except Exception as e:
                                    st.warning(f"전략 분석 오류: {e}")


# ─────────────────────────────────────────────
# Tab 2: 수동 분석형
# ─────────────────────────────────────────────
with tab2:
    st.markdown("""
    <div class="result-card" style="background:linear-gradient(135deg,#F5F5F5,#EEEEEE);border-color:#CCCCCC;">
        <h4 style="color:#111111;margin-bottom:6px;">✏️ 직접 키워드/질문 입력 방식</h4>
        <p style="color:#475569;font-size:0.88rem;margin:0;line-height:1.6;">
        분석하고 싶은 키워드나 질문을 직접 입력하고 사이트 URL과 함께 제출하면,<br>
        해당 질문으로 <b>GPT와 Gemini 양 엔진에서 동시 시뮬레이션</b>을 수행하여 인용 점유율을 비교합니다.
        </p>
    </div>
    """, unsafe_allow_html=True)

    col_in1, col_in2 = st.columns([1, 1])
    with col_in1:
        url_manual = st.text_input(
            "🌐 분석할 사이트 URL",
            placeholder="예) https://www.naver.com",
            key="url_manual"
        )
    with col_in2:
        keyword_input = st.text_input(
            "🔍 키워드 / 질문",
            placeholder="예) 국내 최고의 검색엔진은 어디인가요?",
            key="keyword_input"
        )

    multi_keywords = st.text_area(
        "📝 추가 키워드 (선택사항, 한 줄에 하나씩)",
        placeholder="추가로 분석할 키워드를 입력하세요 (최대 4개)\n예:\n네이버 뉴스 서비스 설명\n네이버 쇼핑 기능",
        height=100,
        key="multi_keywords"
    )

    col_btn_m1, col_btn_m2 = st.columns([2, 1])
    with col_btn_m1:
        run_real_manual = st.button("🔬 분석 시작", key="btn_manual", use_container_width=True)
    with col_btn_m2:
        run_demo_manual = st.button("🎬 데모 실행", key="btn_demo_manual", use_container_width=True,
                                    help="API 키 없이 샘플 결과를 확인합니다")

    if run_demo_manual:
        demo_url_m = url_manual.strip() if url_manual.strip() else "coupang.com"
        target_url_dm = normalize_url(demo_url_m)
        domain_dm = extract_domain(target_url_dm)
        demo_data_m = get_demo_data(target_url_dm)
        demo_kws = demo_data_m["scenario"]["questions"][:3]
        demo_res = demo_data_m["scenario"]["results"][:3]

        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#F5F5F5,#EEEEEE);border:1.5px dashed #AAAAAA;
        border-radius:14px;padding:14px 20px;margin:12px 0;display:flex;align-items:center;gap:10px;">
            <span style="font-size:1.2rem;">🎬</span>
            <div>
                <span style="font-weight:700;color:#333333;font-size:0.9rem;">데모 모드 — 샘플 데이터 표시 중</span><br>
                <span style="color:#555555;font-size:0.78rem;">실제 API를 호출하지 않습니다. 분석 대상: <b>{domain_dm}</b></span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        prog_m = st.progress(0)
        stat_m = st.empty()
        for i, kw in enumerate(demo_kws):
            stat_m.markdown(f"⏳ 분석 중 ({i+1}/{len(demo_kws)}): *{kw[:40]}*")
            prog_m.progress((i + 1) / len(demo_kws))
        prog_m.progress(1.0)
        stat_m.success("✅ 데모 시뮬레이션 완료!")

        render_bar_chart(demo_res, demo_kws, f"[데모] '{domain_dm}' 키워드별 AI 인용 점유율")

        st.markdown("### 📊 결과 요약")
        table_data_d = []
        for kw, r in zip(demo_kws, demo_res):
            avg = (r["gpt_rate"] + r["gemini_rate"]) / 2
            table_data_d.append({
                "키워드": kw,
                "GPT 점유율": f"{r['gpt_rate']}%",
                "Gemini 점유율": f"{r['gemini_rate']}%",
                "평균 점유율": f"{avg:.1f}%",
                "상태": "✅ 양호" if avg >= 30 else ("⚡ 보통" if avg >= 10 else "❌ 개선 필요"),
            })
        st.dataframe(pd.DataFrame(table_data_d), use_container_width=True, hide_index=True)

        for i_d, kw_d in enumerate(demo_kws):
            st.markdown("---")
            st.markdown(f"### 🎯 '{kw_d}' 전략 분석")
            render_strategy_analysis(demo_data_m["strategy"], target_url_dm)

    elif run_real_manual:
        if not url_manual:
            st.error("사이트 URL을 입력해주세요.")
        elif not keyword_input:
            st.error("키워드 또는 질문을 입력해주세요.")
        elif not gpt_ok and not gemini_ok:
            st.error("좌측 사이드바에서 최소 하나의 API 키(GPT 또는 Gemini)를 입력해주세요.")
        else:
            target_url = normalize_url(url_manual)
            domain     = extract_domain(target_url)

            all_keywords = [keyword_input.strip()]
            if multi_keywords.strip():
                extra = [k.strip() for k in multi_keywords.strip().split("\n") if k.strip()]
                all_keywords.extend(extra[:4])
            all_keywords = all_keywords[:5]

            biz_info_m = {}
            with st.spinner(f"🔎 {domain} 업종 분석 중..."):
                try:
                    biz_info_m = analyze_business_identity(
                        client_gpt, client_gemini, target_url, gpt_model, client_gemini
                    )
                    st.success(f"✅ {biz_info_m.get('brand_name', domain)} | {biz_info_m.get('industry', '')} 분석 완료")
                except Exception:
                    biz_info_m = {"brand_name": domain.split(".")[0].upper(),
                                  "industry": "디지털 서비스",
                                  "core_product": "서비스", "target_audience": "일반 사용자"}

            competitors_m = []
            with st.spinner(f"🏢 경쟁사 분석 중..."):
                try:
                    competitors_m = discover_competitors(
                        client_gpt, client_gemini, biz_info_m, target_url,
                        model_gpt=gpt_model,
                        n_competitors=n_competitors,
                    )
                    st.success(f"✅ 경쟁사 {len(competitors_m)}개 도출")
                except Exception as e:
                    st.warning(f"경쟁사 도출 실패: {e}")

            st.markdown(f"**분석 대상:** `{domain}` | **키워드:** {len(all_keywords)}개")

            all_results_m = []
            progress_bar_m = st.progress(0)
            status_text_m  = st.empty()

            for idx, kw in enumerate(all_keywords):
                status_text_m.markdown(f"🔄 분석 중 ({idx+1}/{len(all_keywords)}): *{kw[:40]}*")

                def make_cb_m(idx_outer, total):
                    def cb(p):
                        progress_bar_m.progress((idx_outer + p) / total)
                    return cb

                try:
                    result = run_simulation(
                        client_gpt, client_gemini, kw, target_url,
                        gpt_model, client_gemini, n=sim_count,
                        biz_info=biz_info_m,
                        progress_callback=make_cb_m(idx, len(all_keywords))
                    )
                    all_results_m.append(result)
                except Exception as e:
                    st.warning(f"'{kw}' 분석 오류: {e}")
                    all_results_m.append({
                        "gpt_rate": None, "gemini_rate": None, "avg_rate": None,
                        "gpt_hits": None, "gemini_hits": None, "total": sim_count,
                        "gpt_ci": (None, None), "gemini_ci": (None, None),
                        "gpt_samples": [], "gemini_samples": []
                    })

            progress_bar_m.progress(1.0)
            status_text_m.success("✅ 분석 완료!")

            render_bar_chart(all_results_m, all_keywords,
                             f"'{biz_info_m.get('brand_name', domain)}' 키워드별 AI 인용 점유율")

            if competitors_m:
                st.markdown("---")
                st.markdown(f"**🏆 경쟁사 대비 인용 점유율 (SOV)**")
                st.caption(f"기준 키워드: *{all_keywords[0]}*")
                with st.spinner("SOV 시뮬레이션 중..."):
                    try:
                        sov_m = run_sov_simulation(
                            client_gpt, client_gemini,
                            all_keywords[0], target_url,
                            competitors_m, biz_info_m,
                            model_gpt=gpt_model,
                            n=max(10, sim_count // 3),
                        )
                        render_sov_chart(sov_m, f"'{biz_info_m.get('brand_name', domain)}' vs 경쟁사 SOV")
                    except Exception as e:
                        st.warning(f"SOV 분석 오류: {e}")

            st.markdown("### 📊 결과 요약")
            table_data = []
            for kw, r in zip(all_keywords, all_results_m):
                valid = [v for v in [r.get('gpt_rate'), r.get('gemini_rate')] if v is not None]
                avg   = sum(valid) / len(valid) if valid else 0
                gpt_ci  = r.get("gpt_ci", (None, None))
                gem_ci  = r.get("gemini_ci", (None, None))
                ci_str  = ""
                if gpt_ci[0] is not None:
                    ci_str = f"GPT {gpt_ci[0]}~{gpt_ci[1]}%"
                if gem_ci[0] is not None:
                    ci_str += f" / Gem {gem_ci[0]}~{gem_ci[1]}%"
                table_data.append({
                    "키워드":       kw,
                    "GPT 점유율":   f"{r['gpt_rate']}%"    if r.get('gpt_rate')    is not None else "—",
                    "Gemini 점유율":f"{r['gemini_rate']}%" if r.get('gemini_rate') is not None else "—",
                    "평균 점유율":  f"{avg:.1f}%",
                    "95% 신뢰구간": ci_str if ci_str else "—",
                    "상태": "✅ 양호" if avg >= 30 else ("⚡ 보통" if avg >= 10 else "❌ 개선 필요"),
                })
            st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)

            if all_results_m and (client_gpt or client_gemini):
                for idx_s, (kw_s, r_s) in enumerate(zip(all_keywords, all_results_m)):
                    st.markdown("---")
                    st.markdown(f"### 🎯 '{kw_s}' 전략 분석")

                    gpt_samp = r_s.get("gpt_samples", [])
                    gem_samp = r_s.get("gemini_samples", [])
                    if gpt_samp or gem_samp:
                        with st.expander("💬 AI 인용 응답 샘플", expanded=False):
                            if gpt_samp:
                                st.markdown("**GPT:**")
                                for s in gpt_samp[:2]:
                                    st.markdown(f"""<div style="background:#F5F5F5;border-radius:8px;
                                    padding:10px 14px;margin:4px 0;font-size:0.82rem;color:#374151;
                                    border-left:3px solid #111;">{s}</div>""", unsafe_allow_html=True)
                            if gem_samp:
                                st.markdown("**Gemini:**")
                                for s in gem_samp[:2]:
                                    st.markdown(f"""<div style="background:#F5F5F5;border-radius:8px;
                                    padding:10px 14px;margin:4px 0;font-size:0.82rem;color:#374151;
                                    border-left:3px solid #888;">{s}</div>""", unsafe_allow_html=True)

                    with st.spinner(f"'{kw_s}' 전략 분석 중..."):
                        try:
                            strategy = run_strategy_analysis(
                                client_gpt, client_gemini, kw_s, target_url,
                                gpt_model, client_gemini,
                                biz_info=biz_info_m,
                            )
                            render_strategy_analysis(strategy, target_url)
                        except Exception as e:
                            st.error(f"전략 분석 오류: {e}")


# ─────────────────────────────────────────────
# Tab 3: AI 인용 히스토리
# ─────────────────────────────────────────────
with tab3:
    st.markdown("""
    <div class="result-card" style="background:linear-gradient(135deg,#F5F5F5,#EEEEEE);border-color:#CCCCCC;">
        <h4 style="color:#111111;margin-bottom:6px;">📅 AI 엔진별 브랜드 인용 히스토리</h4>
        <p style="color:#475569;font-size:0.88rem;margin:0;line-height:1.6;">
        로그 파일을 업로드하거나 데모 데이터를 실행하면, Gemini · ChatGPT · Claude 각 엔진이
        선택 기간 동안 자사 브랜드를 인용한 횟수를 <b>누적 막대그래프</b>로 시각화합니다.
        </p>
    </div>
    """, unsafe_allow_html=True)

    col_h1, col_h2, col_h3 = st.columns([1.2, 1, 1.5])
    with col_h1:
        brand_name = st.text_input(
            "🏷️ 자사 브랜드명",
            placeholder="예) 네이버, Coupang, MyBrand",
            key="brand_name"
        )
    with col_h2:
        uploaded_log = st.file_uploader(
            "📂 로그 파일 업로드 (CSV)",
            type=["csv"],
            key="log_upload",
            help="date, engine, count 컬럼을 포함한 CSV"
        )
    with col_h3:
        today = datetime.date.today()
        date_range = st.date_input(
            "📆 분석 기간",
            value=(today - datetime.timedelta(days=29), today),
            key="date_range"
        )

    col_hbtn1, col_hbtn2 = st.columns([2, 1])
    with col_hbtn1:
        run_history_real = st.button("📊 히스토리 분석", key="btn_history", use_container_width=True)
    with col_hbtn2:
        run_history_demo = st.button("🎬 데모 실행", key="btn_history_demo", use_container_width=True,
                                     help="샘플 데이터로 히스토리를 즉시 확인합니다")

    def generate_history_demo(brand: str, days: int = 30) -> pd.DataFrame:
        random.seed(42)
        engines = ["ChatGPT", "Gemini", "Claude"]
        rows = []
        base_date = datetime.date.today() - datetime.timedelta(days=days - 1)
        for d in range(days):
            dt = base_date + datetime.timedelta(days=d)
            for eng in engines:
                base = {"ChatGPT": 12, "Gemini": 9, "Claude": 6}[eng]
                count = max(0, int(random.gauss(base, 3.5)))
                rows.append({"date": dt.strftime("%Y-%m-%d"), "engine": eng, "count": count})
        return pd.DataFrame(rows)

    def parse_uploaded_log(file, brand: str, date_range) -> pd.DataFrame:
        df = pd.read_csv(file)
        df.columns = [c.strip().lower() for c in df.columns]
        if "date" not in df.columns or "engine" not in df.columns or "count" not in df.columns:
            st.error("CSV에 'date', 'engine', 'count' 컬럼이 필요합니다.")
            return pd.DataFrame()
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        if len(date_range) == 2:
            start = date_range[0].strftime("%Y-%m-%d")
            end   = date_range[1].strftime("%Y-%m-%d")
            df = df[(df["date"] >= start) & (df["date"] <= end)]
        return df

    def render_history_chart(df: pd.DataFrame, brand: str):
        if df.empty:
            st.warning("표시할 데이터가 없습니다.")
            return

        pivot = df.pivot_table(index="date", columns="engine", values="count",
                               aggfunc="sum", fill_value=0).reset_index()
        pivot = pivot.sort_values("date")

        engines_present = [e for e in ["ChatGPT", "Gemini", "Claude"] if e in pivot.columns]
        colors = {"ChatGPT": "#111111", "Gemini": "#555555", "Claude": "#999999"}

        total_citations = int(df["count"].sum())
        daily_totals = df.groupby("date")["count"].sum()
        peak_date = daily_totals.idxmax() if not daily_totals.empty else "-"
        peak_count = int(daily_totals.max()) if not daily_totals.empty else 0
        unique_days = df["date"].nunique()

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("총 인용 횟수", f"{total_citations:,}회")
        m2.metric("최다 인용 일자", peak_date, f"당일 {peak_count}회")
        m3.metric("분석 일수", f"{unique_days}일")
        m4.metric("브랜드", brand if brand else "—")

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

        fig = go.Figure()
        for eng in engines_present:
            fig.add_trace(go.Bar(
                name=eng,
                x=pivot["date"],
                y=pivot[eng],
                marker_color=colors.get(eng, "#AAAAAA"),
                text=pivot[eng].apply(lambda v: str(v) if v > 0 else ""),
                textposition="inside",
                textfont=dict(size=10, color="white"),
            ))

        fig.update_layout(
            barmode="stack",
            title=dict(
                text=f"{'[' + brand + '] ' if brand else ''}AI 엔진별 브랜드 인용 횟수 추이",
                font=dict(size=16, color="#111111", family="Plus Jakarta Sans"),
                x=0,
            ),
            plot_bgcolor="rgba(245,245,245,0.8)",
            paper_bgcolor="white",
            font=dict(family="Plus Jakarta Sans", color="#111111"),
            xaxis=dict(
                title="날짜",
                tickangle=-35,
                tickfont=dict(size=10),
                gridcolor="#EEEEEE",
                tickmode="auto",
                nticks=20,
            ),
            yaxis=dict(
                title="인용 횟수 (Count)",
                gridcolor="#EEEEEE",
                rangemode="tozero",
            ),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02,
                xanchor="right", x=1,
                bgcolor="rgba(255,255,255,0.9)",
                bordercolor="#DDDDDD",
                borderwidth=1,
                font=dict(size=12),
            ),
            margin=dict(t=70, b=60, l=55, r=20),
            height=420,
            bargap=0.18,
        )
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("### 📋 엔진별 인용 요약")
        summary_rows = []
        for eng in engines_present:
            sub = df[df["engine"] == eng]
            summary_rows.append({
                "AI 엔진": eng,
                "총 인용 횟수": f"{int(sub['count'].sum()):,}회",
                "일평균": f"{sub['count'].mean():.1f}회",
                "최대 단일 일자": f"{int(sub['count'].max())}회",
                "비중": f"{sub['count'].sum() / df['count'].sum() * 100:.1f}%",
            })
        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

    trigger_history_demo = run_history_demo or st.session_state.get("run_demo_history", False)
    if trigger_history_demo:
        st.session_state["run_demo_history"] = False

        demo_brand = brand_name.strip() if brand_name.strip() else "MyBrand"
        df_demo = generate_history_demo(demo_brand, days=30)

        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#F5F5F5,#EEEEEE);border:1.5px dashed #AAAAAA;
        border-radius:14px;padding:14px 20px;margin:12px 0;display:flex;align-items:center;gap:10px;">
            <span style="font-size:1.2rem;">🎬</span>
            <div>
                <span style="font-weight:700;color:#333333;font-size:0.9rem;">데모 모드 — 최근 30일 가상 인용 데이터</span><br>
                <span style="color:#555555;font-size:0.78rem;">
                실제 로그 파일 없이 샘플 데이터를 시각화합니다. 브랜드: <b>{demo_brand}</b>
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        render_history_chart(df_demo, demo_brand)

    elif run_history_real:
        if uploaded_log is None:
            st.error("CSV 로그 파일을 업로드해주세요.")
        else:
            brand_label = brand_name.strip() if brand_name.strip() else "브랜드"
            dr = date_range if isinstance(date_range, tuple) and len(date_range) == 2 else (
                today - datetime.timedelta(days=29), today)
            df_real = parse_uploaded_log(uploaded_log, brand_label, dr)
            if not df_real.empty:
                render_history_chart(df_real, brand_label)

    else:
        st.markdown("""
        <div style="text-align:center;padding:48px 20px;color:#AAAAAA;">
            <div style="font-size:3rem;margin-bottom:12px;">📊</div>
            <div style="font-size:1rem;font-weight:600;color:#888888;margin-bottom:6px;">
            로그 파일을 업로드하거나 데모를 실행하세요
            </div>
            <div style="font-size:0.82rem;">
            CSV 형식: <code>date, engine, count</code> 컬럼 포함
            </div>
        </div>
        """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 푸터
# ─────────────────────────────────────────────
st.markdown("<div style='height:40px'></div>", unsafe_allow_html=True)
st.markdown("""
<div style="text-align:center;padding:20px;color:#888888;font-size:0.8rem;
border-top:1px solid #DDDDDD;">
    🔍 AI Citation Analyzer &nbsp;|&nbsp; GPT & Gemini 기반 AI 검색 점유율 분석 도구
</div>
""", unsafe_allow_html=True)
