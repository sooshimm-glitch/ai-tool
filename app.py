"""
AI Citation Analyzer — 리팩토링 메인 앱
개선 사항:
1. TTL 캐싱 (비용 폭탄 방지)
2. 문맥 인식 인용 탐지 (false positive 최소화)
3. 3단계 fallback 크롤러
4. 구조화 에러 핸들링
5. 비용 추적기
"""

import streamlit as st
import datetime
import random
import re
import time
import pandas as pd
import plotly.graph_objects as go
from urllib.parse import urlparse

# ── 코어 모듈 임포트 ──
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from core.cache import TTLCache, get_cache
from core.logger import get_logger, CaptureError
from core.citation import build_brand_variants, wilson_ci
from core.crawler import crawl, crawl_search
from core.ai_client import (
    call_gpt, call_gemini,
    run_simulation, run_all_simulations,
    CostTracker, SimResult,
)
from core.biz_analysis import (
    analyze_business, discover_competitors,
    BusinessInfo, Competitor,
)
from core.question_generator import generate_target_questions
from core.strategy_analyzer import run_strategy_analysis
from core.pipeline import (
    run_pipeline, PipelineState,
    content_filter, citation_spot_check,
    render_debug_panel,
)
from core.demo_data import (
    DEMO_SCENARIOS, DEMO_STRATEGY,
    POSITION_COLORS, DIAGNOSE_ICONS, FP_RISK_ICONS,
    score_color as _score_color,
)

logger = get_logger("app")


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
# 세션 상태 초기화
# ─────────────────────────────────────────────
if "dark_mode"    not in st.session_state: st.session_state["dark_mode"]    = False
if "cache_data"   not in st.session_state: st.session_state["cache_data"]   = {}
if "cost_tracker" not in st.session_state: st.session_state["cost_tracker"] = CostTracker()
if "industry_display" not in st.session_state: st.session_state["industry_display"] = ""
if "brand_display"    not in st.session_state: st.session_state["brand_display"]    = ""

# 캐시 복원
_cache = get_cache()
if st.session_state["cache_data"]:
    _cache._store.update(
        TTLCache.from_serializable(st.session_state["cache_data"])._store
    )

_dark = st.session_state["dark_mode"]

# ─────────────────────────────────────────────
# 테마 변수
# ─────────────────────────────────────────────
if _dark:
    _bg = "#0F0F0F"; _bg2 = "#1A1A1A"; _card = "#1E1E1E"
    _border = "#333"; _text = "#F0F0F0"; _text_muted = "#999"
    _primary = "#E0E0E0"; _shadow = "0 4px 24px rgba(0,0,0,.5)"
    _header_gr = "linear-gradient(135deg,#1A1A1A,#2A2A2A,#3A3A3A)"
    _sidebar_gr = "linear-gradient(180deg,#0F0F0F,#1A1A1A,#222)"
    _metric_bg = "#252525"; _input_bg = "rgba(255,255,255,.07)"
    _btn_gr = "linear-gradient(135deg,#333,#555)"
    _tab_bg = "#1E1E1E"; _tab_sel = "#333"
    _progress = "linear-gradient(90deg,#555,#888)"
else:
    _bg = "#F5F5F5"; _bg2 = "#EEE"; _card = "#FFF"
    _border = "#DDD"; _text = "#111"; _text_muted = "#666"
    _primary = "#111"; _shadow = "0 4px 24px rgba(0,0,0,.08)"
    _header_gr = "linear-gradient(135deg,#111,#333,#555)"
    _sidebar_gr = "linear-gradient(180deg,#111,#222,#333)"
    _metric_bg = "#FFF"; _input_bg = "#FFF"
    _btn_gr = "linear-gradient(135deg,#111,#444)"
    _tab_bg = "#FFF"; _tab_sel = "#111"
    _progress = "linear-gradient(90deg,#111,#555)"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');
:root {{
  --bg:{_bg}; --bg2:{_bg2}; --card:{_card}; --border:{_border};
  --text:{_text}; --text-muted:{_text_muted}; --primary:{_primary}; --shadow:{_shadow};
}}

/* ── 전체 기반 ── */
html, body {{ background-color:{_bg} !important; color:{_text} !important; }}
.stApp, .stApp > * {{ background:{_bg} !important; }}
.main .block-container {{ background:{_bg} !important; }}

/* ── 폰트 & 기본 글자색 — Streamlit 사용자 노출 요소만 지정 ── */
body, .stApp, .main, .block-container,
.stMarkdown, .stMarkdown *,
.stTextInput, .stTextArea, .stSelectbox,
.stButton, .stButton button,
[data-testid="stText"],
[data-testid="stWidgetLabel"],
[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] * {{
  font-family:'Plus Jakarta Sans',sans-serif !important;
}}

/* Streamlit이 쓰는 모든 텍스트 노드 색상 강제 적용 */
.stApp p, .stApp span, .stApp div,
.stApp label, .stApp small, .stApp strong,
.stMarkdown, .stMarkdown p, .stMarkdown li,
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3,
.stMarkdown h4, .stMarkdown h5, .stMarkdown h6,
[data-testid="stText"], [data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li {{
  color:{_text} !important;
}}

/* ── 메트릭 컴포넌트 ── */
div[data-testid="metric-container"] {{
  background:{_metric_bg} !important; border-radius:14px !important;
  padding:18px !important; border:1px solid {_border} !important;
  box-shadow:{_shadow} !important;
}}
div[data-testid="metric-container"] label,
div[data-testid="metric-container"] [data-testid="stMetricLabel"],
div[data-testid="metric-container"] [data-testid="stMetricLabel"] p,
div[data-testid="metric-container"] [data-testid="stMetricLabel"] span {{
  color:{_text_muted} !important; font-size:.8rem !important; font-weight:600 !important;
}}
div[data-testid="metric-container"] [data-testid="stMetricValue"],
div[data-testid="metric-container"] [data-testid="stMetricValue"] * {{
  color:{_text} !important; font-weight:700 !important;
}}
/* 델타(↑↓) — 라이트 모드에서 배경색 제거하고 글자만 */
div[data-testid="metric-container"] [data-testid="stMetricDelta"],
div[data-testid="metric-container"] [data-testid="stMetricDelta"] * {{
  color:{_text_muted} !important; font-size:.78rem !important;
  background:transparent !important;
}}
div[data-testid="metric-container"] [data-testid="stMetricDelta"] svg {{
  display:none !important;
}}

/* ── 입력창 레이블 ── */
.stTextInput label, .stTextArea label,
.stSelectbox label, .stSlider label,
.stRadio label, .stCheckbox label,
[data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] p {{
  color:{_text} !important; font-weight:600 !important;
}}

/* 입력 필드 자체 */
.stTextInput>div>div>input,
.stTextArea>div>div>textarea {{
  border-radius:12px !important; border:1.5px solid {_border} !important;
  background:{_input_bg} !important; color:{_text} !important;
  font-size:.9rem !important;
}}
.stTextInput>div>div>input::placeholder,
.stTextArea>div>div>textarea::placeholder {{
  color:{_text_muted} !important;
}}

/* ── 셀렉트박스 ── */
.stSelectbox>div>div,
.stSelectbox [data-baseweb="select"] > div {{
  background:{_input_bg} !important; border:1.5px solid {_border} !important;
  border-radius:12px !important; color:{_text} !important;
}}
.stSelectbox [data-baseweb="select"] span {{
  color:{_text} !important;
}}
/* 드롭다운 메뉴 */
[data-baseweb="popover"] [data-baseweb="menu"],
[data-baseweb="popover"] li {{
  background:{_card} !important; color:{_text} !important;
}}

/* ── 슬라이더 ── */
.stSlider [data-testid="stTickBar"] span,
.stSlider p {{ color:{_text} !important; }}

/* ── 라디오 버튼 ── */
.stRadio > div > label > div > p {{ color:{_text} !important; }}

/* ── 탭 ── */
.stTabs [data-baseweb="tab-list"] {{
  background:{_tab_bg} !important; border-radius:14px !important;
  padding:6px !important; border:1px solid {_border} !important;
}}
.stTabs [data-baseweb="tab"] {{
  border-radius:10px !important; font-weight:600 !important;
  font-size:.9rem !important; color:{_text_muted} !important; padding:10px 22px !important;
  background:transparent !important;
}}
.stTabs [aria-selected="true"] {{
  background:{_tab_sel} !important;
  color:{"white" if not _dark else "#F0F0F0"} !important;
  box-shadow:0 4px 12px rgba(0,0,0,.3) !important;
}}
.stTabs [data-baseweb="tab"] p {{ color:inherit !important; }}

/* ── 버튼 ── */
.stButton>button {{
  background:{_btn_gr} !important; color:white !important;
  border:none !important; border-radius:12px !important; font-weight:700 !important;
  padding:12px 28px !important; transition:all .2s !important;
}}
.stButton>button:hover {{ transform:translateY(-2px) !important; opacity:.92 !important; }}
.stButton>button p {{ color:white !important; }}

/* ── 프로그레스 바 ── */
.stProgress>div>div>div {{ background:{_progress} !important; border-radius:8px !important; }}

/* ── 사이드바 — 다크 고정 ── */
[data-testid="stSidebar"] {{ background:{_sidebar_gr} !important; }}
[data-testid="stSidebar"] *:not(.stButton>button) {{ color:white !important; }}
[data-testid="stSidebar"] .stTextInput>div>div>input {{
  background:rgba(255,255,255,.12) !important;
  border:1px solid rgba(255,255,255,.25) !important; color:white !important;
}}
[data-testid="stSidebar"] .stSelectbox>div>div {{
  background:rgba(255,255,255,.1) !important;
  border:1px solid rgba(255,255,255,.2) !important; color:white !important;
}}
[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] span {{ color:white !important; }}
[data-testid="stSidebar"] .stSlider [role="slider"] {{ background:white !important; }}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span {{ color:white !important; }}

/* ── expander ── */
.streamlit-expander {{
  background:{_card} !important; border:1px solid {_border} !important; border-radius:12px !important;
}}
.streamlit-expander summary {{ color:{_text} !important; }}
.streamlit-expander summary p {{ color:{_text} !important; }}

/* ── 데이터프레임 ── */
[data-testid="stDataFrame"] {{ background:{_card} !important; }}
[data-testid="stDataFrame"] * {{ color:{_text} !important; background:{_card} !important; }}

/* ── 헤더 카드 ── */
.main-header {{
  background:{_header_gr}; border-radius:20px; padding:36px 40px;
  margin-bottom:28px; box-shadow:{_shadow};
}}
.main-header h1 {{ color:white !important; font-size:2rem !important; font-weight:800 !important; margin:0 !important; }}
.main-header p  {{ color:rgba(255,255,255,.82) !important; font-size:1rem !important; margin:8px 0 0 !important; }}
.metric-card,.result-card {{
  background:{_card} !important; border-radius:16px; padding:22px 24px;
  border:1px solid {_border}; box-shadow:{_shadow};
}}
.result-card h4 {{ color:{_text} !important; }}
.result-card p {{ color:{_text} !important; }}

/* ── 사이드바 로고 ── */
.sidebar-logo {{ text-align:center; padding:20px 0 24px; border-bottom:1px solid rgba(255,255,255,.15); margin-bottom:20px; }}
.sidebar-logo .logo-icon {{ font-size:2.5rem; display:block; margin-bottom:8px; }}
.sidebar-logo h2 {{ color:white !important; font-size:1.1rem !important; font-weight:800 !important; margin:0 !important; }}
.sidebar-logo p  {{ color:rgba(255,255,255,.6) !important; font-size:.75rem !important; margin:4px 0 0 !important; }}

/* ── 배지 ── */
.share-badge-high {{ display:inline-block; background:linear-gradient(135deg,#10B981,#059669); color:white !important; padding:4px 12px; border-radius:20px; font-size:.85rem; font-weight:700; }}
.share-badge-mid  {{ display:inline-block; background:linear-gradient(135deg,#F59E0B,#D97706); color:white !important; padding:4px 12px; border-radius:20px; font-size:.85rem; font-weight:700; }}
.share-badge-low  {{ display:inline-block; background:linear-gradient(135deg,#EF4444,#DC2626); color:white !important; padding:4px 12px; border-radius:20px; font-size:.85rem; font-weight:700; }}
.cost-badge  {{ background:rgba(16,185,129,.15); border:1px solid #10B981; color:#059669 !important; padding:4px 10px; border-radius:8px; font-size:.78rem; font-weight:600; }}
.cache-badge {{ background:rgba(99,102,241,.15); border:1px solid #6366F1; color:#4F46E5 !important; padding:4px 10px; border-radius:8px; font-size:.78rem; font-weight:600; }}

/* ── 인라인 카드 / 전략카드 / GEO ── */
.inline-card {{
  background:{_card}; border:1px solid {_border};
  border-radius:10px; padding:11px 16px; margin:5px 0;
  display:flex; align-items:center; gap:12px;
}}
.inline-card .q-text {{ font-size:.9rem; color:{_text} !important; font-weight:500; flex:1; }}
.strategy-item {{
  background:{_card}; border-radius:12px; padding:14px 16px;
  margin:8px 0; border:1px solid {_border};
}}
.strategy-item span {{ font-size:.85rem; color:{_text} !important; }}
.blue-ocean-item {{
  background:{_bg2}; border-radius:12px; padding:12px 16px;
  margin:8px 0; border:1px solid {_border};
  display:flex; align-items:center; gap:10px;
}}
.blue-ocean-item .label {{
  background:linear-gradient(135deg,#111,#444); color:white !important;
  padding:3px 10px; border-radius:20px; font-size:.75rem; font-weight:700;
}}
.blue-ocean-item .kw {{ font-size:.88rem; color:{_text} !important; font-weight:600; }}
.geo-guide-item {{
  background:{_card}; border-radius:14px; padding:18px 20px;
  margin:10px 0; border:1px solid {_border}; box-shadow:0 2px 12px rgba(0,0,0,.06);
}}
.geo-guide-item .geo-text {{ margin:0; font-size:.88rem; color:{_text} !important; line-height:1.8; word-break:keep-all; }}
.hist-empty {{ text-align:center; padding:48px; color:{_text_muted}; }}
.app-footer {{ text-align:center; padding:20px; color:{_text_muted}; font-size:.8rem; border-top:1px solid {_border}; }}

/* ── 토글 ── */
.stToggle label p {{ color:{_text} !important; }}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 유틸
# ─────────────────────────────────────────────
def normalize_url(url: str) -> str:
    if not url.startswith("http"):
        url = "https://" + url
    return url.rstrip("/")


def extract_domain(url: str) -> str:
    try:
        p = urlparse(url if url.startswith("http") else "https://" + url)
        return p.netloc.replace("www.", "")
    except Exception:
        return url


def save_cache():
    """세션 상태에 캐시 직렬화 저장"""
    with CaptureError("save_cache", log_level="debug"):
        st.session_state["cache_data"] = _cache.to_serializable()


# ─────────────────────────────────────────────
# 차트 렌더링
# ─────────────────────────────────────────────
def render_bar_chart(results: list, questions: list[str], title: str = "AI 엔진별 인용 점유율"):
    if not results:
        return

    short_q = [q[:18] + "…" if len(q) > 20 else q for q in questions]

    # SimResult 또는 dict 모두 지원
    def _get(r, k, default=None):
        if isinstance(r, dict):
            return r.get(k, default)
        return getattr(r, k, default)

    gpt_rates    = [_get(r, "gpt_rate")    for r in results]
    gemini_rates = [_get(r, "gemini_rate") for r in results]
    has_gpt    = any(v is not None for v in gpt_rates)
    has_gemini = any(v is not None for v in gemini_rates)

    fig = go.Figure()
    if has_gpt:
        fig.add_trace(go.Bar(
            name="GPT", x=short_q,
            y=[v or 0 for v in gpt_rates],
            marker=dict(color="#111111", line=dict(color="#000", width=1)),
            text=[f"{v:.1f}%" if v is not None else "" for v in gpt_rates],
            textposition="outside",
        ))
    if has_gemini:
        fig.add_trace(go.Bar(
            name="Gemini", x=short_q,
            y=[v or 0 for v in gemini_rates],
            marker=dict(color="#888888"),
            text=[f"{v:.1f}%" if v is not None else "" for v in gemini_rates],
            textposition="outside",
        ))

    all_vals = [v for v in gpt_rates + gemini_rates if v is not None]
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color=_text, family="Plus Jakarta Sans"), x=0),
        barmode="group", bargap=0.25,
        plot_bgcolor=_bg2, paper_bgcolor=_card,
        font=dict(family="Plus Jakarta Sans", color=_text),
        xaxis=dict(tickfont=dict(size=11), gridcolor=_border),
        yaxis=dict(title="인용 점유율 (%)", ticksuffix="%", gridcolor=_border,
                   range=[0, max(max(all_vals, default=0) + 15, 20)]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=60, b=40, l=50, r=20), height=380,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_strategy(strategy: dict, target_url: str):
    domain = extract_domain(target_url)

    st.markdown("### 🏆 AI 인용 경쟁 현황 (TOP 10)")
    for comp in strategy.get("competitors", [])[:10]:
        r = comp.get("rank", "?")
        d = comp.get("domain", "")
        b = comp.get("brand_name", d)
        reason = comp.get("reason", "")
        pos = comp.get("position", "")
        is_t = domain.lower() in d.lower()
        bg = "linear-gradient(135deg,#EEE,#E0E0E0)" if is_t else "#F8F8F8"
        bd = "#111" if is_t else "#DDD"
        lbl = " ← 내 사이트" if is_t else ""
        pc = POSITION_COLORS.get(pos, "#888")
        pb = (f'<span style="background:{pc};color:white;padding:2px 8px;border-radius:20px;'
              f'font-size:.72rem;font-weight:700;margin-left:8px;">{pos}</span>' if pos else "")
        st.markdown(f"""
        <div style="display:flex;align-items:center;justify-content:space-between;
        padding:11px 16px;border-radius:10px;margin:5px 0;background:{bg};border:1.5px solid {bd};">
          <div style="display:flex;align-items:center;gap:12px;">
            <div style="width:28px;height:28px;border-radius:8px;
            background:{'linear-gradient(135deg,#111,#444)' if is_t else '#CCC'};
            color:white;font-weight:700;font-size:.8rem;display:flex;align-items:center;justify-content:center;">{r}</div>
            <span style="font-weight:{'700' if is_t else '500'};color:var(--text);font-size:.9rem;">
            {b} <span style="color:var(--text-muted);font-size:.78rem;">({d})</span>{lbl}{pb}</span>
          </div>
          <span style="color:var(--text-muted);font-size:.8rem;">{reason}</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<hr style='border:none;height:1px;background:linear-gradient(90deg,transparent,#DDD,transparent);margin:20px 0;'>",
                unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 🔬 인용 실패 원인 진단")
        for i, d in enumerate(strategy.get("diagnoses", [])):
            col = ["#111", "#555", "#888"][i % 3]
            icon = DIAGNOSE_ICONS[i % len(DIAGNOSE_ICONS)]
            st.markdown(f"""
            <div class="strategy-item" style="border-left:4px solid {col};">
              <span>{icon} {d}</span>
            </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown("### 🌊 블루오션 키워드")
        for kw in strategy.get("keywords", []):
            st.markdown(f"""
            <div class="blue-ocean-item">
              <span class="label">NEW</span>
              <span class="kw">{kw}</span>
            </div>""", unsafe_allow_html=True)

    st.markdown("### 📋 GEO 최적화 가이드")
    for i, g in enumerate(strategy.get("geo_guides", [])):
        import re as _re
        g_html = _re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', g)
        g_html = g_html.replace('\n', '<br>')
        st.markdown(f"""
        <div class="geo-guide-item">
          <div style="display:flex;gap:12px;align-items:flex-start;">
            <div style="min-width:30px;height:30px;border-radius:8px;flex-shrink:0;
            background:linear-gradient(135deg,#111,#444);color:white;font-weight:800;
            font-size:.85rem;display:flex;align-items:center;justify-content:center;">{i+1}</div>
            <div class="geo-text">{g_html}</div>
          </div>
        </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 데모 데이터
# ─────────────────────────────────────────────
def get_demo(url: str) -> dict:
    domain = extract_domain(url).lower()
    for k in DEMO_SCENARIOS:
        if k != "default" and k in domain:
            return {"scenario": DEMO_SCENARIOS[k], "strategy": DEMO_STRATEGY}
    return {"scenario": DEMO_SCENARIOS["default"], "strategy": DEMO_STRATEGY}


# ─────────────────────────────────────────────
# 사이드바
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div class="sidebar-logo">
        <span class="logo-icon">🔍</span>
        <h2>AI Citation Analyzer</h2>
        <p>v2.0 — 비용 최적화 · 정밀 탐지</p>
    </div>""", unsafe_allow_html=True)

    if st.button("🌙 다크 모드" if not _dark else "☀️ 라이트 모드",
                 key="btn_dark", use_container_width=True):
        st.session_state["dark_mode"] = not _dark
        st.rerun()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    openai_key  = st.text_input("OpenAI API Key",  type="password", placeholder="sk-...")
    gemini_key  = st.text_input("Gemini API Key",  type="password", placeholder="AIza...")
    gpt_model   = st.selectbox("GPT 모델", ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"])
    gemini_model_name = st.selectbox("Gemini 모델",
        ["models/gemini-2.0-flash", "models/gemini-flash-latest"])

    st.markdown("---")
    sim_count = st.slider("시뮬레이션 횟수", 10, 100, 50, 10,
        help="적응형 조기 종료로 실제 비용은 설정값보다 낮을 수 있습니다")
    market_scope  = st.radio("경쟁사 범위", ["국내 (대한민국)", "글로벌"], horizontal=True)
    n_competitors = st.slider("경쟁사 수", 3, 10, 5)

    st.markdown("---")

    # 연결 상태
    gpt_ok    = bool(openai_key and openai_key.startswith("sk-"))
    gemini_ok = bool(gemini_key and len(gemini_key) > 10)

    c1, c2 = st.columns(2)
    c1.markdown("🟢 **GPT**" if gpt_ok else "⚪ **GPT**")
    c2.markdown("🟢 **Gemini**" if gemini_ok else "🔴 **Gemini**")

    # 비용 추적
    tracker: CostTracker = st.session_state["cost_tracker"]
    cost_summary = tracker.summary()
    if cost_summary["api_calls"] > 0:
        st.markdown(f"""
        <div style="background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.2);
        border-radius:8px;padding:10px 12px;margin-top:8px;font-size:.75rem;color:rgba(255,255,255,.85);">
        💰 누적 비용: ~${cost_summary['estimated_usd']:.4f}<br>
        🔢 API 호출: {cost_summary['api_calls']}회
        </div>""", unsafe_allow_html=True)

    # 캐시 통계
    cache_stats = _cache.stats()
    if cache_stats["entries"] > 0:
        st.markdown(f"""
        <div style="background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.2);
        border-radius:8px;padding:8px 12px;margin-top:6px;font-size:.73rem;color:rgba(255,255,255,.75);">
        ⚡ 캐시 히트율: {cache_stats['hit_rate']}% ({cache_stats['entries']}개 저장)
        </div>""", unsafe_allow_html=True)

    if st.button("🗑️ 캐시 초기화", key="btn_clear_cache", use_container_width=True):
        _cache._store.clear()
        st.session_state["cache_data"] = {}
        st.session_state["cost_tracker"] = CostTracker()
        st.success("캐시 초기화 완료")

    st.markdown("---")
    st.markdown("**🔬 개발자 옵션**")
    debug_mode = st.toggle(
        "Debug 모드",
        value=st.session_state.get("debug_mode", False),
        key="debug_toggle",
        help="각 파이프라인 단계의 입출력, Content Filter 결과, Citation Spot-check를 표시합니다",
    )
    st.session_state["debug_mode"] = debug_mode

    st.markdown("---")
    if st.button("▶ 데모 실행", key="btn_demo_sidebar", use_container_width=True):
        st.session_state["run_demo"] = True


# ─────────────────────────────────────────────
# API 클라이언트 초기화
# ─────────────────────────────────────────────
def get_clients():
    client_gpt = None
    client_gemini = None
    if gpt_ok:
        with CaptureError("init_gpt", log_level="error"):
            import openai
            client_gpt = openai.OpenAI(api_key=openai_key)
    if gemini_ok:
        with CaptureError("init_gemini", log_level="error"):
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            client_gemini = genai.GenerativeModel(gemini_model_name)
    return client_gpt, client_gemini


# ─────────────────────────────────────────────
# 메인 헤더
# ─────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>🔍 AI 검색 점유율 분석 대시보드</h1>
    <p>GPT & Gemini AI 엔진에서 내 사이트 인용 점유율 측정 — 비용 최적화 · 문맥 인식 · 3단계 크롤링</p>
</div>""", unsafe_allow_html=True)

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("분석 엔진", "GPT + Gemini", "2개 동시")
col2.metric("시뮬레이션", f"{sim_count}회", "적응형 조기종료")
col3.metric("API 연결", f"{(1 if gpt_ok else 0)+(1 if gemini_ok else 0)}/2", "활성화")
col4.metric("캐시 저장", f"{_cache.stats()['entries']}개", f"히트율 {_cache.stats()['hit_rate']}%")
col5.metric("누적 비용", f"~${tracker.summary()['estimated_usd']:.4f}", "USD 추정")

st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["🤖 자동 분석형", "✏️ 수동 분석형", "📅 히스토리"])

client_gpt, client_gemini = get_clients()


# ─────────────────────────────────────────────
# Tab 1: 자동 분석형
# ─────────────────────────────────────────────
with tab1:
    st.markdown("""
    <div class="result-card" style="background:linear-gradient(135deg,#F5F5F5,#EEE);border-color:#CCC;">
        <h4>🤖 AI 타겟 질문 자동 도출 방식</h4>
        <p style="color:#475569;font-size:.88rem;margin:0;line-height:1.6;">
        <b>파이프라인:</b> Crawl → Biz 분석 → 경쟁사(병렬) → 질문 생성(크롤 컨텍스트 반영) → Citation Spot-Check → 시뮬레이션<br>
        <b>개선</b>: 크롤 데이터 전 단계 공유 · Content Filter · 문맥 인식 탐지 · TTL 캐시 · Debug 모드
        </p>
    </div>""", unsafe_allow_html=True)

    col_u, col_i, col_b = st.columns([2, 1, 1])
    with col_u:
        url_auto = st.text_input("🌐 사이트 URL", placeholder="예) naver.com", key="url_auto")
    with col_i:
        # key와 value를 동시에 쓰면 rerun 시 위젯이 사라지는 버그 발생.
        # session_state 키만 사용하고 value= 는 제거한다.
        if "industry_widget" not in st.session_state:
            st.session_state["industry_widget"] = st.session_state.get("industry_display", "")
        manual_industry = st.text_input(
            "🏭 업종 확인·수정",
            placeholder="AI 자동 분석 → 직접 수정 가능",
            key="industry_widget",
        )
        st.session_state["industry_display"] = st.session_state["industry_widget"]
    with col_b:
        if "brand_widget" not in st.session_state:
            st.session_state["brand_widget"] = st.session_state.get("brand_display", "")
        st.text_input(
            "🏷️ 브랜드명 확인·수정",
            placeholder="AI 자동 추출 → 직접 수정 가능",
            key="brand_widget",
        )
        st.session_state["brand_display"] = st.session_state["brand_widget"]

    c_pre, c_run, c_demo = st.columns([1, 2, 1])
    with c_pre:
        pre_clicked = st.button("🔍 업종 미리 분석", key="btn_pre", use_container_width=True)
    with c_run:
        run_auto = st.button("🚀 자동 분석 시작", key="btn_auto", use_container_width=True)
    with c_demo:
        demo_auto = st.button("🎬 데모", key="btn_demo_auto", use_container_width=True)

    q_engine = st.radio("질문 도출 엔진", ["GPT", "Gemini"], horizontal=True)

    # ── 업종 미리 분석 ──
    if pre_clicked:
        if not url_auto.strip():
            st.warning("URL을 먼저 입력하세요.")
        elif not gpt_ok and not gemini_ok:
            st.warning("API 키가 필요합니다.")
        else:
            _pre_url = normalize_url(url_auto.strip())
            _pre_domain = extract_domain(_pre_url)
            status_box = st.empty()
            stages_log = []

            def _pre_cb(stage, msg):
                stages_log.append(f"[{stage}] {msg}")
                status_box.markdown(
                    "**파이프라인 진행:**\n" +
                    "\n".join(f"- {s}" for s in stages_log[-4:])
                )

            with st.spinner("크롤링 → 업종 분석 중..."):
                with CaptureError("pre_pipeline", log_level="warning") as ctx:
                    _pre_state = run_pipeline(
                        client_gpt, client_gemini,
                        url=_pre_url, model_gpt=gpt_model,
                        confirmed_industry="",
                        confirmed_brand="",
                        q_engine=q_engine,
                        market_scope=market_scope,
                        n_competitors=0,          # 미리 분석은 경쟁사 생략
                        tracker=tracker,
                        use_cache=True,
                        debug=st.session_state.get("debug_mode", False),
                        status_callback=_pre_cb,
                    )
                if not ctx.ok:
                    st.error(f"분석 실패: {ctx.error}")
                else:
                    biz = _pre_state.biz_info
                    cr  = _pre_state.crawl_result
                    st.session_state["industry_display"] = biz.industry
                    st.session_state["industry_widget"] = biz.industry   # ← rerun 후 위젯 유지
                    st.session_state["brand_display"] = biz.brand_name
                    st.session_state["brand_widget"] = biz.brand_name     # ← rerun 후 위젯 유지
                    st.session_state["pre_pipeline_state"] = {
                        "url": _pre_url,
                        "biz": biz.to_dict(),
                        "crawl_ok": cr.ok if cr else False,
                        "crawl_tier": cr.tier_used if cr else 0,
                    }
                    col_p1, col_p2, col_p3, col_p4 = st.columns(4)
                    col_p1.metric("브랜드", biz.brand_name)
                    col_p2.metric("업종", biz.industry[:20])
                    col_p3.metric("크롤 Tier", f"Tier{cr.tier_used if cr else 0}")
                    col_p4.metric("신뢰도", biz.confidence)
                    if biz.key_services:
                        st.caption("📋 주요 서비스: " + " · ".join(biz.key_services[:4]))
                    st.info("업종이 맞지 않으면 위 입력창에서 수정 후 [자동 분석 시작]을 누르세요.")

                    if st.session_state.get("debug_mode") and _pre_state:
                        render_debug_panel(_pre_state)

                    save_cache()
                    st.rerun()

    # ── 데모 ──
    elif demo_auto or st.session_state.get("run_demo"):
        st.session_state["run_demo"] = False
        demo_url = normalize_url(url_auto.strip() if url_auto.strip() else "naver.com")
        domain_d = extract_domain(demo_url)
        dd = get_demo(demo_url)

        st.info(f"🎬 데모 모드 — {domain_d} 샘플 데이터")

        prog = st.progress(0)
        for i, q in enumerate(dd["scenario"]["questions"]):
            st.markdown(f"⏳ Q{i+1}: *{q[:50]}*")
            prog.progress((i+1)/5)
            time.sleep(0.1)
        prog.progress(1.0)
        st.success("✅ 데모 완료")

        for i, q in enumerate(dd["scenario"]["questions"], 1):
            st.markdown(f"""
            <div class="inline-card">
              <span style="background:linear-gradient(135deg,#333,#666);color:white;
              min-width:26px;height:26px;border-radius:8px;font-weight:700;font-size:.8rem;
              display:flex;align-items:center;justify-content:center;">{i}</span>
              <span class="q-text">{q}</span>
            </div>""", unsafe_allow_html=True)

        render_bar_chart(dd["scenario"]["results"], dd["scenario"]["questions"],
                         f"[데모] {domain_d} 인용 점유율")

        for i, (q, r) in enumerate(zip(dd["scenario"]["questions"], dd["scenario"]["results"])):
            avg = (r["gpt_rate"] + r["gemini_rate"]) / 2
            with st.expander(f"Q{i+1}. {q[:50]}", expanded=(i == 0)):
                c1, c2, c3 = st.columns(3)
                c1.metric("GPT", f"{r['gpt_rate']}%")
                c2.metric("Gemini", f"{r['gemini_rate']}%")
                c3.metric("평균", f"{avg:.1f}%")
                render_strategy(dd["strategy"], demo_url)

    # ── 실제 분석 ──
    elif run_auto:
        if not url_auto:
            st.error("URL을 입력하세요.")
        elif not gpt_ok and not gemini_ok:
            st.error("API 키를 입력하세요.")
        else:
            target_url  = normalize_url(url_auto)
            domain      = extract_domain(target_url)
            debug_mode  = st.session_state.get("debug_mode", False)
            confirmed_industry = st.session_state["industry_display"].strip()
            confirmed_brand    = st.session_state["brand_display"].strip()

            # ── 파이프라인 진행 상태 표시 ──
            pipeline_status = st.container()
            prog_bar   = pipeline_status.progress(0)
            stage_text = pipeline_status.empty()
            stage_log  = []

            _stage_weights = {
                "crawl": 0.15, "biz": 0.30,
                "competitors": 0.40, "questions": 0.55,
                "spot_check": 0.65,
            }

            def _status_cb(stage: str, msg: str):
                stage_log.append(f"**[{stage}]** {msg}")
                w = _stage_weights.get(stage, 0.5)
                prog_bar.progress(w)
                stage_text.markdown(
                    "\n".join(stage_log[-3:]),
                    unsafe_allow_html=False
                )

            # ── Step 0: 사전 분석 캐시 재사용 확인 ──
            _pre_cached = st.session_state.get("pre_pipeline_state", {})
            _reuse_pre  = (
                _pre_cached.get("url") == target_url
                and _pre_cached.get("biz")
            )
            if _reuse_pre and not confirmed_industry:
                # 사전 분석 biz 재사용 → confirmed_industry에 업종 반영
                confirmed_industry = _pre_cached["biz"].get("industry", "")
                stage_text.info(
                    f"ℹ️ 사전 분석 재사용: "
                    f"{_pre_cached['biz'].get('brand_name','')} | "
                    f"{_pre_cached['biz'].get('industry','')}"
                )

            # ── Step 1: 파이프라인 실행 ──
            t_pipeline = time.time()
            pipeline_state: PipelineState
            with CaptureError("full_pipeline", log_level="warning") as pipe_ctx:
                pipeline_state = run_pipeline(
                    client_gpt, client_gemini,
                    url=target_url,
                    model_gpt=gpt_model,
                    confirmed_industry=confirmed_industry,
                    confirmed_brand=confirmed_brand,
                    q_engine=q_engine,
                    market_scope=market_scope,
                    n_competitors=n_competitors,
                    tracker=tracker,
                    use_cache=True,
                    debug=debug_mode,
                    status_callback=_status_cb,
                )

            if not pipe_ctx.ok:
                stage_text.error(f"파이프라인 오류: {pipe_ctx.error}")
                st.stop()

            elapsed_pipe = int(time.time() - t_pipeline)
            prog_bar.progress(0.65)
            stage_text.success(
                f"✅ 파이프라인 완료 ({elapsed_pipe}초) | "
                f"크롤 Tier{pipeline_state.crawl_result.tier_used if pipeline_state.crawl_result else 0} | "
                f"캐시 히트율 {_cache.stats()['hit_rate']}%"
            )

            save_cache()
            st.session_state["cost_tracker"] = tracker

            biz_info   = pipeline_state.biz_info
            questions  = pipeline_state.questions
            competitors = pipeline_state.competitors

            # ── Biz 분석 결과 요약 ──
            st.markdown("---")
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("브랜드", biz_info.brand_name)
            c2.metric("업종", biz_info.industry[:18])
            c3.metric("크롤 Tier", f"Tier {biz_info.crawl_tier}")
            c4.metric("신뢰도", biz_info.confidence)
            c5.metric("경쟁사", f"{len(competitors)}개")

            if biz_info.key_services:
                st.caption("📋 핵심 서비스: " + " · ".join(biz_info.key_services[:5]))

            # ── 업종 확정 UX — 변경 즉시 반영 안내 ──
            if biz_info.is_vague_industry():
                st.warning(
                    f"⚠️ 업종이 모호합니다: **{biz_info.industry}**\n"
                    "좌측 '업종 확인·수정'란에서 구체적인 업종을 입력 후 다시 실행하세요."
                )

            # ── Citation Spot-Check 결과 표시 ──
            spot = pipeline_state.spot_check
            if spot:
                fp_risk = spot.get("false_positive_risk", "unknown")
                fp_color = FP_RISK_ICONS.get(fp_risk, "⚪")
                st.markdown(
                    f"**🎯 Citation 정확도 Spot-Check** "
                    f"| 초기 추정: `{spot['hit_rate']}%` "
                    f"| FP 리스크: {fp_color} `{fp_risk}` "
                    f"| 샘플 {spot['n_samples']}회"
                )
                if fp_risk == "high":
                    st.warning(
                        "⚠️ False Positive 리스크 높음. "
                        "브랜드 변형 단어가 일반 문맥에서 오탐을 유발할 수 있습니다. "
                        "결과 해석 시 주의하세요."
                    )
                    if spot.get("suspect_variants"):
                        st.caption(f"오탐 의심 변형: {spot['suspect_variants']}")

            # ── 질문 목록 표시 ──
            if not questions:
                st.error("질문 생성 실패. 업종을 수동으로 입력 후 재시도하세요.")
                if debug_mode:
                    render_debug_panel(pipeline_state)
                st.stop()

            st.markdown(f"**📝 타겟 질문 {len(questions)}개 (Content Filter 통과)**")
            for i, q in enumerate(questions, 1):
                cf_result = content_filter(q, biz_info.brand_name)
                score_color = _score_color(cf_result["score"])
                st.markdown(f"""
                <div class="inline-card">
                  <span style="background:linear-gradient(135deg,#111,#444);color:white;
                  min-width:26px;height:26px;border-radius:8px;font-weight:700;font-size:.8rem;
                  display:flex;align-items:center;justify-content:center;">{i}</span>
                  <span class="q-text">{q}</span>
                  <span style="font-size:.75rem;font-weight:700;color:{score_color};white-space:nowrap;">
                  Q{cf_result['score']}</span>
                </div>""", unsafe_allow_html=True)

            # ── Step 2: 병렬 시뮬레이션 ──
            _n_engines = (1 if client_gpt else 0) + (1 if client_gemini else 0)
            st.markdown(
                f"**📊 병렬 시뮬레이션** "
                f"<span style='color:#888;font-size:.82rem;'>⚡ {sim_count}회 × "
                f"{len(questions)}개 × {_n_engines}엔진 | 문맥 인식 탐지 + 적응형 조기종료</span>",
                unsafe_allow_html=True
            )

            # spot-check refined_variants 사용 (FP 리스크 낮춤)
            refined_variants = spot.get("refined_variants") if spot else None

            sim_prog = st.progress(0.65)
            sim_stat = st.empty()
            sim_stat.markdown("🚀 전체 질문 병렬 실행 중...")

            t_sim = time.time()
            all_results: list[SimResult] = run_all_simulations(
                client_gpt, client_gemini, questions, target_url,
                model_gpt=gpt_model, n=sim_count,
                biz_info=biz_info.to_dict(),
                tracker=tracker,
                use_cache=True,
            )
            elapsed_sim = int(time.time() - t_sim)
            sim_prog.progress(1.0)
            sim_stat.success(
                f"✅ 시뮬레이션 완료! ({elapsed_sim}초) | "
                f"총 소요: {elapsed_pipe + elapsed_sim}초 | "
                f"추정비용 ~${tracker.summary()['estimated_usd']:.4f}"
            )

            save_cache()
            st.session_state["cost_tracker"] = tracker

            render_bar_chart(
                [r.to_dict() for r in all_results],
                questions,
                f"'{biz_info.brand_name}' AI 인용 점유율"
            )

            # ── 경쟁사 목록 간략 표시 ──
            if competitors:
                st.markdown("**🏢 도출된 경쟁사**")
                comp_cols = st.columns(min(len(competitors), 5))
                for i, comp in enumerate(competitors[:5]):
                    comp_cols[i].markdown(
                        f"**{comp.rank}.** {comp.brand_name}\n\n"
                        f"<span style='font-size:.75rem;color:#888;'>{comp.domain}</span>",
                        unsafe_allow_html=True
                    )

            # ── 질문별 상세 결과 ──
            st.markdown("### 📋 질문별 상세 결과")
            for i, (q, r) in enumerate(zip(questions, all_results)):
                gpt_v   = f"{r.gpt_rate}%"    if r.gpt_rate    is not None else "—"
                gem_v   = f"{r.gemini_rate}%" if r.gemini_rate is not None else "—"
                avg     = r.avg_rate or 0
                gpt_ci  = r.gpt_ci
                gem_ci  = r.gemini_ci
                ci_txt  = ""
                if gpt_ci and gpt_ci[0] is not None:
                    ci_txt += f"GPT {gpt_ci[0]}~{gpt_ci[1]}%"
                if gem_ci and gem_ci[0] is not None:
                    ci_txt += f" / Gem {gem_ci[0]}~{gem_ci[1]}%"

                cache_icon = "⚡" if r.cache_hit else ""
                cf_res = content_filter(q, biz_info.brand_name)
                cf_badge = f"Q{cf_res['score']}"

                with st.expander(
                    f"{cache_icon}Q{i+1}. {q[:55]}{'...' if len(q)>55 else ''} [{cf_badge}]",
                    expanded=(i == 0)
                ):
                    cc1, cc2, cc3, cc4 = st.columns(4)
                    cc1.metric("GPT",    gpt_v,
                               f"{r.gpt_hits}회/{r.n}" if r.gpt_hits is not None else "—")
                    cc2.metric("Gemini", gem_v,
                               f"{r.gemini_hits}회/{r.n}" if r.gemini_hits is not None else "—")
                    cc3.metric("평균", f"{avg:.1f}%")
                    cc4.metric("95% CI", ci_txt if ci_txt else "—")

                    if r.cache_hit:
                        st.markdown('<span class="cache-badge">⚡ 캐시 결과 (API 비용 없음)</span>',
                                    unsafe_allow_html=True)

                    # 인용 응답 샘플
                    samps = r.gpt_samples + r.gemini_samples
                    if samps:
                        with st.expander("💬 인용 응답 샘플 (문맥 인식 탐지)", expanded=False):
                            for s in samps[:3]:
                                st.markdown(f"""
                                <div style="background:#F5F5F5;border-radius:8px;padding:10px 14px;
                                margin:4px 0;font-size:.82rem;color:#374151;
                                border-left:3px solid #111;">{s}</div>""",
                                unsafe_allow_html=True)

                    # 전략 분석
                    with st.spinner("전략 분석 중..."):
                        with CaptureError("strategy", log_level="warning") as s_ctx:
                            strategy = run_strategy_analysis(
                                client_gpt, client_gemini, q, target_url,
                                model_gpt=gpt_model, biz_info=biz_info,
                                market_scope=market_scope,
                            )
                            render_strategy(strategy, target_url)
                            save_cache()
                        if not s_ctx.ok:
                            st.warning(f"전략 분석 오류: {s_ctx.error}")

            # ── Debug 패널 (하단) ──
            if debug_mode:
                render_debug_panel(pipeline_state)


# ─────────────────────────────────────────────
# Tab 2: 수동 분석형
# ─────────────────────────────────────────────
with tab2:
    st.markdown("""
    <div class="result-card" style="background:linear-gradient(135deg,#F5F5F5,#EEE);border-color:#CCC;">
        <h4>✏️ 직접 키워드/질문 입력 방식</h4>
        <p style="color:#475569;font-size:.88rem;margin:0;">
        분석 키워드를 직접 입력 → GPT + Gemini 동시 시뮬레이션 → 문맥 인식 인용 탐지
        </p>
    </div>""", unsafe_allow_html=True)

    c_u2, c_k = st.columns([1, 1])
    with c_u2:
        url_manual = st.text_input("🌐 URL", placeholder="예) coupang.com", key="url_manual")
    with c_k:
        keyword_input = st.text_input("🔍 키워드/질문", key="kw_input",
                                      placeholder="예) 국내 최고 배송 쇼핑몰은?")
    multi_kw = st.text_area("📝 추가 키워드 (선택, 줄당 하나, 최대 4개)", height=90, key="multi_kw")

    c_run2, c_demo2 = st.columns([2, 1])
    with c_run2:
        run_manual = st.button("🔬 분석 시작", key="btn_manual", use_container_width=True)
    with c_demo2:
        demo_manual = st.button("🎬 데모", key="btn_demo_manual", use_container_width=True)

    if demo_manual:
        demo_url_m = normalize_url(url_manual.strip() if url_manual.strip() else "coupang.com")
        dd_m = get_demo(demo_url_m)
        domain_m = extract_domain(demo_url_m)
        st.info(f"🎬 데모 — {domain_m}")
        qs_m = dd_m["scenario"]["questions"][:3]
        rs_m = dd_m["scenario"]["results"][:3]
        prog_m = st.progress(0)
        for i in range(3):
            prog_m.progress((i+1)/3)
            time.sleep(0.08)
        prog_m.progress(1.0)
        render_bar_chart(rs_m, qs_m, f"[데모] {domain_m} 키워드별 점유율")
        rows = [{"키워드": q, "GPT": f"{r['gpt_rate']}%", "Gemini": f"{r['gemini_rate']}%",
                 "평균": f"{(r['gpt_rate']+r['gemini_rate'])/2:.1f}%"}
                for q, r in zip(qs_m, rs_m)]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        render_strategy(dd_m["strategy"], demo_url_m)

    elif run_manual:
        if not url_manual:
            st.error("URL을 입력하세요.")
        elif not keyword_input:
            st.error("키워드를 입력하세요.")
        elif not gpt_ok and not gemini_ok:
            st.error("API 키를 입력하세요.")
        else:
            target_url_m = normalize_url(url_manual)
            domain_m     = extract_domain(target_url_m)
            all_kw = [keyword_input.strip()]
            if multi_kw.strip():
                all_kw += [k.strip() for k in multi_kw.strip().split("\n") if k.strip()][:4]
            all_kw = all_kw[:5]

            # 비즈니스 분석
            biz_m: BusinessInfo
            with st.spinner("업종 분석 중..."):
                with CaptureError("biz_manual", log_level="warning") as ctx_m:
                    biz_m = analyze_business(
                        client_gpt, client_gemini, target_url_m, model_gpt=gpt_model
                    )
                if not ctx_m.ok:
                    biz_m = BusinessInfo(
                        brand_name=domain_m.split(".")[0].upper(),
                        industry="서비스", industry_category="기타",
                        core_product="서비스", target_audience="고객",
                    )
                st.success(f"✅ {biz_m.brand_name} | {biz_m.industry} | Tier{biz_m.crawl_tier}")
                save_cache()

            # 경쟁사 도출
            comp_m: list[Competitor] = []
            with st.spinner(f"[{market_scope}] 경쟁사 분석 중..."):
                with CaptureError("comp_manual", log_level="warning"):
                    comp_m = discover_competitors(
                        client_gpt, client_gemini, biz_m, target_url_m,
                        market_scope=market_scope, model_gpt=gpt_model,
                        n_competitors=n_competitors,
                    )
                    st.success(f"✅ 경쟁사 {len(comp_m)}개 도출")
                    save_cache()

            # 시뮬레이션 — 병렬 실행 (run_all_simulations)
            all_results_m: list[SimResult] = []
            prog_m2 = st.progress(0)
            stat_m2 = st.empty()

            stat_m2.markdown(f"병렬 실행 중... ({len(all_kw)}개 키워드)")
            all_results_m = run_all_simulations(
                client_gpt, client_gemini, all_kw, target_url_m,
                model_gpt=gpt_model, n=sim_count,
                biz_info=biz_m.to_dict(),
                tracker=tracker,
                use_cache=True,
            )
            prog_m2.progress(1.0)
            stat_m2.success("✅ 완료!")
            save_cache()
            st.session_state["cost_tracker"] = tracker

            render_bar_chart(
                [r.to_dict() for r in all_results_m], all_kw,
                f"'{biz_m.brand_name}' 키워드별 인용 점유율"
            )

            # 결과 테이블
            rows_m = []
            for kw, r in zip(all_kw, all_results_m):
                vl = [v for v in [r.gpt_rate, r.gemini_rate] if v is not None]
                avg = sum(vl)/len(vl) if vl else 0
                ci_s = ""
                if r.gpt_ci and r.gpt_ci[0] is not None:
                    ci_s = f"GPT {r.gpt_ci[0]}~{r.gpt_ci[1]}%"
                rows_m.append({
                    "키워드": kw,
                    "GPT": f"{r.gpt_rate}%" if r.gpt_rate is not None else "—",
                    "Gemini": f"{r.gemini_rate}%" if r.gemini_rate is not None else "—",
                    "평균": f"{avg:.1f}%",
                    "95% CI": ci_s or "—",
                    "캐시": "⚡" if r.cache_hit else "—",
                    "상태": "✅" if avg >= 30 else ("⚡" if avg >= 10 else "❌"),
                })
            st.dataframe(pd.DataFrame(rows_m), use_container_width=True, hide_index=True)

            # 전략 분석
            for kw, r in zip(all_kw, all_results_m):
                st.markdown(f"---\n### 🎯 '{kw}' 전략 분석")
                with st.spinner("분석 중..."):
                    with CaptureError("strategy_m", log_level="warning") as s_ctx:
                        strat = run_strategy_analysis(
                            client_gpt, client_gemini, kw, target_url_m,
                            model_gpt=gpt_model, biz_info=biz_m,
                            market_scope=market_scope,
                        )
                        render_strategy(strat, target_url_m)
                        save_cache()
                    if not s_ctx.ok:
                        st.warning(f"전략 분석 오류: {s_ctx.error}")


# ─────────────────────────────────────────────
# Tab 3: 히스토리
# ─────────────────────────────────────────────
with tab3:
    st.markdown("""
    <div class="result-card" style="background:linear-gradient(135deg,#F5F5F5,#EEE);border-color:#CCC;">
        <h4>📅 AI 엔진별 브랜드 인용 히스토리</h4>
        <p style="color:#475569;font-size:.88rem;margin:0;">
        CSV 업로드 또는 데모 데이터로 ChatGPT · Gemini · Claude 인용 추이를 누적 막대그래프로 시각화합니다.
        </p>
    </div>""", unsafe_allow_html=True)

    ch1, ch2, ch3 = st.columns([1.2, 1, 1.5])
    with ch1:
        brand_h = st.text_input("🏷️ 브랜드명", placeholder="예) 네이버", key="brand_h")
    with ch2:
        log_file = st.file_uploader("📂 CSV (date,engine,count)", type=["csv"])
    with ch3:
        today = datetime.date.today()
        date_range = st.date_input("📆 분석 기간",
                                   value=(today - datetime.timedelta(29), today))

    rb1, rb2 = st.columns([2, 1])
    with rb1: run_hist = st.button("📊 히스토리 분석", key="btn_hist", use_container_width=True)
    with rb2: demo_hist = st.button("🎬 데모", key="btn_demo_hist", use_container_width=True)

    def gen_demo_hist(brand: str, days: int = 30) -> pd.DataFrame:
        random.seed(42)
        rows = []
        base = datetime.date.today() - datetime.timedelta(days - 1)
        for d in range(days):
            dt = base + datetime.timedelta(d)
            for eng, mu in [("ChatGPT", 12), ("Gemini", 9), ("Claude", 6)]:
                rows.append({"date": dt.strftime("%Y-%m-%d"), "engine": eng,
                              "count": max(0, int(random.gauss(mu, 3.5)))})
        return pd.DataFrame(rows)

    def render_hist(df: pd.DataFrame, brand: str):
        if df.empty:
            st.warning("데이터 없음")
            return
        pivot = df.pivot_table("count", "date", "engine", aggfunc="sum", fill_value=0).reset_index()
        pivot = pivot.sort_values("date")
        engs = [e for e in ["ChatGPT", "Gemini", "Claude"] if e in pivot.columns]
        colors = {"ChatGPT": "#111", "Gemini": "#555", "Claude": "#999"}
        total = int(df["count"].sum())
        daily = df.groupby("date")["count"].sum()
        peak_d = daily.idxmax() if not daily.empty else "—"
        peak_v = int(daily.max()) if not daily.empty else 0
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("총 인용", f"{total:,}회")
        m2.metric("최다 일자", peak_d, f"{peak_v}회")
        m3.metric("분석 일수", f"{df['date'].nunique()}일")
        m4.metric("브랜드", brand or "—")
        fig = go.Figure()
        for eng in engs:
            fig.add_trace(go.Bar(
                name=eng, x=pivot["date"], y=pivot[eng],
                marker_color=colors.get(eng, "#AAA"),
                text=pivot[eng].apply(lambda v: str(v) if v > 0 else ""),
                textposition="inside", textfont=dict(size=10, color="white"),
            ))
        fig.update_layout(
            barmode="stack", title=f"{'['+brand+'] ' if brand else ''}AI 엔진별 인용 추이",
            plot_bgcolor=_bg2, paper_bgcolor=_card,
            font=dict(family="Plus Jakarta Sans"), height=420,
            xaxis=dict(tickangle=-35, gridcolor=_border),
            yaxis=dict(gridcolor=_border),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(t=60, b=60, l=55, r=20),
        )
        st.plotly_chart(fig, use_container_width=True)

    if demo_hist:
        b = brand_h.strip() or "MyBrand"
        render_hist(gen_demo_hist(b), b)
    elif run_hist:
        if log_file is None:
            st.error("CSV 파일을 업로드하세요.")
        else:
            df_r = pd.read_csv(log_file)
            df_r.columns = [c.strip().lower() for c in df_r.columns]
            if not all(c in df_r.columns for c in ["date","engine","count"]):
                st.error("date, engine, count 컬럼이 필요합니다.")
            else:
                df_r["date"] = pd.to_datetime(df_r["date"]).dt.strftime("%Y-%m-%d")
                if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
                    s, e = date_range[0].strftime("%Y-%m-%d"), date_range[1].strftime("%Y-%m-%d")
                    df_r = df_r[(df_r["date"] >= s) & (df_r["date"] <= e)]
                render_hist(df_r, brand_h.strip())
    else:
        st.markdown("""
        <div class="hist-empty">
          <div style="font-size:3rem;margin-bottom:12px;">📊</div>
          <div style="font-size:1rem;font-weight:600;">CSV 업로드 또는 데모를 실행하세요</div>
          <div style="font-size:.82rem;margin-top:6px;">컬럼 형식: date, engine, count</div>
        </div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 푸터
# ─────────────────────────────────────────────
st.markdown("<div style='height:40px'></div>", unsafe_allow_html=True)
st.markdown("""
<div class="app-footer">
  🔍 AI Citation Analyzer v2.0 — 문맥 인식 탐지 · TTL 캐싱 · 3단계 크롤러 · 비용 추적
</div>""", unsafe_allow_html=True)
