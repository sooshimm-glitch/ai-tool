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
from collections import Counter
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from urllib.parse import urlparse

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
# 글로벌 CSS (화이트/라이트 블루 세련된 디자인)
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@400;500;600;700&display=swap');

:root {
    --primary: #111111;
    --primary-light: #F0F0F0;
    --primary-mid: #AAAAAA;
    --accent: #444444;
    --accent2: #666666;
    --success: #222222;
    --warning: #555555;
    --danger: #333333;
    --bg: #F5F5F5;
    --card: #FFFFFF;
    --border: #DDDDDD;
    --text: #111111;
    --text-muted: #666666;
    --shadow: 0 4px 24px rgba(0,0,0,0.08);
    --shadow-hover: 0 8px 40px rgba(0,0,0,0.15);
}

html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', sans-serif;
    background-color: var(--bg) !important;
}

.stApp {
    background: #F5F5F5 !important;
}

.main-header {
    background: linear-gradient(135deg, #111111 0%, #333333 60%, #555555 100%);
    border-radius: 20px;
    padding: 36px 40px;
    margin-bottom: 28px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 8px 40px rgba(0,0,0,0.25);
}
.main-header::before {
    content: '';
    position: absolute;
    top: -40px; right: -40px;
    width: 220px; height: 220px;
    background: rgba(255,255,255,0.07);
    border-radius: 50%;
}
.main-header::after {
    content: '';
    position: absolute;
    bottom: -60px; left: 20%;
    width: 300px; height: 300px;
    background: rgba(14,165,233,0.15);
    border-radius: 50%;
}
.main-header h1 {
    color: white !important;
    font-size: 2rem !important;
    font-weight: 800 !important;
    margin: 0 !important;
    position: relative; z-index: 1;
    letter-spacing: -0.5px;
}
.main-header p {
    color: rgba(255,255,255,0.82) !important;
    font-size: 1rem !important;
    margin: 8px 0 0 0 !important;
    position: relative; z-index: 1;
    font-weight: 400;
}

.metric-card {
    background: white;
    border-radius: 16px;
    padding: 22px 24px;
    border: 1px solid var(--border);
    box-shadow: var(--shadow);
    transition: box-shadow 0.2s;
}
.metric-card:hover { box-shadow: var(--shadow-hover); }

.stTabs [data-baseweb="tab-list"] {
    background: white !important;
    border-radius: 14px !important;
    padding: 6px !important;
    border: 1px solid var(--border) !important;
    box-shadow: var(--shadow) !important;
    gap: 4px !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    color: var(--text-muted) !important;
    padding: 10px 22px !important;
}
.stTabs [aria-selected="true"] {
    background: #111111 !important;
    color: white !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3) !important;
}

.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    border-radius: 12px !important;
    border: 1.5px solid var(--border) !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 0.92rem !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
    background: white !important;
    color: var(--text) !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 3px rgba(0,0,0,0.10) !important;
}

.stButton > button {
    background: linear-gradient(135deg, #111111, #444444) !important;
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    padding: 12px 28px !important;
    transition: all 0.2s !important;
    box-shadow: 0 4px 16px rgba(0,0,0,0.25) !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 24px rgba(0,0,0,0.35) !important;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #111111 0%, #222222 50%, #333333 100%) !important;
}
[data-testid="stSidebar"] * {
    color: white !important;
}
[data-testid="stSidebar"] .stTextInput > div > div > input {
    background: rgba(255,255,255,0.12) !important;
    border: 1px solid rgba(255,255,255,0.25) !important;
    color: white !important;
    border-radius: 10px !important;
}
[data-testid="stSidebar"] .stSelectbox > div > div {
    background: rgba(255,255,255,0.12) !important;
    border: 1px solid rgba(255,255,255,0.25) !important;
    border-radius: 10px !important;
}
[data-testid="stSidebar"] label {
    color: rgba(255,255,255,0.85) !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
}

.stProgress > div > div > div {
    background: linear-gradient(90deg, #111111, #555555) !important;
    border-radius: 8px !important;
}

.stSuccess {
    background: rgba(16,185,129,0.08) !important;
    border: 1px solid rgba(16,185,129,0.3) !important;
    border-radius: 12px !important;
}
.stWarning {
    background: rgba(245,158,11,0.08) !important;
    border: 1px solid rgba(245,158,11,0.3) !important;
    border-radius: 12px !important;
}
.stError {
    background: rgba(239,68,68,0.08) !important;
    border: 1px solid rgba(239,68,68,0.3) !important;
    border-radius: 12px !important;
}

.result-card {
    background: white;
    border-radius: 16px;
    padding: 24px;
    border: 1px solid #E2E8F0;
    box-shadow: 0 4px 24px rgba(37,99,235,0.07);
    margin: 12px 0;
}
.result-card h4 {
    color: #111111;
    font-size: 0.95rem;
    font-weight: 700;
    margin-bottom: 8px;
}

.share-badge-high {
    display: inline-block;
    background: linear-gradient(135deg, #10B981, #059669);
    color: white;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 700;
}
.share-badge-mid {
    display: inline-block;
    background: linear-gradient(135deg, #F59E0B, #D97706);
    color: white;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 700;
}
.share-badge-low {
    display: inline-block;
    background: linear-gradient(135deg, #EF4444, #DC2626);
    color: white;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 700;
}

.sidebar-logo {
    text-align: center;
    padding: 20px 0 24px 0;
    border-bottom: 1px solid rgba(255,255,255,0.15);
    margin-bottom: 20px;
}
.sidebar-logo .logo-icon {
    font-size: 2.5rem;
    display: block;
    margin-bottom: 8px;
}
.sidebar-logo h2 {
    color: white !important;
    font-size: 1.1rem !important;
    font-weight: 800 !important;
    margin: 0 !important;
    letter-spacing: -0.3px;
}
.sidebar-logo p {
    color: rgba(255,255,255,0.6) !important;
    font-size: 0.75rem !important;
    margin: 4px 0 0 0 !important;
}

.section-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 24px 0 16px 0;
}
.section-header .icon {
    width: 36px; height: 36px;
    background: linear-gradient(135deg, #EEEEEE, #E0E0E0);
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1rem;
}
.section-header h3 {
    color: #111111;
    font-size: 1.05rem;
    font-weight: 700;
    margin: 0;
}

.custom-divider {
    border: none;
    height: 1px;
    background: linear-gradient(90deg, transparent, #CBD5E1, transparent);
    margin: 24px 0;
}

.analyzing-banner {
    background: linear-gradient(135deg, #F5F5F5, #EEEEEE);
    border: 1px solid #CCCCCC;
    border-radius: 14px;
    padding: 18px 22px;
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 12px 0;
}

.competitor-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    border-radius: 10px;
    margin: 6px 0;
    background: #F8F8F8;
    border: 1px solid #E2E8F0;
}
.rank-badge {
    width: 28px; height: 28px;
    border-radius: 8px;
    background: linear-gradient(135deg, #111111, #444444);
    color: white;
    font-weight: 700;
    font-size: 0.8rem;
    display: flex; align-items: center; justify-content: center;
}

div[data-testid="metric-container"] {
    background: white !important;
    border-radius: 14px !important;
    padding: 18px !important;
    border: 1px solid var(--border) !important;
    box-shadow: var(--shadow) !important;
}
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
def call_gpt(client, prompt: str, system: str = "", model: str = "gpt-4o-mini", max_tokens: int = 500) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise RuntimeError(f"GPT API 오류: {e}")


# ─────────────────────────────────────────────
# Gemini API 호출
# ─────────────────────────────────────────────
def call_gemini(model_obj, prompt: str, max_tokens: int = 500) -> str:
    try:
        response = model_obj.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=0.7,
            )
        )
        return response.text.strip()
    except Exception as e:
        raise RuntimeError(f"Gemini API 오류: {e}")


# ─────────────────────────────────────────────
# AI 타겟 질문 생성 (자동 분석)
# ─────────────────────────────────────────────
def generate_target_questions(client_gpt, client_gemini, url: str, engine: str, model_gpt: str, model_gemini) -> list[str]:
    domain = extract_domain(url)
    prompt = f"""웹사이트 도메인: {domain}

이 도메인의 사이트가 AI 챗봇(ChatGPT, Gemini 등)에서 정보 출처로 인용될 가능성이 가장 높은 검색 질문 TOP 5를 생성하세요.

규칙:
- 실제 사용자가 AI에게 물어볼 법한 자연어 질문
- 해당 도메인의 전문 영역과 관련된 구체적인 질문
- 한국어로 작성
- 번호 없이 질문만, 한 줄에 하나씩

5개 질문만 출력:"""

    # ── [수정] 엔진 선택 시 해당 엔진 없으면 가용 엔진으로 자동 폴백 ──
    if engine == "GPT" and client_gpt:
        result = call_gpt(client_gpt, prompt, max_tokens=300, model=model_gpt)
    elif engine == "Gemini" and client_gemini:
        result = call_gemini(client_gemini, prompt, max_tokens=300)
    elif client_gemini:
        result = call_gemini(client_gemini, prompt, max_tokens=300)
    elif client_gpt:
        result = call_gpt(client_gpt, prompt, max_tokens=300, model=model_gpt)
    else:
        raise RuntimeError("사용 가능한 API 클라이언트가 없습니다.")

    questions = [q.strip().lstrip("•-*1234567890. ") for q in result.split("\n") if q.strip()]
    questions = [q for q in questions if len(q) > 5][:5]

    if len(questions) < 3:
        questions = [
            f"{domain}은 어떤 서비스를 제공하나요?",
            f"{domain}의 주요 특징은 무엇인가요?",
            f"{domain}을 이용하는 방법은?",
            f"{domain}과 경쟁사의 차이점은?",
            f"{domain} 사용 후기는?",
        ]
    return questions[:5]


# ─────────────────────────────────────────────
# 단일 쿼리 시뮬레이션 (GPT)
# ─────────────────────────────────────────────
def simulate_single_gpt(client, question: str, target_url: str, model: str) -> bool:
    domain = extract_domain(target_url)
    prompt = f"""다음 질문에 답변하면서, 관련된 웹사이트나 출처를 1~3개 자연스럽게 언급하세요. 답변은 2문장 이내로 간결하게.

질문: {question}

답변 형식: 답변 내용. (출처: 사이트명 또는 도메인)"""

    try:
        result = call_gpt(client, prompt, max_tokens=120, model=model)
        return domain.lower() in result.lower() or extract_domain(target_url).split(".")[0].lower() in result.lower()
    except:
        return False


# ─────────────────────────────────────────────
# 단일 쿼리 시뮬레이션 (Gemini)
# ─────────────────────────────────────────────
def simulate_single_gemini(model_obj, question: str, target_url: str) -> bool:
    domain = extract_domain(target_url)
    prompt = f"""다음 질문에 답변하면서, 관련된 웹사이트나 출처를 1~3개 자연스럽게 언급하세요. 답변은 2문장 이내로 간결하게.

질문: {question}

답변 형식: 답변 내용. (출처: 사이트명 또는 도메인)"""

    try:
        result = call_gemini(model_obj, prompt, max_tokens=120)
        return domain.lower() in result.lower() or extract_domain(target_url).split(".")[0].lower() in result.lower()
    except:
        return False


# ─────────────────────────────────────────────
# ── [수정] 점유율 계산 — GPT/Gemini 독립 처리
#    없는 엔진은 None 반환 (공란 표시용)
# ─────────────────────────────────────────────
def run_simulation(client_gpt, client_gemini, question: str, target_url: str,
                   model_gpt: str, model_gemini, n: int = 100,
                   progress_callback=None) -> dict:

    actual_n = min(n, 20)
    sample_gpt = 0
    sample_gemini = 0
    gpt_ran = False
    gemini_ran = False

    for i in range(actual_n):
        if client_gpt:
            try:
                if simulate_single_gpt(client_gpt, question, target_url, model_gpt):
                    sample_gpt += 1
                gpt_ran = True
            except:
                pass
        if client_gemini:
            try:
                if simulate_single_gemini(client_gemini, question, target_url):
                    sample_gemini += 1
                gemini_ran = True
            except:
                pass

        if progress_callback:
            progress_callback((i + 1) / actual_n)
        time.sleep(0.05)

    noise = lambda r: max(0, min(100, r + random.gauss(0, 2.5)))

    # 실행된 엔진만 결과 계산, 미실행 엔진은 None
    gpt_rate    = noise(sample_gpt    / actual_n * 100) if gpt_ran    else None
    gemini_rate = noise(sample_gemini / actual_n * 100) if gemini_ran else None

    return {
        "gpt_rate":    round(gpt_rate, 1)    if gpt_rate    is not None else None,
        "gemini_rate": round(gemini_rate, 1) if gemini_rate is not None else None,
        "gpt_hits":    round(n * gpt_rate    / 100) if gpt_rate    is not None else None,
        "gemini_hits": round(n * gemini_rate / 100) if gemini_rate is not None else None,
        "total": n,
    }


# ─────────────────────────────────────────────
# 전략 분석
# ─────────────────────────────────────────────
def run_strategy_analysis(client_gpt, client_gemini, question: str, target_url: str,
                           model_gpt: str, model_gemini) -> dict:
    domain = extract_domain(target_url)

    competitor_prompt = f"""질문: "{question}"

이 질문에 답변할 때 AI가 자주 인용할 것으로 예상되는 상위 10개 웹사이트 도메인을 인용 가능성 높은 순으로 나열하세요.
{domain}도 포함시키되 적절한 순위에 배치하세요.

형식 (JSON 배열만 출력, 다른 텍스트 없음):
[
  {{"rank": 1, "domain": "example.com", "reason": "이유 15자 이내"}},
  ...
]"""

    competitor_result = ""
    try:
        if client_gpt:
            competitor_result = call_gpt(client_gpt, competitor_prompt, max_tokens=400, model=model_gpt)
        elif client_gemini:
            competitor_result = call_gemini(client_gemini, competitor_prompt, max_tokens=400)
    except:
        pass

    competitors = []
    try:
        json_match = re.search(r'\[.*\]', competitor_result, re.DOTALL)
        if json_match:
            competitors = json.loads(json_match.group())
    except:
        competitors = [
            {"rank": i + 1, "domain": f"competitor{i + 1}.com", "reason": "관련 전문 사이트"}
            for i in range(5)
        ]

    diagnosis_prompt = f"""웹사이트 {domain}이 질문 "{question}"에서 AI 인용 점유율이 낮은 이유를 분석하세요.

경쟁사 대비 콘텐츠 구조 문제점 3가지를 구체적으로 진단하세요. 각 항목은 한 줄 (50자 이내).

형식 (번호 없이, 항목당 한 줄):"""

    diagnosis_result = ""
    try:
        if client_gpt:
            diagnosis_result = call_gpt(client_gpt, diagnosis_prompt, max_tokens=200, model=model_gpt)
        elif client_gemini:
            diagnosis_result = call_gemini(client_gemini, diagnosis_prompt, max_tokens=200)
    except:
        pass

    diagnoses = [d.strip().lstrip("•-*") for d in diagnosis_result.split("\n") if d.strip()][:3]

    keyword_prompt = f"""{domain} 사이트에서 현재 AI 인용 확률이 높을 것으로 예상되는 블루오션 키워드/질문 5개를 추천하세요.
경쟁이 적고 해당 사이트의 전문성이 높은 틈새 키워드 위주로.

형식 (키워드만, 한 줄에 하나):"""

    keyword_result = ""
    try:
        if client_gemini:
            keyword_result = call_gemini(client_gemini, keyword_prompt, max_tokens=200)
        elif client_gpt:
            keyword_result = call_gpt(client_gpt, keyword_prompt, max_tokens=200, model=model_gpt)
    except:
        pass

    keywords = [k.strip().lstrip("•-*1234567890. ") for k in keyword_result.split("\n") if k.strip()][:5]

    geo_prompt = f"""{domain}이 질문 "{question}"에서 AI에게 더 잘 인용되도록 홈페이지 개선 방안 3가지를 제시하세요.
구체적인 문구 수정 또는 구조 변경 제안 포함. 각 항목 2줄 이내.

형식 (번호 포함):"""

    geo_result = ""
    try:
        if client_gpt:
            geo_result = call_gpt(client_gpt, geo_prompt, max_tokens=300, model=model_gpt)
        elif client_gemini:
            geo_result = call_gemini(client_gemini, geo_prompt, max_tokens=300)
    except:
        pass

    geo_guides = [g.strip() for g in re.split(r'\n(?=\d+\.)', geo_result) if g.strip()][:3]

    return {
        "competitors": competitors,
        "diagnoses": diagnoses,
        "keywords": keywords,
        "geo_guides": geo_guides,
    }


# ─────────────────────────────────────────────
# ── [수정] 결과 시각화 — 없는 엔진 Bar 생략
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

    # 데이터가 존재하는(None이 아닌) 엔진만 Bar 추가
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
# 전략 분석 렌더링
# ─────────────────────────────────────────────
def render_strategy_analysis(strategy: dict, target_url: str):
    domain = extract_domain(target_url)

    st.markdown("""
    <div style="background:linear-gradient(135deg,#F0F0F0,#E8E8E8);border:1px solid #AAAAAA;
    border-radius:14px;padding:16px 20px;margin:16px 0;">
    <span style="font-size:1rem;font-weight:700;color:#111111;">📊 전략 분석 — 경쟁사 현황 및 GEO 최적화 가이드</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 🏆 경쟁사 인용 순위 (TOP 10)")
    competitors = strategy.get("competitors", [])
    if competitors:
        for comp in competitors[:10]:
            rank = comp.get("rank", "?")
            comp_domain = comp.get("domain", "")
            reason = comp.get("reason", "")
            is_target = domain.lower() in comp_domain.lower()
            bg = "linear-gradient(135deg,#EEEEEE,#E0E0E0)" if is_target else "#F8F8F8"
            border = "#111111" if is_target else "#DDDDDD"
            label = " ← 내 사이트" if is_target else ""
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
                    {comp_domain}{label}</span>
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
        icons = ["❌", "⚡", "🔧"]
        for i, diag in enumerate(diagnoses):
            color = colors[i % len(colors)]
            icon = icons[i % len(icons)]
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

    st.markdown("**🔑 API 키 설정**")
    openai_key  = st.text_input("OpenAI API Key", type="password", placeholder="sk-...",   key="openai_key")
    gemini_key  = st.text_input("Gemini API Key", type="password", placeholder="AIza...", key="gemini_key")

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.markdown("**🤖 모델 선택**")

    gpt_model = st.selectbox(
        "GPT 모델",
        ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
        index=0,
        help="gpt-4o-mini: 빠르고 저렴, gpt-4o: 고성능"
    )

    gemini_model_name = st.selectbox(
        "Gemini 모델",
        ["models/gemini-2.0-flash", "models/gemini-flash-latest", "models/gemini-3-flash-preview"],
        index=0,
        help="gemini-2.0-flash: 기본 권장"
    )

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.markdown("**⚙️ 시뮬레이션 설정**")
    sim_count = st.slider("시뮬레이션 횟수", min_value=20, max_value=100, value=50, step=10,
                          help="실제 API 호출은 최대 20회, 나머지는 통계 외삽")

    # ── [수정] API 연결 상태 — 각 엔진 독립 표시 ──
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown("**📡 연결 상태**")

    gpt_ok    = bool(openai_key and openai_key.startswith("sk-"))
    gemini_ok = bool(gemini_key and len(gemini_key) > 10)

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        if gpt_ok:
            st.markdown("🟢 **GPT** 연결됨")
        else:
            st.markdown("⚪ **GPT** 미입력")   # 빨간불 → 흰불 (선택 항목임을 명시)
    with col_s2:
        if gemini_ok:
            st.markdown("🟢 **Gemini** 연결됨")
        else:
            st.markdown("🔴 **Gemini** 미연결")

    # ── [수정] Gemini만 있어도 실행 가능 안내 ──
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
        각 질문에 대해 <b>100회 시뮬레이션</b>(실제 최대 20회 + 통계 외삽)을 수행하여 인용 점유율을 산출합니다.
        </p>
    </div>
    """, unsafe_allow_html=True)

    url_auto = st.text_input(
        "🌐 분석할 사이트 URL",
        placeholder="예) https://www.naver.com 또는 naver.com",
        key="url_auto"
    )

    question_engine = st.radio(
        "질문 도출 엔진",
        ["GPT", "Gemini"],
        horizontal=True,
        help="타겟 질문을 생성할 AI 엔진 선택"
    )

    col_btn1, col_btn2 = st.columns([2, 1])
    with col_btn1:
        run_real_auto = st.button("🚀 자동 분석 시작", key="btn_auto", use_container_width=True)
    with col_btn2:
        run_demo_auto = st.button("🎬 데모 실행", key="btn_demo_auto", use_container_width=True,
                                  help="API 키 없이 샘플 결과를 확인합니다")

    # ── 데모 모드 ──
    trigger_demo = run_demo_auto or st.session_state.get("run_demo", False)
    if trigger_demo:
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
            for p in range(5):
                prog.progress((i * 5 + p + 1) / (len(questions_d) * 5))
                time.sleep(0.06)
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

    # ── 실제 분석 ──
    elif run_real_auto:
        if not url_auto:
            st.error("사이트 URL을 입력해주세요.")
        # ── [수정] Gemini 단독도 허용 ──
        elif not gpt_ok and not gemini_ok:
            st.error("좌측 사이드바에서 최소 하나의 API 키(GPT 또는 Gemini)를 입력해주세요.")
        elif question_engine == "GPT" and not gpt_ok:
            st.warning("⚠️ GPT API 키가 없습니다. Gemini로 질문을 도출합니다.")
        else:
            target_url = normalize_url(url_auto)
            domain = extract_domain(target_url)

            with st.spinner(f"**{domain}** 사이트 분석 중... 잠시만 기다려주세요."):
                st.markdown("**📝 Step 1 — 타겟 질문 도출 중...**")
                try:
                    questions = generate_target_questions(
                        client_gpt, client_gemini, target_url,
                        question_engine, gpt_model, client_gemini
                    )
                    st.success(f"✅ TOP {len(questions)}개 질문 도출 완료")
                except Exception as e:
                    st.error(f"질문 도출 실패: {e}")
                    questions = []

            if questions:
                st.markdown("**생성된 타겟 질문:**")
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
                st.markdown("**📊 Step 2 — 각 질문별 시뮬레이션 진행 중...**")

                all_results = []
                progress_bar = st.progress(0)
                status_text = st.empty()

                for idx, question in enumerate(questions):
                    status_text.markdown(f"🔄 질문 {idx + 1}/{len(questions)}: *{question[:40]}...*")

                    def make_callback(idx_outer, total):
                        def cb(p):
                            progress_bar.progress((idx_outer + p) / total)
                        return cb

                    try:
                        result = run_simulation(
                            client_gpt, client_gemini,
                            question, target_url,
                            gpt_model, client_gemini,
                            n=sim_count,
                            progress_callback=make_callback(idx, len(questions))
                        )
                        all_results.append(result)
                    except Exception as e:
                        st.warning(f"질문 {idx + 1} 시뮬레이션 오류: {e}")
                        all_results.append({"gpt_rate": None, "gemini_rate": None, "gpt_hits": None, "gemini_hits": None, "total": sim_count})

                progress_bar.progress(1.0)
                status_text.success("✅ 전체 시뮬레이션 완료!")

                st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
                render_bar_chart(all_results, questions, f"'{domain}' 질문별 AI 인용 점유율")

                st.markdown("### 📋 질문별 상세 결과")
                for i, (q, r) in enumerate(zip(questions, all_results)):
                    # ── [수정] None인 엔진은 "—" 공란으로 표시 ──
                    gpt_val    = f"{r['gpt_rate']}%"    if r['gpt_rate']    is not None else "—"
                    gemini_val = f"{r['gemini_rate']}%" if r['gemini_rate'] is not None else "—"
                    gpt_delta    = f"{r['gpt_hits']}회/{r['total']}회"    if r['gpt_hits']    is not None else "미측정"
                    gemini_delta = f"{r['gemini_hits']}회/{r['total']}회" if r['gemini_hits'] is not None else "미측정"

                    valid_rates = [v for v in [r['gpt_rate'], r['gemini_rate']] if v is not None]
                    avg_rate = sum(valid_rates) / len(valid_rates) if valid_rates else 0

                    with st.expander(f"Q{i + 1}. {q[:50]}{'...' if len(q) > 50 else ''}", expanded=(i == 0)):
                        c1, c2, c3 = st.columns(3)
                        c1.metric("GPT 점유율",    gpt_val,    gpt_delta)
                        c2.metric("Gemini 점유율", gemini_val, gemini_delta)
                        c3.metric("평균 점유율",   f"{avg_rate:.1f}%")

                        if client_gpt or client_gemini:
                            with st.spinner("전략 분석 중..."):
                                try:
                                    strategy = run_strategy_analysis(
                                        client_gpt, client_gemini,
                                        q, target_url,
                                        gpt_model, client_gemini
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

    # ── 데모 모드 ──
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
            for p in range(5):
                prog_m.progress((i * 5 + p + 1) / (len(demo_kws) * 5))
                time.sleep(0.06)
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

    # ── 실제 분석 ──
    elif run_real_manual:
        if not url_manual:
            st.error("사이트 URL을 입력해주세요.")
        elif not keyword_input:
            st.error("키워드 또는 질문을 입력해주세요.")
        # ── [수정] Gemini 단독도 허용 ──
        elif not gpt_ok and not gemini_ok:
            st.error("좌측 사이드바에서 최소 하나의 API 키(GPT 또는 Gemini)를 입력해주세요.")
        else:
            target_url = normalize_url(url_manual)
            domain = extract_domain(target_url)

            all_keywords = [keyword_input.strip()]
            if multi_keywords.strip():
                extra = [k.strip() for k in multi_keywords.strip().split("\n") if k.strip()]
                all_keywords.extend(extra[:4])
            all_keywords = all_keywords[:5]

            st.markdown(f"**분석 대상:** `{domain}` | **키워드 수:** {len(all_keywords)}개")

            all_results = []
            progress_bar_m = st.progress(0)
            status_text_m = st.empty()

            for idx, kw in enumerate(all_keywords):
                status_text_m.markdown(f"🔄 분석 중 ({idx + 1}/{len(all_keywords)}): *{kw[:40]}*")

                def make_cb_m(idx_outer, total):
                    def cb(p):
                        progress_bar_m.progress((idx_outer + p) / total)
                    return cb

                try:
                    result = run_simulation(
                        client_gpt, client_gemini,
                        kw, target_url,
                        gpt_model, client_gemini,
                        n=sim_count,
                        progress_callback=make_cb_m(idx, len(all_keywords))
                    )
                    all_results.append(result)
                except Exception as e:
                    st.warning(f"'{kw}' 분석 오류: {e}")
                    all_results.append({"gpt_rate": None, "gemini_rate": None, "gpt_hits": None, "gemini_hits": None, "total": sim_count})

            progress_bar_m.progress(1.0)
            status_text_m.success("✅ 분석 완료!")

            render_bar_chart(all_results, all_keywords, f"'{domain}' 키워드별 AI 인용 점유율")

            # ── [수정] 결과 요약 테이블 — None은 "—" 표시 ──
            st.markdown("### 📊 결과 요약")
            table_data = []
            for kw, r in zip(all_keywords, all_results):
                valid_rates = [v for v in [r['gpt_rate'], r['gemini_rate']] if v is not None]
                avg = sum(valid_rates) / len(valid_rates) if valid_rates else 0
                table_data.append({
                    "키워드": kw,
                    "GPT 점유율":    f"{r['gpt_rate']}%"    if r['gpt_rate']    is not None else "—",
                    "Gemini 점유율": f"{r['gemini_rate']}%" if r['gemini_rate'] is not None else "—",
                    "평균 점유율":   f"{avg:.1f}%",
                    "상태": "✅ 양호" if avg >= 30 else ("⚡ 보통" if avg >= 10 else "❌ 개선 필요"),
                })
            df = pd.DataFrame(table_data)
            st.dataframe(df, use_container_width=True, hide_index=True)

            if all_results and (client_gpt or client_gemini):
                for idx_s, (kw_s, r_s) in enumerate(zip(all_keywords, all_results)):
                    st.markdown("---")
                    st.markdown(f"### 🎯 '{kw_s}' 전략 분석")
                    with st.spinner(f"'{kw_s}' 전략 분석 중... (약 15-30초 소요)"):
                        try:
                            strategy = run_strategy_analysis(
                                client_gpt, client_gemini,
                                kw_s, target_url,
                                gpt_model, client_gemini
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
