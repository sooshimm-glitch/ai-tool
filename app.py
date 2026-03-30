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
import hashlib
from collections import Counter
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from urllib.parse import urlparse
import concurrent.futures
import requests
from html.parser import HTMLParser
from io import BytesIO
from docx import Document
import difflib

# ─────────────────────────────────────────────
# 페이지 설정 (V15 원본 동일)
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="AI Citation Analyzer",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "dark_mode" not in st.session_state:
    st.session_state["dark_mode"] = False

_dark = st.session_state["dark_mode"]

# ─────────────────────────────────────────────
# 글로벌 CSS — V15 원본 스타일 복구
# ─────────────────────────────────────────────
if _dark:
    _bg, _bg2, _card, _border, _text, _text_muted = "#0F0F0F", "#1A1A1A", "#1E1E1E", "#333333", "#F0F0F0", "#999999"
    _header_gr = "linear-gradient(135deg,#1A1A1A 0%,#2A2A2A 60%,#3A3A3A 100%)"
    _sidebar_gr = "linear-gradient(180deg,#0F0F0F 0%,#1A1A1A 50%,#222222 100%)"
    _btn_gr = "linear-gradient(135deg,#333333,#555555)"
else:
    _bg, _bg2, _card, _border, _text, _text_muted = "#F5F5F5", "#EEEEEE", "#FFFFFF", "#DDDDDD", "#111111", "#666666"
    _header_gr = "linear-gradient(135deg,#111111 0%,#333333 60%,#555555 100%)"
    _sidebar_gr = "linear-gradient(180deg,#111111 0%,#222222 50%,#333333 100%)"
    _btn_gr = "linear-gradient(135deg,#111111,#444444)"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');
:root {{ --bg: {_bg}; --bg2: {_bg2}; --card: {_card}; --border: {_border}; --text: {_text}; --text-muted: {_text_muted}; }}
html, body, [class*="css"], .stApp {{ font-family: 'Plus Jakarta Sans', sans-serif; background-color: var(--bg) !important; color: var(--text) !important; }}
.main-header {{ background: {_header_gr}; border-radius: 20px; padding: 36px 40px; margin-bottom: 28px; box-shadow: 0 8px 40px rgba(0,0,0,0.1); position: relative; overflow: hidden; }}
.main-header h1, .main-header p {{ color: white !important; margin: 0 !important; }}
.metric-card, .result-card {{ background: var(--card) !important; border-radius: 16px; padding: 22px 24px; border: 1px solid var(--border); box-shadow: 0 4px 24px rgba(0,0,0,0.05); color: var(--text); }}
.stTabs [data-baseweb="tab-list"] {{ background: {_tab_bg if 'tab_bg' in locals() else _bg2} !important; border-radius: 14px !important; padding: 6px !important; }}
.stButton > button {{ background: {_btn_gr} !important; color: white !important; border-radius: 12px !important; font-weight: 700 !important; padding: 12px 28px !important; border: none !important; }}
[data-testid="stSidebar"] {{ background: {_sidebar_gr} !important; }}
[data-testid="stSidebar"] * {{ color: white !important; }}
</style>
""", unsafe_allow_html=True)

# =========================
# 🧠 로직 파트 (캐싱/병렬 유지)
# =========================
CACHE = {}
def _hash_key(prompt: str, model: str):
    return hashlib.md5(f"{model}:{prompt}".encode()).hexdigest()

def cached_call(call_fn, prompt: str, model: str, ttl=3600):
    key = _hash_key(prompt, model)
    if key in CACHE:
        data, ts = CACHE[key]
        if time.time() - ts < ttl: return data
    try:
        result = call_fn(prompt)
        CACHE[key] = (result, time.time())
        return result
    except: return ""

def call_gpt(prompt):
    if "openai_key" not in st.session_state: return ""
    client = openai.OpenAI(api_key=st.session_state["openai_key"])
    def _call(p):
        res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": p}], max_tokens=300)
        return res.choices[0].message.content.strip()
    return cached_call(_call, prompt, "gpt")

def call_gemini(prompt):
    if "gemini_key" not in st.session_state: return ""
    def _call(p):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={st.session_state['gemini_key']}"
        body = {"contents": [{"parts": [{"text": p}]}]}
        res = requests.post(url, json=body)
        if res.status_code == 200: return res.json()["candidates"][0]["content"]["parts"][0]["text"]
        return ""
    return cached_call(_call, prompt, "gemini")

def build_variants(domain, brand):
    base = domain.split(".")[0]
    return list(set([base.lower(), domain.lower(), brand.lower(), brand.replace(" ", "").lower()]))

def is_brand_mentioned(text, variants):
    text = text.lower()
    for v in variants:
        if v in text: return True
        for word in text.split():
            if difflib.SequenceMatcher(None, word, v).ratio() > 0.75: return True
    return False

def generate_questions(brand, industry):
    prompt = f"{industry}에서 {brand} 관련 질문 5개 생성"
    res = call_gpt(prompt) or call_gemini(prompt)
    return [q.strip("- ").strip() for q in res.split("\n") if "?" in q][:5]

def run_simulation(question, domain, brand, n=20):
    variants = build_variants(domain, brand)
    use_gpt = "openai_key" in st.session_state
    use_gemini = "gemini_key" in st.session_state
    def single():
        prompt = f"질문: {question}\n답변:"
        hit, total = 0, 0
        if use_gpt:
            res = call_gpt(prompt)
            total += 1
            if is_brand_mentioned(res, variants): hit += 1
        if use_gemini:
            res = call_gemini(prompt)
            total += 1
            if is_brand_mentioned(res, variants): hit += 1
        return hit, total
    hits, total = 0, 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(single) for _ in range(n)]
        for f in futures:
            try:
                h, t = f.result()
                hits += h
                total += t
            except: pass
    rate = round((hits / total * 100), 1) if total > 0 else 0
    return hits, total, rate

def run_strategy(question, brand):
    prompt = f"{brand}이 '{question}'에서 노출을 높이는 전략 3가지"
    return call_gpt(prompt) or call_gemini(prompt)

def save_word_report(data):
    doc = Document()
    doc.add_heading(f"AI Citation Report: {data['brand']}", 0)
    for r in data["results"]:
        doc.add_heading(f"Q. {r['question']}", level=1)
        doc.add_paragraph(f"점유율: {r['rate']}% ({r['hits']}/{r['total']})")
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# =========================
# 🎨 사이드바 UI (V15 복구)
# =========================
with st.sidebar:
    st.markdown("<div class='sidebar-logo'><span class='logo-icon'>🔍</span><h2>AI Citation</h2></div>", unsafe_allow_html=True)
    
    _mode_label = "☀️ 라이트 모드 전환" if _dark else "🌙 다크 모드 전환"
    if st.button(_mode_label, use_container_width=True):
        st.session_state["dark_mode"] = not st.session_state["dark_mode"]
        st.rerun()

    st.markdown("### 🔐 API 설정")
    st.session_state["openai_key"] = st.text_input("OpenAI API Key", type="password", value=st.session_state.get("openai_key", ""))
    st.session_state["gemini_key"] = st.text_input("Gemini API Key", type="password", value=st.session_state.get("gemini_key", ""))
    
    st.divider()
    sim_count = st.slider("시뮬레이션 횟수", 10, 100, 30)

# =========================
# 🚀 메인 화면 UI (V15 복구)
# =========================
st.markdown("""
<div class="main-header">
    <h1>🔍 AI 검색 점유율 분석 대시보드</h1>
    <p>GPT & Gemini 엔진에서 우리 브랜드의 노출도를 측정합니다</p>
</div>
""", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["🤖 자동 분석형 (AI 질문 도출)", "✏️ 수동 분석형 (키워드 직접 입력)", "📅 AI 인용 히스토리"])

with tab1:
    st.markdown("<div class='result-card'><h4>🤖 AI 타겟 질문 자동 도출 방식</h4><p>URL을 입력하면 AI가 질문을 생성하고 점유율을 분석합니다.</p></div>", unsafe_allow_html=True)
    
    col_in1, col_in2, col_in3 = st.columns(3)
    brand_val = col_in1.text_input("🏷️ 브랜드명", "에이바헤어", key="auto_brand")
    domain_val = col_in2.text_input("🌐 도메인", "avahair.co.kr", key="auto_domain")
    industry_val = col_in3.text_input("🏭 산업군", "미용실 프랜차이즈", key="auto_ind")

    if st.button("🚀 자동 분석 시작", use_container_width=True):
        if not st.session_state.get("openai_key") and not st.session_state.get("gemini_key"):
            st.error("API 키를 입력해주세요.")
        else:
            report_data = {"brand": brand_val, "domain": domain_val, "created_at": str(datetime.datetime.now()), "results": []}
            questions = generate_questions(brand_val, industry_val)
            
            with st.spinner("AI 분석 진행 중..."):
                for q in questions:
                    hits, total, rate = run_simulation(q, domain_val, brand_val, n=sim_count)
                    st.markdown(f"<div class='metric-card'><h3>❓ {q}</h3>", unsafe_allow_html=True)
                    c1, c2, c3 = st.columns(3)
                    c1.metric("인용 횟수", f"{hits}회")
                    c2.metric("총 시도", f"{total}회")
                    c3.metric("점유율 (%)", f"{rate}%")
                    st.markdown("</div><br>", unsafe_allow_html=True)
                    report_data["results"].append({"question": q, "hits": hits, "total": total, "rate": rate})
            
            st.download_button("📥 Word 보고서 다운로드", save_word_report(report_data), file_name=f"report_{brand_val}.docx")

with tab2:
    st.info("수동 분석 기능은 준비 중입니다.")

with tab3:
    st.info("인용 히스토리 로그를 시각화하는 탭입니다.")
