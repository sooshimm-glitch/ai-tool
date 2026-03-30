"""
AI 검색 점유율 분석 대시보드
============================
GPT & Gemini 기반 AI 인용 점유율 분석 도구 (Enterprise Edition)
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
# 글로벌 AI 모델 고정 (UI에서 숨기고 자동화)
# ─────────────────────────────────────────────
GPT_MODEL = "gpt-4o-mini"
GEMINI_MODEL = "models/gemini-2.0-flash"

# ─────────────────────────────────────────────
# 페이지 설정
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="AI Citation Analyzer",
    page_icon="📊",
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
# 고급 엔터프라이즈 SaaS 테마 CSS
# ─────────────────────────────────────────────
if _dark:
    _bg        = "#0F172A"  # Slate 900
    _bg2       = "#1E293B"  # Slate 800
    _card      = "#1E293B"  
    _border    = "#334155"  # Slate 700
    _text      = "#F8FAFC"  # Slate 50
    _text_muted= "#94A3B8"  # Slate 400
    _primary   = "#3B82F6"  # Blue 500
    _accent    = "#6366F1"  # Indigo 500
    _shadow    = "0 4px 6px -1px rgba(0,0,0,0.5), 0 2px 4px -2px rgba(0,0,0,0.5)"
    _shadow_h  = "0 10px 15px -3px rgba(0,0,0,0.5), 0 4px 6px -4px rgba(0,0,0,0.5)"
    _header_gr = "linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%)"
    _sidebar_gr= "linear-gradient(180deg, #0F172A 0%, #1E293B 100%)"
    _btn_gr    = "linear-gradient(135deg, #2563EB, #4F46E5)"
else:
    _bg        = "#F8FAFC"  # Slate 50
    _bg2       = "#F1F5F9"  # Slate 100
    _card      = "#FFFFFF"
    _border    = "#E2E8F0"  # Slate 200
    _text      = "#0F172A"  # Slate 900
    _text_muted= "#64748B"  # Slate 500
    _primary   = "#2563EB"  # Blue 600
    _accent    = "#4F46E5"  # Indigo 600
    _shadow    = "0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -2px rgba(0,0,0,0.025)"
    _shadow_h  = "0 10px 15px -3px rgba(0,0,0,0.08), 0 4px 6px -4px rgba(0,0,0,0.04)"
    _header_gr = "linear-gradient(135deg, #1E3A8A 0%, #2563EB 100%)"
    _sidebar_gr= "linear-gradient(180deg, #1E293B 0%, #0F172A 100%)"
    _btn_gr    = "linear-gradient(135deg, #2563EB, #4F46E5)"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@300;400;500;600;700;800&display=swap');

:root {{
    --bg: {_bg};
    --card: {_card};
    --border: {_border};
    --text: {_text};
    --text-muted: {_text_muted};
    --primary: {_primary};
}}

html, body, [class*="css"] {{
    font-family: 'Pretendard', sans-serif !important;
    background-color: var(--bg) !important;
    color: var(--text) !important;
}}
.stApp {{ background: var(--bg) !important; }}

/* ── 메인 헤더 (고급스러운 블루 그라데이션) ── */
.main-header {{
    background: {_header_gr};
    border-radius: 16px;
    padding: 32px 40px;
    margin-bottom: 30px;
    position: relative;
    overflow: hidden;
    box-shadow: {_shadow_h};
    color: white;
}}
.main-header::after {{
    content: ''; position: absolute; right: -50px; top: -50px;
    width: 200px; height: 200px; background: rgba(255,255,255,0.1);
    border-radius: 50%;
}}
.main-header h1 {{ color: white !important; font-size: 2.2rem !important; font-weight: 800 !important; margin: 0 0 8px 0 !important; letter-spacing: -0.5px; z-index: 2; position: relative; }}
.main-header p {{ color: rgba(255,255,255,0.85) !important; font-size: 1.05rem !important; margin: 0 !important; z-index: 2; position: relative; }}

/* ── 카드 디자인 ── */
.metric-card, .result-card {{
    background: var(--card) !important;
    border-radius: 16px;
    padding: 24px;
    border: 1px solid var(--border);
    box-shadow: {_shadow};
    color: var(--text);
}}

/* ── 탭 디자인 ── */
.stTabs [data-baseweb="tab-list"] {{
    background: {_bg2} !important;
    border-radius: 12px !important;
    padding: 6px !important;
    border: 1px solid var(--border) !important;
}}
.stTabs [data-baseweb="tab"] {{
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    color: var(--text-muted) !important;
    padding: 10px 24px !important;
}}
.stTabs [aria-selected="true"] {{
    background: var(--card) !important;
    color: var(--primary) !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05) !important;
}}

/* ── 인풋 필드 ── */
.stTextInput > div > div > input, .stTextArea > div > div > textarea {{
    border-radius: 10px !important;
    border: 1.5px solid var(--border) !important;
    background: var(--card) !important;
    color: var(--text) !important;
    padding: 12px 16px !important;
    font-size: 0.95rem !important;
}}
.stTextInput > div > div > input:focus {{ border-color: var(--primary) !important; box-shadow: 0 0 0 3px rgba(37,99,235,0.15) !important; }}

/* ── 버튼 디자인 (Call to Action) ── */
.stButton > button {{
    background: {_btn_gr} !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    padding: 12px 24px !important;
    box-shadow: 0 4px 12px rgba(37,99,235,0.2) !important;
    transition: all 0.2s ease !important;
}}
.stButton > button:hover {{ transform: translateY(-2px) !important; box-shadow: 0 6px 16px rgba(37,99,235,0.3) !important; }}

/* ── 사이드바 ── */
[data-testid="stSidebar"] {{ background: {_sidebar_gr} !important; border-right: none !important; }}
[data-testid="stSidebar"] * {{ color: #F8FAFC !important; }}
[data-testid="stSidebar"] .stTextInput > div > div > input {{ background: rgba(255,255,255,0.05) !important; border: 1px solid rgba(255,255,255,0.1) !important; color: white !important; }}

div[data-testid="metric-container"] {{
    background: var(--card) !important;
    border-radius: 12px !important;
    padding: 16px 20px !important;
    border: 1px solid var(--border) !important;
    box-shadow: {_shadow} !important;
}}
div[data-testid="metric-container"] label {{ color: var(--text-muted) !important; font-weight: 600 !important; }}
div[data-testid="metric-container"] div {{ color: var(--text) !important; }}

{"" if not _dark else """
.stMarkdown, .stMarkdown p, .stMarkdown li { color: #E2E8F0 !important; }
.stExpander { background: #1E293B !important; border-color: #334155 !important; }
.stDataFrame { background: #1E293B !important; }
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

    if brand_name:
        words = brand_name.split()
        if len(words) >= 2:
            abbrev = "".join(w[0] for w in words if w).lower()
            if len(abbrev) >= 2:
                variants.add(abbrev)

    for v in list(variants):
        if re.search(r'[가-힣]', v) and brand_name and re.search(r'[a-zA-Z]', brand_name):
            variants.add(brand_name.lower())

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
# Jina Reader 검색 수집 & 경쟁사 도출
# ─────────────────────────────────────────────
def fetch_competitor_search_context(industry: str, brand: str) -> str:
    queries = [f"{industry} 주요 경쟁사", f"{brand} 경쟁사 대안 서비스"]
    collected = []
    headers = {"Accept": "text/markdown", "X-Timeout": "10"}
    for q in queries:
        try:
            search_url = f"https://r.jina.ai/https://www.google.com/search?q={requests.utils.quote(q)}&hl=ko"
            resp = requests.get(search_url, headers=headers, timeout=10)
            if resp.status_code == 200 and len(resp.text) > 300:
                collected.append(f"[검색: {q}]\n{resp.text[:3000]}")
        except: pass
    return "\n\n".join(collected)[:8000]

def discover_competitors(client_gpt, client_gemini, biz_info: dict, target_url: str, n_competitors: int = 5) -> list[dict]:
    brand    = biz_info.get("brand_name", extract_domain(target_url))
    industry = biz_info.get("industry", "비즈니스 서비스")
    domain   = extract_domain(target_url)

    search_context = fetch_competitor_search_context(industry, brand)
    
    prompt = f"""디지털 마케팅 애널리스트로서 {brand}({industry})의 실제 경쟁사를 도출하세요.
[검색 맥락]\n{search_context[:3000]}\n
- {brand}와 동일 시장에서 파이가 겹치는 실제 서비스 5개를 JSON 배열로 출력. (본인 도메인 제외)
형식: [{{"rank":1, "brand_name":"A사", "domain":"a.com", "reason":"동일 타겟층 공략", "is_direct_competitor":true}}]"""

    result_str = ""
    try:
        if client_gpt:
            result_str = call_gpt(client_gpt, prompt, max_tokens=1000, model=GPT_MODEL, temperature_override=0.2)
        elif client_gemini:
            result_str = call_gemini(client_gemini, prompt, max_tokens=1000, temperature_override=0.2)
    except: pass

    competitors = []
    try:
        json_match = re.search(r'\[.*\]', result_str, re.DOTALL)
        if json_match:
            raw = json.loads(json_match.group())
            competitors = [c for c in raw if c.get("domain", "").strip() and c.get("domain") != domain][:n_competitors]
    except: pass

    if not competitors:
        competitors = [{"rank": i+1, "brand_name": f"경쟁사 {i+1}", "domain": f"comp{i+1}.com", "reason": "업계 경쟁사"} for i in range(n_competitors)]
    return competitors

def run_sov_simulation(client_gpt, client_gemini, question: str, target_url: str, competitor_list: list[dict], biz_info: dict, n: int = 30) -> dict:
    all_urls = [target_url] + [normalize_url(c.get("domain", "")) for c in competitor_list]
    all_labels = [biz_info.get("brand_name", extract_domain(target_url))] + [c.get("brand_name", c.get("domain", "")) for c in competitor_list]

    def _sim_one_brand(url: str, brand_variants: list[str]) -> dict:
        gpt_hits, gem_hits, gpt_ran, gem_ran = 0, 0, False, False

        def _gpt_batch():
            h = 0
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
                futures = [ex.submit(simulate_single_gpt, client_gpt, question, url, GPT_MODEL, brand_variants) for _ in range(n)]
                for f in concurrent.futures.as_completed(futures):
                    if f.result(timeout=15).get("cited"): h += 1
            return h

        def _gem_batch():
            h = 0
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
                futures = [ex.submit(simulate_single_gemini, client_gemini, question, url, brand_variants) for _ in range(n)]
                for f in concurrent.futures.as_completed(futures):
                    if f.result(timeout=15).get("cited"): h += 1
            return h

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            f_gpt = ex.submit(_gpt_batch) if client_gpt else None
            f_gem = ex.submit(_gem_batch) if client_gemini else None
            if f_gpt: gpt_hits, gpt_ran = f_gpt.result(), True
            if f_gem: gem_hits, gem_ran = f_gem.result(), True

        gpt_rate = round(gpt_hits / n * 100, 1) if gpt_ran else None
        gem_rate = round(gem_hits / n * 100, 1) if gem_ran else None
        valid = [v for v in [gpt_rate, gem_rate] if v is not None]
        return {
            "gpt_rate": gpt_rate, "gem_rate": gem_rate,
            "avg_rate": round(sum(valid)/max(1,len(valid)),1) if valid else 0,
            "ci_lo": calc_confidence_interval(gpt_hits+gem_hits, (n if gpt_ran else 0)+(n if gem_ran else 0))[0]
        }

    sov_results = []
    for i, (url, label) in enumerate(zip(all_urls, all_labels)):
        brand_biz = biz_info if i==0 else {"brand_name": label, "industry": biz_info.get("industry", "")}
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
        self.title, self.description, self._in_title = "", "", False
    def handle_starttag(self, tag, attrs):
        if tag == "title": self._in_title = True
        if tag == "meta":
            d = dict(attrs)
            if d.get("name", "").lower() == "description" or d.get("property", "").lower() == "og:description":
                self.description = d.get("content", "")
    def handle_endtag(self, tag):
        if tag == "title": self._in_title = False
    def handle_data(self, data):
        if self._in_title and not self.title: self.title = data.strip()

def crawl_site_metadata(url: str) -> dict:
    try:
        resp = requests.get(f"https://r.jina.ai/{url}", headers={"Accept": "text/markdown"}, timeout=15)
        if resp.status_code == 200 and len(resp.text) > 200:
            return {"title": resp.text[:100], "description": resp.text[:500], "html_snippet": resp.text[:4000], "crawl_ok": True}
    except: pass
    
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        parser = _MetaParser()
        parser.feed(resp.text[:50000])
        return {"title": parser.title, "description": parser.description, "html_snippet": resp.text[:4000], "crawl_ok": True}
    except:
        return {"title": "", "description": "", "html_snippet": "", "crawl_ok": False}

def analyze_business_identity(client_gpt, client_gemini, url: str) -> dict:
    meta = crawl_site_metadata(url)
    domain = extract_domain(url)
    
    prompt = f"""[도메인]: {domain}
[크롤링]: {meta['title']} / {meta['description']}
크롤링 텍스트가 없더라도 도메인명({domain})과 사전 지식을 활용해 이 브랜드의 실제 업종을 구체적으로 추론하세요. (예: avahair.co.kr -> 미용실 프랜차이즈)
JSON만 출력: {{"brand_name":"사명", "industry":"실물 비즈니스명", "core_product":"핵심상품", "target_audience":"타겟"}}"""

    res = ""
    if client_gpt: res = call_gpt(client_gpt, prompt, max_tokens=500, model=GPT_MODEL)
    elif client_gemini: res = call_gemini(client_gemini, prompt, max_tokens=500)

    try:
        return json.loads(re.search(r'\{.*\}', res, re.DOTALL).group())
    except:
        return {"brand_name": domain.split(".")[0].upper(), "industry": "비즈니스 서비스", "core_product": "서비스", "target_audience": "잠재 고객"}

# ─────────────────────────────────────────────
# API 호출 기본 함수
# ─────────────────────────────────────────────
def call_gpt(client, prompt: str, system: str = "", model: str = GPT_MODEL, max_tokens: int = 1500, temperature_override: float = 0.7) -> str:
    messages = [{"role": "system", "content": system}] if system else []
    messages.append({"role": "user", "content": prompt})
    res = client.chat.completions.create(model=model, messages=messages, max_tokens=max_tokens, temperature=temperature_override)
    return res.choices[0].message.content.strip()

def call_gemini(model_obj, prompt: str, max_tokens: int = 1500, temperature_override: float = 0.7) -> str:
    res = model_obj.generate_content(prompt, generation_config=genai.types.GenerationConfig(max_output_tokens=max_tokens, temperature=temperature_override))
    return res.text.strip()

# ─────────────────────────────────────────────
# AI 타겟 질문 생성 (창의성 극대화)
# ─────────────────────────────────────────────
def generate_target_questions(client_gpt, client_gemini, url: str, biz_info: dict) -> list[str]:
    brand = biz_info.get("brand_name", extract_domain(url))
    ind = biz_info.get("industry", "서비스")
    prod = biz_info.get("core_product", "")
    
    prompt = f"""당신은 {ind} 전문 마케터입니다.
{brand}({prod})의 실제 고객이 구매 전 지식인이나 AI에게 물어볼 법한 구체적이고 현실적인 타겟 질문 5개를 도출하세요.
- 뻔한 템플릿("차별점은?", "장단점은?") 금지. 업계 실무 용어와 맥락(비용, 수수료, 연동, 유지력 등)을 반영할 것.
- 도메인 주소 대신 한글 사명 '{brand}' 포함.
물음표로 끝나는 질문 5개만 한 줄씩 출력."""

    res = ""
    if client_gpt: res = call_gpt(client_gpt, prompt, max_tokens=800, model=GPT_MODEL)
    elif client_gemini: res = call_gemini(client_gemini, prompt, max_tokens=800)

    qs = [re.sub(r'^[\d\.\-\*\[\]\s]+', '', q).strip() for q in res.split('\n') if '?' in q]
    return [q for q in qs if len(q) > 5][:5]

# ─────────────────────────────────────────────
# 병렬 시뮬레이션 로직 (Turbo)
# ─────────────────────────────────────────────
def simulate_single_gpt(client, q: str, url: str, model: str, bv: list) -> dict:
    try:
        res = call_gpt(client, f"질문: {q}\n\n답변:", max_tokens=150, model=model, temperature_override=0.5)
        cited = any(v.lower() in res.lower() for v in bv)
        return {"cited": cited, "response_sample": res[:200] if cited else ""}
    except: return {"cited": False, "response_sample": ""}

def simulate_single_gemini(model_obj, q: str, url: str, bv: list) -> dict:
    try:
        res = call_gemini(model_obj, f"질문: {q}\n\n답변:", max_tokens=150, temperature_override=0.5)
        cited = any(v.lower() in res.lower() for v in bv)
        return {"cited": cited, "response_sample": res[:200] if cited else ""}
    except: return {"cited": False, "response_sample": ""}

def run_simulation(client_gpt, client_gemini, question: str, target_url: str, n: int = 50, biz_info: dict = None, cb=None) -> dict:
    bv = build_brand_variants(target_url, biz_info or {})
    gpt_h, gem_h, gpt_r, gem_r = 0, 0, False, False
    g_samp, m_samp = [], []

    def _gpt():
        h, s = 0, []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            futs = [ex.submit(simulate_single_gpt, client_gpt, question, target_url, GPT_MODEL, bv) for _ in range(n)]
            for f in concurrent.futures.as_completed(futs):
                r = f.result(timeout=15)
                if r["cited"]: 
                    h += 1
                    if len(s)<2: s.append(r["response_sample"])
        return h, s

    def _gem():
        h, s = 0, []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            futs = [ex.submit(simulate_single_gemini, client_gemini, question, target_url, bv) for _ in range(n)]
            for f in concurrent.futures.as_completed(futs):
                r = f.result(timeout=15)
                if r["cited"]: 
                    h += 1
                    if len(s)<2: s.append(r["response_sample"])
        return h, s

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        if client_gpt: f1 = ex.submit(_gpt)
        if client_gemini: f2 = ex.submit(_gem)
        if cb: cb(0.5)
        if client_gpt: gpt_h, g_samp = f1.result(); gpt_r = True
        if client_gemini: gem_h, m_samp = f2.result(); gem_r = True
    if cb: cb(1.0)

    gpt_rate = round(gpt_h/n*100,1) if gpt_r else None
    gem_rate = round(gem_h/n*100,1) if gem_r else None
    valid = [v for v in [gpt_rate, gem_rate] if v is not None]
    return {
        "gpt_rate": gpt_rate, "gemini_rate": gem_rate,
        "avg_rate": round(sum(valid)/len(valid),1) if valid else 0,
        "gpt_hits": gpt_h, "gemini_hits": gem_h, "total": n,
        "gpt_ci": calc_confidence_interval(gpt_h, n) if gpt_r else (None,None),
        "gemini_ci": calc_confidence_interval(gem_h, n) if gem_r else (None,None),
        "gpt_samples": g_samp, "gemini_samples": m_samp
    }

def run_all_simulations(client_gpt, client_gemini, questions: list, url: str, n: int = 50, biz_info: dict = None) -> list:
    res = [None]*len(questions)
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(questions),5)) as ex:
        fmap = {ex.submit(run_simulation, client_gpt, client_gemini, q, url, n, biz_info): i for i,q in enumerate(questions)}
        for f in concurrent.futures.as_completed(fmap):
            try: res[fmap[f]] = f.result(timeout=max(120,n*3))
            except: res[fmap[f]] = {"gpt_rate":0, "gemini_rate":0, "avg_rate":0, "total":n, "gpt_samples":[], "gemini_samples":[]}
    return res

# ─────────────────────────────────────────────
# 전략 분석
# ─────────────────────────────────────────────
def run_strategy_analysis(client_gpt, client_gemini, question: str, target_url: str, biz_info: dict) -> dict:
    domain, brand, ind = extract_domain(target_url), biz_info.get("brand_name",""), biz_info.get("industry","")
    sys_msg = "완성된 문장으로 마침표(.)로 끝맺으세요."

    p_diag = f"[{brand}]이 질문 '{question}'에서 AI 인용 점유율이 낮습니다. 사이트 구조/콘텐츠 문제점 3가지 (항목당 1줄)"
    p_kw = f"[{brand}]({ind})가 AI 인용을 선점하기 좋은 블루오션 틈새 질문/키워드 5개 추천 (한 줄씩)"
    p_geo = f"[{brand}]이 '{question}' 검색 시 인용되도록 홈페이지 개선방안 3가지 (각 2줄 이내)"

    def _call(p):
        if client_gpt: return call_gpt(client_gpt, p, system=sys_msg, model=GPT_MODEL)
        if client_gemini: return call_gemini(client_gemini, p)
        return ""

    diag_res = _call(p_diag)
    kw_res = _call(p_kw)
    geo_res = _call(p_geo)

    return {
        "diagnoses": [d.strip().lstrip("•-*") for d in diag_res.split('\n') if d.strip()][:3],
        "keywords": [k.strip().lstrip("•-*1234567890. ") for k in kw_res.split('\n') if k.strip()][:5],
        "geo_guides": [g.strip() for g in re.split(r'\n(?=\d+\.)', geo_res) if g.strip()][:3]
    }

# ─────────────────────────────────────────────
# 렌더링 UI
# ─────────────────────────────────────────────
def render_bar_chart(results: list, questions: list, title: str):
    if not results: return
    fig = go.Figure()
    sq = [q[:20]+"…" if len(q)>20 else q for q in questions]
    
    g_y = [r.get("gpt_rate") for r in results]
    m_y = [r.get("gemini_rate") for r in results]
    
    if any(v is not None for v in g_y):
        fig.add_trace(go.Bar(name="GPT", x=sq, y=[v or 0 for v in g_y], marker_color="#1E3A8A", text=[f"{v}%" if v else "" for v in g_y], textposition="outside"))
    if any(v is not None for v in m_y):
        fig.add_trace(go.Bar(name="Gemini", x=sq, y=[v or 0 for v in m_y], marker_color="#3B82F6", text=[f"{v}%" if v else "" for v in m_y], textposition="outside"))

    fig.update_layout(title=dict(text=title, font=dict(size=16)), barmode="group", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color=st.session_state.get("_text", "#333"), margin=dict(t=50, b=30, l=40, r=20), height=350)
    st.plotly_chart(fig, use_container_width=True)

def render_sov_chart(sov_results: list, title: str):
    if not sov_results: return
    labels = [r["label"] for r in sov_results]
    avgs = [r.get("avg_rate",0) for r in sov_results]
    colors = ["#2563EB" if r.get("is_target") else "#94A3B8" for r in sov_results]
    
    fig = go.Figure(go.Bar(x=avgs, y=labels, orientation="h", marker_color=colors, text=[f"{v:.1f}%" for v in avgs], textposition="outside"))
    fig.update_layout(title=title, yaxis=dict(autorange="reversed"), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=100, r=40, t=50, b=40), height=max(300, len(labels)*50))
    st.plotly_chart(fig, use_container_width=True)
    
    df = pd.DataFrame([{"브랜드": r["label"], "평균 점유율": f"{r.get('avg_rate',0):.1f}%"} for r in sov_results])
    st.dataframe(df, use_container_width=True, hide_index=True)

def render_strategy_analysis(strategy: dict):
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### 🚨 인용 실패 원인 진단")
        for d in strategy.get("diagnoses", []):
            st.markdown(f"<div style='background:rgba(239,68,68,0.1);padding:10px;border-radius:8px;margin-bottom:8px;border-left:3px solid #EF4444;font-size:0.9rem;'>{d}</div>", unsafe_allow_html=True)
    with c2:
        st.markdown("##### 💡 블루오션 타겟 질문 추천")
        for k in strategy.get("keywords", []):
            st.markdown(f"<div style='background:rgba(59,130,246,0.1);padding:10px;border-radius:8px;margin-bottom:8px;border-left:3px solid #3B82F6;font-size:0.9rem;'>{k}</div>", unsafe_allow_html=True)
    
    st.markdown("##### 🛠️ GEO 최적화 가이드")
    for i, g in enumerate(strategy.get("geo_guides", [])):
        st.info(f"**Step {i+1}.** {g}")

# ─────────────────────────────────────────────
# 사이드바
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("<div style='text-align:center; margin-bottom:20px;'><h1 style='margin:0; font-size:2.5rem;'>📊</h1><h3 style='margin:5px 0; color:white;'>AI Citation Analyzer</h3><p style='color:#94A3B8; font-size:0.8rem;'>Enterprise Edition</p></div>", unsafe_allow_html=True)

    if st.button("🌓 다크/라이트 모드", use_container_width=True):
        st.session_state["dark_mode"] = not st.session_state["dark_mode"]
        st.rerun()

    st.markdown("<hr style='border-color:#334155;'>", unsafe_allow_html=True)
    openai_key  = st.text_input("OpenAI API Key", type="password", placeholder="sk-...")
    gemini_key  = st.text_input("Gemini API Key", type="password", placeholder="AIza...")

    st.markdown("<hr style='border-color:#334155;'>", unsafe_allow_html=True)
    sim_count = st.slider("정밀도 (시뮬레이션 횟수)", 10, 100, 30, 10, help="횟수가 높을수록 정확한 통계가 산출됩니다.")
    n_competitors = st.slider("분석할 경쟁사 수", 3, 10, 5)

    gpt_ok = bool(openai_key and openai_key.startswith("sk-"))
    gemini_ok = bool(gemini_key and len(gemini_key) > 10)
    
    st.markdown("##### 📡 엔진 연결 상태")
    st.success("GPT 활성화") if gpt_ok else st.error("GPT 미연결")
    st.success("Gemini 활성화") if gemini_ok else st.error("Gemini 미연결")

def get_clients():
    cgpt, cgem = None, None
    if gpt_ok: cgpt = openai.OpenAI(api_key=openai_key)
    if gemini_ok: 
        genai.configure(api_key=gemini_key)
        cgem = genai.GenerativeModel(GEMINI_MODEL)
    return cgpt, cgem

client_gpt, client_gemini = get_clients()

# ─────────────────────────────────────────────
# 메인 화면
# ─────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>🚀 GEO Performance Dashboard</h1>
    <p>엔터프라이즈 AI 검색 점유율(SOV) 및 경쟁사 최적화 분석 도구</p>
</div>
""", unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
c1.metric("데이터 연산 파이프라인", "GPT-4o-mini & Gemini 2.0", "Dual Engine")
c2.metric("정밀도 설정", f"질문당 {sim_count}회", "병렬 처리 활성화")
c3.metric("경쟁사 도출", f"Top {n_competitors} 자동 분석", "Jina Reader 연동")
st.write("")

tab1, tab2 = st.tabs(["🤖 자동 분석 (AI 전략 도출)", "✏️ 수동 분석 (키워드 입력)"])

# ─────────────────────────────────────────────
# TAB 1
# ─────────────────────────────────────────────
with tab1:
    st.markdown("##### 🎯 타겟 사이트 분석")
    t1_c1, t1_c2 = st.columns([2, 1])
    url_auto = t1_c1.text_input("URL 입력", placeholder="https://avahair.co.kr", key="url_auto")
    ind_auto = t1_c2.text_input("업종 수정 (선택)", value=st.session_state.get("ind_auto_val", ""), placeholder="예: 미용실 프랜차이즈")
    
    btn_pre = st.button("🔎 1단계: 업종 자동 파악", use_container_width=True)
    if btn_pre and url_auto:
        with st.spinner("비즈니스 아이덴티티 분석 중..."):
            biz = analyze_business_identity(client_gpt, client_gemini, normalize_url(url_auto))
            st.session_state["ind_auto_val"] = biz.get("industry", "")
            st.session_state["biz_auto_val"] = biz
            st.success(f"✅ 파악 완료: **{biz.get('brand_name','')}** ({biz.get('industry','')})")
            st.rerun()

    if st.button("🚀 2단계: Full 시뮬레이션 시작", type="primary", use_container_width=True):
        if not url_auto or (not gpt_ok and not gemini_ok):
            st.error("URL과 API 키를 확인해주세요.")
        else:
            url_norm = normalize_url(url_auto)
            biz = st.session_state.get("biz_auto_val", analyze_business_identity(client_gpt, client_gemini, url_norm))
            if ind_auto: biz["industry"] = ind_auto

            st.write("---")
            with st.spinner("🧠 타겟 질문 생성 중..."):
                qs = generate_target_questions(client_gpt, client_gemini, url_norm, biz)
            
            st.markdown("##### 📝 도출된 타겟 질문")
            for i, q in enumerate(qs): st.markdown(f"`Q{i+1}` {q}")

            with st.spinner("⚡ 병렬 인용 점유율 분석 중..."):
                results = run_all_simulations(client_gpt, client_gemini, qs, url_norm, sim_count, biz)
            
            render_bar_chart(results, qs, f"'{biz.get('brand_name')}' 타겟 질문별 AI 인용 점유율")
            
            st.write("---")
            with st.spinner("🏢 경쟁사 SOV 매칭 중..."):
                comps = discover_competitors(client_gpt, client_gemini, biz, url_norm, n_competitors)
                sov = run_sov_simulation(client_gpt, client_gemini, qs[0], url_norm, comps, biz, max(10, sim_count//2))
            
            st.markdown("##### 🏆 경쟁사 대비 SOV (기준: 1번 질문)")
            render_sov_chart(sov, "시장 내 AI 인용 점유율(SOV) 비교")

            st.write("---")
            with st.spinner("💡 딥러닝 최적화 전략 생성 중..."):
                strat = run_strategy_analysis(client_gpt, client_gemini, qs[0], url_norm, biz)
                render_strategy_analysis(strat)

# ─────────────────────────────────────────────
# TAB 2
# ─────────────────────────────────────────────
with tab2:
    st.markdown("##### ✏️ 특정 키워드/질문 직접 검증")
    m_url = st.text_input("URL 입력", key="m_url")
    m_kw = st.text_input("검증할 질문/키워드", placeholder="손상모 복구펌 가격은?", key="m_kw")
    
    if st.button("🔬 수동 검증 시작", type="primary", use_container_width=True):
        if not m_url or not m_kw or (not gpt_ok and not gemini_ok):
            st.error("입력값을 확인해주세요.")
        else:
            url_norm = normalize_url(m_url)
            with st.spinner("분석 중..."):
                biz = analyze_business_identity(client_gpt, client_gemini, url_norm)
                res = run_simulation(client_gpt, client_gemini, m_kw, url_norm, sim_count, biz)
            
            render_bar_chart([res], [m_kw], f"'{m_kw}' 분석 결과")
            
            with st.spinner("전략 생성 중..."):
                strat = run_strategy_analysis(client_gpt, client_gemini, m_kw, url_norm, biz)
                render_strategy_analysis(strat)
