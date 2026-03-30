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
# 글로벌 CSS — 다크/라이트 모드 통합 (글자 묻힘 완벽 해결)
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
else:
    _bg        = "#F5F5F5"
    _bg2       = "#EEEEEE"
    _card      = "#FFFFFF"
    _border    = "#DDDDDD"
    _text      = "#111111"
    _text_muted= "#555555"
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

/* 1. 전체 배경 & 기본 폰트 */
html, body, [class*="css"], .stApp {{
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    background-color: var(--bg) !important;
}}

/* 2. 메인 화면 텍스트 색상 강제 고정 (라이트모드 글씨 실종 완벽 차단) */
.stApp p, .stApp span, .stApp label, .stApp li, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, .stApp .markdown-text-container {{
    color: var(--text) !important;
}}

/* 3. 사이드바 강제 예외 처리 (어두운 배경이므로 항상 흰색 텍스트) */
[data-testid="stSidebar"] {{
    background: {_sidebar_gr} !important;
}}
[data-testid="stSidebar"] p, 
[data-testid="stSidebar"] span, 
[data-testid="stSidebar"] label, 
[data-testid="stSidebar"] h1, 
[data-testid="stSidebar"] h2, 
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] {{
    color: #F8FAFC !important;
}}
[data-testid="stSidebar"] .stTextInput > div > div > input,
[data-testid="stSidebar"] .stSelectbox > div > div {{
    background: rgba(255,255,255,0.08) !important;
    border: 1px solid rgba(255,255,255,0.2) !important;
    color: white !important;
}}

/* 4. 메인 헤더 영역 (어두운 그라데이션이므로 흰색 고정) */
.main-header {{
    background: {_header_gr};
    border-radius: 20px;
    padding: 36px 40px;
    margin-bottom: 28px;
    position: relative;
    overflow: hidden;
    box-shadow: {_shadow_h};
}}
.main-header h1, .main-header p, .main-header span {{
    color: white !important;
    position: relative;
    z-index: 1;
}}

/* 5. 버튼 디자인 및 텍스트 고정 */
.stButton > button {{
    background: {_btn_gr} !important;
    border: none !important;
    border-radius: 12px !important;
    box-shadow: 0 4px 16px rgba(0,0,0,0.25) !important;
}}
.stButton > button p, .stButton > button span {{
    color: white !important;
    font-weight: 700 !important;
}}

/* 6. 탭 영역 디자인 */
.stTabs [data-baseweb="tab-list"] {{
    background: {_tab_bg} !important;
    border-radius: 14px !important;
    border: 1px solid var(--border) !important;
    padding: 6px !important;
}}
.stTabs [data-baseweb="tab"] p, .stTabs [data-baseweb="tab"] span {{
    color: var(--text-muted) !important;
    font-weight: 600 !important;
}}
.stTabs [aria-selected="true"] {{
    background: {_tab_sel} !important;
    border-radius: 10px !important;
}}
.stTabs [aria-selected="true"] p, .stTabs [aria-selected="true"] span {{
    color: {"white" if not _dark else "#F0F0F0"} !important;
}}

/* 7. 메트릭 컨테이너 세부 텍스트 매핑 */
div[data-testid="metric-container"] {{
    background: var(--card) !important;
    border-radius: 14px !important;
    padding: 18px !important;
    border: 1px solid var(--border) !important;
    box-shadow: var(--shadow) !important;
}}
div[data-testid="metric-container"] label, div[data-testid="metric-container"] label p {{
    color: var(--text-muted) !important;
}}
div[data-testid="metric-container"] div[data-testid="stMetricValue"] > div {{
    color: var(--text) !important;
}}

/* 8. 입력 폼 텍스트 및 배경 */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {{
    background: {_input_bg} !important;
    border: 1.5px solid var(--border) !important;
    color: var(--text) !important;
}}

/* 9. 데이터프레임 다크모드 대응 */
.stDataFrame, [data-testid="stTable"] {{ 
    background: var(--card) !important; 
}}

/* 10. 익스팬더(아코디언) 다크모드 대응 */
{"" if not _dark else """
.stExpander { background: #1E1E1E !important; border-color: #333333 !important; }
.stExpander summary p, .stExpander summary span { color: #E0E0E0 !important; }
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

def calc_confidence_interval(hits: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    if n == 0: return 0.0, 100.0
    z   = 1.96 if confidence == 0.95 else 2.576
    p   = hits / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = (z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))) / denom
    lo = max(0.0, (center - margin) * 100)
    hi = min(100.0, (center + margin) * 100)
    return round(lo, 1), round(hi, 1)

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
# Jina Reader 기반 경쟁사 검색 컨텍스트 수집
# ─────────────────────────────────────────────
def fetch_competitor_search_context(industry: str, brand: str, market_scope: str) -> str:
    scope_kw = "한국 국내" if "국내" in market_scope else "글로벌"
    queries = [
        f"{industry} 경쟁사 {scope_kw}",
        f"{brand} 경쟁사 대안 서비스",
    ]
    collected = []
    headers = {"Accept": "text/markdown, text/plain, */*", "X-Return-Format": "markdown", "X-Timeout": "10"}
    for q in queries:
        try:
            search_url = f"https://r.jina.ai/https://www.google.com/search?q={requests.utils.quote(q)}&hl=ko"
            resp = requests.get(search_url, headers=headers, timeout=15)
            if resp.status_code == 200 and len(resp.text) > 300:
                collected.append(f"[검색: {q}]\n{resp.text[:3000]}")
        except Exception:
            continue
    return "\n\n".join(collected)[:8000]

def discover_competitors(client_gpt, client_gemini, biz_info: dict, target_url: str,
                          market_scope: str, model_gpt: str, n_competitors: int = 5) -> list[dict]:
    brand    = biz_info.get("brand_name", extract_domain(target_url))
    industry = biz_info.get("industry", "디지털 서비스")
    domain   = extract_domain(target_url)

    scope_instruction = (
        "반드시 대한민국에서 서비스 중인 국내 기업만 포함하세요. 해외 기업은 제외합니다."
        if "국내" in market_scope else "전 세계 글로벌 시장에서 활동하는 기업을 포함하세요."
    )

    search_context = fetch_competitor_search_context(industry, brand, market_scope)
    prompt = f"""당신은 디지털 마케팅 업계 전문 애널리스트입니다.
아래 데이터를 바탕으로 실제 경쟁사를 분석하세요.
[도메인]: {domain} / [업종]: {industry} / [브랜드]: {brand}
[검색 결과]\n{search_context[:3000]}

[출력 형식 - 순수 JSON 배열만 출력]
[{{ "rank": 1, "brand_name": "A사", "domain": "a.com", "reason": "경쟁 이유", "domain_valid": true, "is_direct_competitor": true }}]
조건: {scope_instruction} 본인 도메인은 제외. 정확히 {n_competitors}개 도출.
"""
    result_str = ""
    try:
        if client_gpt:
            result_str = call_gpt(client_gpt, prompt, max_tokens=1000, model=model_gpt, temperature_override=0.2)
        elif client_gemini:
            result_str = call_gemini(client_gemini, prompt, max_tokens=1000, temperature_override=0.2)
    except Exception:
        pass

    competitors = []
    try:
        json_match = re.search(r'\[.*\]', result_str, re.DOTALL)
        if json_match:
            raw = json.loads(json_match.group())
            competitors = [c for c in raw if c.get("domain", "").strip() and "competitor" not in c.get("domain", "").lower()]
    except Exception:
        pass

    if not competitors:
        competitors = [{"rank": i+1, "brand_name": f"경쟁사 {i+1}", "domain": f"comp{i+1}.com", "reason": "업계 경쟁사", "domain_valid": False} for i in range(n_competitors)]
    return competitors[:n_competitors]

def run_sov_simulation(client_gpt, client_gemini, question: str, target_url: str,
                        competitor_list: list[dict], biz_info: dict, model_gpt: str, n: int = 30) -> dict:
    all_urls = [target_url] + [normalize_url(c.get("domain", "")) for c in competitor_list if c.get("domain", "").strip()]
    all_labels = [biz_info.get("brand_name", extract_domain(target_url))] + [c.get("brand_name", c.get("domain", "")) for c in competitor_list]

    def _sim_one_brand(url: str, brand_variants: list[str]) -> dict:
        gpt_hits, gem_hits, gpt_ran, gem_ran = 0, 0, False, False

        def _gpt_batch():
            h = 0
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
                futs = [ex.submit(call_gpt, client_gpt, f"질문: {question}\n\n답변:", max_tokens=150, model=model_gpt, temperature_override=0.5) for _ in range(n)]
                for f in concurrent.futures.as_completed(futs):
                    try:
                        res = f.result(timeout=10)
                        if any(v in res.lower() for v in brand_variants): h += 1
                    except Exception: pass
            return h

        def _gem_batch():
            h = 0
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
                futs = [ex.submit(call_gemini, client_gemini, f"질문: {question}\n\n답변:", max_tokens=150, temperature_override=0.5) for _ in range(n)]
                for f in concurrent.futures.as_completed(futs):
                    try:
                        res = f.result(timeout=10)
                        if any(v in res.lower() for v in brand_variants): h += 1
                    except Exception: pass
            return h

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            f_gpt = ex.submit(_gpt_batch) if client_gpt else None
            f_gem = ex.submit(_gem_batch) if client_gemini else None
            if f_gpt:
                try: gpt_hits = f_gpt.result(timeout=max(60, n*2)); gpt_ran = True
                except Exception: pass
            if f_gem:
                try: gem_hits = f_gem.result(timeout=max(60, n*2)); gem_ran = True
                except Exception: pass

        gpt_rate = round(gpt_hits / n * 100, 1) if gpt_ran else None
        gem_rate = round(gem_hits / n * 100, 1) if gem_ran else None
        valid = [v for v in [gpt_rate, gem_rate] if v is not None]
        avg = round(sum(valid) / max(1, len(valid)), 1) if valid else 0
        ci_lo, ci_hi = calc_confidence_interval((gpt_hits if gpt_ran else 0) + (gem_hits if gem_ran else 0), (n if gpt_ran else 0) + (n if gem_ran else 0))
        
        return {"gpt_rate": gpt_rate, "gem_rate": gem_rate, "avg_rate": avg, "ci_lo": ci_lo, "ci_hi": ci_hi}

    sov_results = []
    for i, (url, label) in enumerate(zip(all_urls, all_labels)):
        brand_biz = biz_info if i == 0 else {"brand_name": label, "industry": biz_info.get("industry", "")}
        res = _sim_one_brand(url, build_brand_variants(url, brand_biz))
        res.update({"label": label, "domain": extract_domain(url), "is_target": (i == 0)})
        sov_results.append(res)
    return sov_results

# ─────────────────────────────────────────────
# 사이트 크롤링 및 비즈니스 분석
# ─────────────────────────────────────────────
class _MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title, self.description, self.og_title, self.og_description, self._in_title = "", "", "", "", False
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "title": self._in_title = True
        if tag == "meta":
            name, prop, content = d.get("name", "").lower(), d.get("property", "").lower(), d.get("content", "")
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
            desc = " ".join([line.strip() for line in lines if line.strip() and not line.strip().startswith("#")][:5])
            return {"title": title, "description": desc[:500], "html_snippet": resp.text[:6000], "crawl_ok": True}
    except Exception: pass

    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10, allow_redirects=True)
        resp.encoding = resp.apparent_encoding or "utf-8"
        if len(resp.text) > 500 and "자동등록방지" not in resp.text:
            p = _MetaParser(); p.feed(resp.text[:80000])
            return {"title": p.og_title or p.title or "", "description": p.og_description or p.description or "", "html_snippet": resp.text[:4000], "crawl_ok": True}
    except Exception: pass
    return {"title": "", "description": "", "html_snippet": "", "crawl_ok": False}

def analyze_business_identity(client_gpt, client_gemini, url: str, model_gpt: str, model_gemini) -> dict:
    meta = crawl_site_metadata(url)
    domain = extract_domain(url)
    domain_stem = domain.split(".")[0]

    prompt = f"""당신은 비즈니스 인텔리전스 전문가입니다. 사이트를 정밀 분석하세요.
[도메인]: {domain}
[크롤링]: {meta.get('title', '')} / {meta.get('description', '')}

[지침]
크롤링 데이터가 없어도 도메인명({domain})과 사전 지식으로 어떤 비즈니스를 하는지 명확한 업종명을 추론하세요. (예: avahair.co.kr -> 미용실 프랜차이즈)
JSON만 출력: {{"brand_name":"회사명", "industry":"실물 업종명", "industry_category":"대분류", "core_product":"핵심 서비스", "target_audience":"타겟층", "key_services":["A", "B"]}}"""

    result_str = ""
    try:
        if client_gpt: result_str = call_gpt(client_gpt, prompt, max_tokens=600, model=model_gpt, temperature_override=0.2)
        elif client_gemini: result_str = call_gemini(client_gemini, prompt, max_tokens=600, temperature_override=0.2)
        
        m = re.search(r'\{.*\}', result_str, re.DOTALL)
        if m: return json.loads(m.group())
    except Exception: pass

    return {"brand_name": domain_stem.upper(), "industry": "비즈니스 서비스", "industry_category": "기타", "core_product": "서비스", "target_audience": "고객", "key_services": []}

# ─────────────────────────────────────────────
# API 호출
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
# 질문 생성 & 시뮬레이션
# ─────────────────────────────────────────────
def generate_target_questions(client_gpt, client_gemini, url: str, engine: str, model_gpt: str, model_gemini, biz_info: dict = None) -> list[str]:
    brand = biz_info.get("brand_name", extract_domain(url))
    industry = biz_info.get("industry", "서비스")
    product = biz_info.get("core_product", "서비스")

    prompt = f"""당신은 {industry} 분야 마케터입니다.
{brand}({product})의 실제 고객이 챗봇에 입력할 매우 구체적이고 현실적인 구매 여정 질문 5개를 창의적으로 도출하세요.
뻔한 템플릿 질문 금지. 업계 실무 용어 및 구체적 상황을 포함하세요. 
질문 안에 '{brand}'를 포함.
다른 텍스트 없이 질문 5개만 한 줄씩 물음표로 끝나게 출력하세요."""

    res = ""
    try:
        if engine == "GPT" and client_gpt: res = call_gpt(client_gpt, prompt, max_tokens=800, model=model_gpt, temperature_override=0.8)
        elif engine == "Gemini" and client_gemini: res = call_gemini(client_gemini, prompt, max_tokens=800, temperature_override=0.8)
        elif client_gpt: res = call_gpt(client_gpt, prompt, max_tokens=800, model=model_gpt, temperature_override=0.8)
        elif client_gemini: res = call_gemini(client_gemini, prompt, max_tokens=800, temperature_override=0.8)
    except Exception: pass

    qs = [re.sub(r'^[\d\.\-\*\[\]\s]+', '', q).strip() for q in res.split('\n') if '?' in q]
    qs = [q for q in qs if len(q) > 5][:5]
    
    if not qs:
        qs = [f"{brand}의 {industry} 주요 서비스 특징은 무엇인가요?", f"{brand} 이용 시 비용 구조는 어떤가요?", f"{brand}의 실제 사용 후기는 어떤가요?"]
    return qs[:5]

def simulate_single_gpt(client, question: str, url: str, model: str, bv: list) -> dict:
    try:
        res = call_gpt(client, f"질문: {question}\n\n답변:", max_tokens=150, model=model, temperature_override=0.5)
        cited = any(v.lower() in res.lower() for v in bv)
        return {"cited": cited, "response_sample": res[:200] if cited else ""}
    except Exception: return {"cited": False, "response_sample": ""}

def simulate_single_gemini(model_obj, question: str, url: str, bv: list) -> dict:
    try:
        res = call_gemini(model_obj, f"질문: {question}\n\n답변:", max_tokens=150, temperature_override=0.5)
        cited = any(v.lower() in res.lower() for v in bv)
        return {"cited": cited, "response_sample": res[:200] if cited else ""}
    except Exception: return {"cited": False, "response_sample": ""}

def run_simulation(client_gpt, client_gemini, question: str, target_url: str, model_gpt: str, model_gemini, n: int = 50, biz_info: dict = None, progress_callback=None) -> dict:
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
            try: gpt_h, g_samp = f_gpt.result(timeout=max(120, n*2)); gpt_r = True
            except Exception: pass
        if f_gem:
            try: gem_h, m_samp = f_gem.result(timeout=max(120, n*2)); gem_r = True
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
            try: results[fmap[f]] = f.result(timeout=max(120, n * 3))
            except Exception: results[fmap[f]] = {"gpt_rate": None, "gemini_rate": None, "avg_rate": 0, "gpt_hits": 0, "gemini_hits": 0, "total": n, "gpt_ci": (None, None), "gemini_ci": (None, None), "gpt_samples": [], "gemini_samples": []}
    return results

def run_strategy_analysis(client_gpt, client_gemini, question: str, target_url: str,
                           model_gpt: str, model_gemini, biz_info: dict = None, market_scope: str = "글로벌") -> dict:
    domain, brand, industry = extract_domain(target_url), (biz_info or {}).get("brand_name", extract_domain(target_url)), (biz_info or {}).get("industry", "서비스")
    scope_instruction = "대한민국에서 서비스하는 국내 기업만 포함하세요." if "국내" in market_scope else "국내외 글로벌 기업을 모두 포함하세요."

    sys_msg = "완성된 문장으로 마침표(.)로 끝맺으세요."
    p_comp = f"질문: '{question}' 에 답변할 때 AI가 인용할 상위 10개 경쟁사 도메인을 분석하세요.\n조건: {scope_instruction}\n출력: [{{\"rank\":1, \"domain\":\"a.com\", \"brand_name\":\"A사\", \"reason\":\"이유\"}}]"
    p_diag = f"[{brand}]이 질문 '{question}'에서 AI 인용 점유율이 낮은 이유를 분석. 문제점 3가지 (번호 없이 한 줄씩)"
    p_kw = f"[{brand}]({industry}) 사이트에서 AI 인용 확률이 높을 블루오션 틈새 질문/키워드 5개 추천 (한 줄씩)"
    p_geo = f"[{domain}]이 질문 '{question}'에서 잘 인용되도록 홈페이지 구조/문구 개선 방안 3가지 (번호 포함)"

    def _call(p):
        try:
            if client_gpt: return call_gpt(client_gpt, p, system=sys_msg, model=model_gpt, max_tokens=800)
            if client_gemini: return call_gemini(client_gemini, p, max_tokens=800)
        except Exception: pass
        return ""

    comps = []
    try:
        m = re.search(r'\[.*\]', _call(p_comp), re.DOTALL)
        if m: comps = json.loads(m.group())
    except Exception: pass

    return {
        "competitors": comps,
        "diagnoses": [d.strip().lstrip("•-*") for d in _call(p_diag).split("\n") if d.strip()][:3],
        "keywords": [k.strip().lstrip("•-*1234567890. ") for k in _call(p_kw).split("\n") if k.strip()][:5],
        "geo_guides": [g.strip() for g in re.split(r'\n(?=\d+\.)', _call(p_geo)) if g.strip()][:3],
    }

# ─────────────────────────────────────────────
# 렌더링 UI
# ─────────────────────────────────────────────
def render_bar_chart(results: list[dict], questions: list[str], title: str):
    if not results: return
    short_questions = [q[:18] + "…" if len(q) > 20 else q for q in questions]

    fig = go.Figure()
    
    # ── 다크/라이트 텍스트 컬러 변수 ──
    _color_text = "#F0F0F0" if st.session_state.get("dark_mode") else "#111111"
    _color_grid = "#333333" if st.session_state.get("dark_mode") else "#DDDDDD"

    if any(r.get("gpt_rate") is not None for r in results):
        y_vals = [r.get("gpt_rate") or 0 for r in results]
        fig.add_trace(go.Bar(name="GPT", x=short_questions, y=y_vals, marker=dict(color="#111111" if not st.session_state.get("dark_mode") else "#E0E0E0", line=dict(color="#000000", width=1)), text=[f"{v}%" if v is not None else "" for v in y_vals], textposition="outside", textfont=dict(size=11, color=_color_text, family="Plus Jakarta Sans")))
    if any(r.get("gemini_rate") is not None for r in results):
        y_vals = [r.get("gemini_rate") or 0 for r in results]
        fig.add_trace(go.Bar(name="Gemini", x=short_questions, y=y_vals, marker=dict(color="#888888", line=dict(color="#666666", width=1)), text=[f"{v}%" if v is not None else "" for v in y_vals], textposition="outside", textfont=dict(size=11, color=_color_text, family="Plus Jakarta Sans")))

    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color=_color_text, family="Plus Jakarta Sans"), x=0),
        barmode="group", bargap=0.25, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Plus Jakarta Sans", color=_color_text),
        xaxis=dict(tickfont=dict(size=11), gridcolor=_color_grid, title=""),
        yaxis=dict(title="인용 점유율 (%)", ticksuffix="%", gridcolor=_color_grid),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor="rgba(0,0,0,0)"),
        margin=dict(t=60, b=40, l=50, r=20), height=380,
    )
    st.plotly_chart(fig, use_container_width=True)

def render_sov_chart(sov_results: list[dict], title: str):
    if not sov_results: return
    labels = [r["label"] for r in sov_results]
    avgs = [r.get("avg_rate", 0) for r in sov_results]
    
    _color_text = "#F0F0F0" if st.session_state.get("dark_mode") else "#111111"
    _color_grid = "#333333" if st.session_state.get("dark_mode") else "#DDDDDD"
    colors = ["#111111" if not st.session_state.get("dark_mode") else "#E0E0E0" if r.get("is_target") else "#AAAAAA" for r in sov_results]

    fig = go.Figure(go.Bar(x=avgs, y=labels, orientation="h", marker_color=colors, text=[f"{v:.1f}%" for v in avgs], textposition="outside", textfont=dict(size=12, color=_color_text)))
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color=_color_text), x=0),
        xaxis=dict(title="평균 AI 인용률 (%)", ticksuffix="%", gridcolor=_color_grid),
        yaxis=dict(autorange="reversed", tickfont=dict(size=12)),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Plus Jakarta Sans", color=_color_text),
        margin=dict(t=55, b=40, l=120, r=60), height=max(300, len(sov_results) * 55 + 100),
    )
    st.plotly_chart(fig, use_container_width=True)

    rows = [{"브랜드": ("⭐ " if r["is_target"] else "") + r["label"], "도메인": r.get("domain", ""), "GPT 점유율": f"{r['gpt_rate']}%" if r.get("gpt_rate") is not None else "—", "Gemini 점유율": f"{r['gem_rate']}%" if r.get("gem_rate") is not None else "—", "평균 점유율": f"{r.get('avg_rate', 0):.1f}%"} for r in sov_results]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

def render_strategy_analysis(strategy: dict, target_url: str):
    domain = extract_domain(target_url)

    st.markdown("""
    <div style="background:var(--bg2);border:1px solid var(--border);border-radius:14px;padding:16px 20px;margin:16px 0;">
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
        try: st.rerun()
        except AttributeError: st.experimental_rerun()

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
    with col_s1: st.markdown("🟢 **GPT** 연결됨" if gpt_ok else "⚪ **GPT** 미입력")
    with col_s2: st.markdown("🟢 **Gemini** 연결됨" if gemini_ok else "🔴 **Gemini** 미연결")

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

client_gpt, client_gemini = get_clients()

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

# ─────────────────────────────────────────────
# Tab 1: 자동 분석형
# ─────────────────────────────────────────────
with tab1:
    st.markdown("""
    <div class="result-card" style="background:var(--card);border-color:var(--border);">
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
    <div class="result-card" style="background:var(--card);border-color:var(--border);">
        <h4 style="color:var(--text);margin-bottom:6px;">✏️ 직접 키워드/질문 입력 방식</h4>
        <p style="color:var(--text-muted);font-size:0.88rem;margin:0;line-height:1.6;">
        분석하고 싶은 키워드나 질문을 직접 입력하고 제출하면 양 엔진에서 동시 시뮬레이션을 수행합니다.
        </p>
    </div>
    """, unsafe_allow_html=True)

    c_m1, c_m2 = st.columns(2)
    url_manual = c_m1.text_input("🌐 사이트 URL", key="m_url")
    kw_manual = c_m2.text_input("🔍 메인 키워드 / 질문", key="m_kw")
    
    if st.button("🔬 수동 검증 시작", use_container_width=True):
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
    st.markdown("""
    <div class="result-card" style="background:var(--card);border-color:var(--border);">
        <h4 style="color:var(--text);margin-bottom:6px;">📅 AI 엔진별 브랜드 인용 히스토리</h4>
        <p style="color:var(--text-muted);font-size:0.88rem;margin:0;line-height:1.6;">
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
        colors = {"ChatGPT": "#111111" if not _dark else "#E0E0E0", "Gemini": "#555555", "Claude": "#999999"}

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

        _color_text = "#F0F0F0" if st.session_state.get("dark_mode") else "#111111"
        _color_grid = "#333333" if st.session_state.get("dark_mode") else "#DDDDDD"

        fig = go.Figure()
        for eng in engines_present:
            fig.add_trace(go.Bar(
                name=eng,
                x=pivot["date"],
                y=pivot[eng],
                marker_color=colors.get(eng, "#AAAAAA"),
                text=pivot[eng].apply(lambda v: str(v) if v > 0 else ""),
                textposition="inside",
                textfont=dict(size=10, color="white" if eng != "ChatGPT" or _dark else "#111111"),
            ))

        fig.update_layout(
            barmode="stack",
            title=dict(
                text=f"{'[' + brand + '] ' if brand else ''}AI 엔진별 브랜드 인용 횟수 추이",
                font=dict(size=16, color=_color_text, family="Plus Jakarta Sans"),
                x=0,
            ),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Plus Jakarta Sans", color=_color_text),
            xaxis=dict(
                title="날짜",
                tickangle=-35,
                tickfont=dict(size=10),
                gridcolor=_color_grid,
                tickmode="auto",
                nticks=20,
            ),
            yaxis=dict(
                title="인용 횟수 (Count)",
                gridcolor=_color_grid,
                rangemode="tozero",
            ),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02,
                xanchor="right", x=1,
                bgcolor="rgba(0,0,0,0)",
                bordercolor=_color_grid,
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
        <div style="background:var(--bg2);border:1.5px dashed var(--border);
        border-radius:14px;padding:14px 20px;margin:12px 0;display:flex;align-items:center;gap:10px;">
            <span style="font-size:1.2rem;">🎬</span>
            <div>
                <span style="font-weight:700;color:var(--text);font-size:0.9rem;">데모 모드 — 최근 30일 가상 인용 데이터</span><br>
                <span style="color:var(--text-muted);font-size:0.78rem;">
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
        <div style="text-align:center;padding:48px 20px;color:var(--text-muted);">
            <div style="font-size:3rem;margin-bottom:12px;">📊</div>
            <div style="font-size:1rem;font-weight:600;color:var(--text-muted);margin-bottom:6px;">
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
<div style="text-align:center;padding:20px;color:var(--text-muted);font-size:0.8rem;border-top:1px solid var(--border);">
    🔍 AI Citation Analyzer &nbsp;|&nbsp; GPT & Gemini 기반 AI 검색 점유율 분석 도구
</div>
""", unsafe_allow_html=True)
