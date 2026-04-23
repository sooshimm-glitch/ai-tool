"""
AI Citation Analyzer v3.0 — 통합형

변경사항:
- 자동/수동 탭 통합 → 질문은 사용자가 직접 입력
- 결과는 기존 자동분석형 양식 그대로 (차트 + 경쟁사 TOP5 + 진단 + 키워드 + GEO)
- 히스토리 탭 유지
"""

import streamlit as st
import re
import time
import pandas as pd
import plotly.graph_objects as go
from urllib.parse import urlparse

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from core.cache import TTLCache, get_cache
from core.logger import get_logger, CaptureError
from core.citation import build_brand_variants
from core.ai_client import run_all_simulations, CostTracker, SimResult
from core.biz_analysis import run_strategy_analysis, BusinessInfo, Competitor
from core.pipeline import content_filter, citation_spot_check

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
if "history"      not in st.session_state: st.session_state["history"]      = []

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
    _bg         = "#0F0F0F"; _bg2        = "#1A1A1A"; _card       = "#1E1E1E"
    _border     = "#333333"; _text       = "#F0F0F0"; _text_muted = "#999999"
    _shadow     = "0 4px 24px rgba(0,0,0,.5)"
    _header_gr  = "linear-gradient(135deg,#1A1A1A,#2A2A2A,#3A3A3A)"
    _sidebar_gr = "linear-gradient(180deg,#0F0F0F,#1A1A1A,#222222)"
    _metric_bg  = "#252525"; _input_bg   = "rgba(255,255,255,.07)"
    _btn_gr     = "linear-gradient(135deg,#333,#555)"
    _tab_bg     = "#1E1E1E"; _tab_sel    = "#333333"; _tab_txt    = "#F0F0F0"
    _progress   = "linear-gradient(90deg,#555,#888)"
    _plot_bg    = "rgba(30,30,30,.9)";  _plot_paper = "#1E1E1E"
    _plot_font  = "#F0F0F0"; _plot_grid  = "#333"
else:
    _bg         = "#F5F5F5"; _bg2        = "#EEEEEE"; _card       = "#FFFFFF"
    _border     = "#DDDDDD"; _text       = "#111111"; _text_muted = "#666666"
    _shadow     = "0 4px 24px rgba(0,0,0,.08)"
    _header_gr  = "linear-gradient(135deg,#111,#333,#555)"
    _sidebar_gr = "linear-gradient(180deg,#111,#222,#333)"
    _metric_bg  = "#FFFFFF"; _input_bg   = "#FFFFFF"
    _btn_gr     = "linear-gradient(135deg,#111,#444)"
    _tab_bg     = "#FFFFFF"; _tab_sel    = "#111111"; _tab_txt    = "#FFFFFF"
    _progress   = "linear-gradient(90deg,#111,#555)"
    _plot_bg    = "rgba(245,245,245,.8)"; _plot_paper = "#FFFFFF"
    _plot_font  = "#111111"; _plot_grid  = "#DDDDDD"

# ─────────────────────────────────────────────
# 글로벌 CSS
# ─────────────────────────────────────────────

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');

html, body {{ background-color:{_bg} !important; color:{_text} !important; }}
.stApp, .stApp > * {{ background:{_bg} !important; }}
.main .block-container {{ background:{_bg} !important; }}
*, *::before, *::after {{ font-family:'Plus Jakarta Sans',sans-serif !important; }}

.stApp p, .stApp span, .stApp div, .stApp label, .stApp small, .stApp strong,
.stMarkdown, .stMarkdown p, .stMarkdown li,
.stMarkdown h1,.stMarkdown h2,.stMarkdown h3,.stMarkdown h4,.stMarkdown h5,.stMarkdown h6,
[data-testid="stText"],[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li {{
    color:{_text} !important;
    -webkit-text-fill-color:{_text} !important;
}}

div[data-testid="metric-container"] {{
    background:{_metric_bg} !important; border-radius:14px !important;
    padding:18px !important; border:1px solid {_border} !important;
    box-shadow:{_shadow} !important;
}}
div[data-testid="metric-container"] [data-testid="stMetricLabel"],
div[data-testid="metric-container"] [data-testid="stMetricLabel"] p,
div[data-testid="metric-container"] [data-testid="stMetricLabel"] span {{
    color:{_text_muted} !important; -webkit-text-fill-color:{_text_muted} !important;
    font-size:.8rem !important; font-weight:600 !important;
}}
div[data-testid="metric-container"] [data-testid="stMetricValue"],
div[data-testid="metric-container"] [data-testid="stMetricValue"] * {{
    color:{_text} !important; -webkit-text-fill-color:{_text} !important;
    font-size:1.6rem !important; font-weight:800 !important;
}}
div[data-testid="metric-container"] [data-testid="stMetricDelta"],
div[data-testid="metric-container"] [data-testid="stMetricDelta"] * {{
    color:{_text_muted} !important; background:transparent !important;
}}
div[data-testid="metric-container"] [data-testid="stMetricDelta"] svg {{ display:none !important; }}

.stTextInput label,.stTextArea label,.stSelectbox label,.stSlider label,
.stRadio label,.stCheckbox label,
[data-testid="stWidgetLabel"],[data-testid="stWidgetLabel"] p {{
    color:{_text} !important; -webkit-text-fill-color:{_text} !important; font-weight:600 !important;
}}
.stTextInput>div>div>input, .stTextArea>div>div>textarea {{
    border-radius:12px !important; border:1.5px solid {_border} !important;
    background:{_input_bg} !important; color:{_text} !important;
    -webkit-text-fill-color:{_text} !important; font-size:.9rem !important;
}}
.stTextInput>div>div>input::placeholder, .stTextArea>div>div>textarea::placeholder {{
    color:{_text_muted} !important;
}}
.stSelectbox>div>div, .stSelectbox [data-baseweb="select"]>div {{
    background:{_input_bg} !important; border:1.5px solid {_border} !important;
    border-radius:12px !important; color:{_text} !important;
}}
.stSelectbox [data-baseweb="select"] span {{ color:{_text} !important; }}
[data-baseweb="popover"] [data-baseweb="menu"],[data-baseweb="popover"] li {{
    background:{_card} !important; color:{_text} !important;
}}

.stTabs [data-baseweb="tab-list"] {{
    background:{_tab_bg} !important; border-radius:14px !important;
    padding:6px !important; border:1px solid {_border} !important;
}}
.stTabs [data-baseweb="tab"] {{
    border-radius:10px !important; font-weight:600 !important; font-size:.9rem !important;
    color:{_text_muted} !important; -webkit-text-fill-color:{_text_muted} !important;
    padding:10px 22px !important; background:transparent !important;
}}
.stTabs [aria-selected="true"] {{
    background:{_tab_sel} !important;
    color:{_tab_txt} !important; -webkit-text-fill-color:{_tab_txt} !important;
    box-shadow:0 4px 12px rgba(0,0,0,.3) !important;
}}
.stTabs [data-baseweb="tab"] p,.stTabs [data-baseweb="tab"] span {{
    color:inherit !important; -webkit-text-fill-color:inherit !important;
}}

.stButton>button {{
    background:{_btn_gr} !important; color:white !important;
    -webkit-text-fill-color:white !important;
    border:none !important; border-radius:12px !important;
    font-weight:700 !important; padding:12px 28px !important; transition:all .2s !important;
}}
.stButton>button:hover {{ transform:translateY(-2px) !important; opacity:.92 !important; }}
.stButton>button p {{ color:white !important; -webkit-text-fill-color:white !important; }}

.stProgress>div>div>div {{ background:{_progress} !important; border-radius:8px !important; }}

[data-testid="stSidebar"] {{ background:{_sidebar_gr} !important; }}
[data-testid="stSidebar"] *:not(.stButton>button) {{
    color:white !important; -webkit-text-fill-color:white !important;
}}
[data-testid="stSidebar"] .stTextInput>div>div>input {{
    background:rgba(255,255,255,.12) !important;
    border:1px solid rgba(255,255,255,.25) !important;
    color:white !important; -webkit-text-fill-color:white !important;
}}
[data-testid="stSidebar"] .stSelectbox>div>div {{
    background:rgba(255,255,255,.1) !important;
    border:1px solid rgba(255,255,255,.2) !important;
}}
[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] span {{
    color:white !important; -webkit-text-fill-color:white !important;
}}

.streamlit-expander {{
    background:{_card} !important; border:1px solid {_border} !important; border-radius:12px !important;
}}
.streamlit-expander summary,
.streamlit-expander summary p {{ color:{_text} !important; -webkit-text-fill-color:{_text} !important; }}
.streamlit-expander [data-testid="stMarkdownContainer"] p,
.streamlit-expander p, .streamlit-expander span {{
    color:{_text} !important; -webkit-text-fill-color:{_text} !important;
}}

[data-testid="stDataFrame"] {{ background:{_card} !important; }}
[data-testid="stDataFrame"] * {{ color:{_text} !important; background:{_card} !important; }}

/* ── 헤더 ── */
.main-header {{
    background:{_header_gr}; border-radius:20px; padding:36px 40px;
    margin-bottom:28px; box-shadow:{_shadow};
}}
.stApp .main-header h1, div.main-header h1 {{
    color:white !important; -webkit-text-fill-color:white !important;
    font-size:2rem !important; font-weight:800 !important; margin:0 !important;
}}
.stApp .main-header p, div.main-header p {{
    color:rgba(255,255,255,.85) !important; -webkit-text-fill-color:rgba(255,255,255,.85) !important;
    font-size:1rem !important; margin:8px 0 0 !important;
}}

/* ── 카드 ── */
.result-card {{
    background:{_card} !important; border-radius:16px; padding:22px 24px;
    border:1px solid {_border}; box-shadow:{_shadow};
}}
.result-card h4 {{ color:{_text} !important; }}
.result-card p  {{ color:{_text} !important; }}

/* ── 인라인 카드 ── */
.inline-card {{
    background:{_card}; border:1px solid {_border};
    border-radius:10px; padding:11px 16px; margin:5px 0;
    display:flex; align-items:center; gap:12px;
}}
.inline-card .q-text {{ font-size:.9rem; color:{_text} !important; font-weight:500; flex:1; }}

/* ── 전략 카드 ── */
.strategy-item {{
    background:{_card}; border-radius:12px; padding:14px 16px;
    margin:8px 0; border:1px solid {_border};
}}
.strategy-item span {{
    font-size:.85rem; color:{_text} !important;
    word-break:keep-all; display:block; line-height:1.6;
}}
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
.geo-guide-item .geo-text {{
    margin:0; font-size:.88rem; color:{_text} !important; line-height:1.8; word-break:keep-all;
}}

/* ── 배지 ── */
.share-badge-high {{ display:inline-block; background:linear-gradient(135deg,#10B981,#059669); color:white !important; padding:4px 12px; border-radius:20px; font-size:.85rem; font-weight:700; }}
.share-badge-mid  {{ display:inline-block; background:linear-gradient(135deg,#F59E0B,#D97706); color:white !important; padding:4px 12px; border-radius:20px; font-size:.85rem; font-weight:700; }}
.share-badge-low  {{ display:inline-block; background:linear-gradient(135deg,#EF4444,#DC2626); color:white !important; padding:4px 12px; border-radius:20px; font-size:.85rem; font-weight:700; }}

/* ── 사이드바 로고 ── */
.sidebar-logo {{ text-align:center; padding:20px 0 24px; border-bottom:1px solid rgba(255,255,255,.15); margin-bottom:20px; }}
.sidebar-logo .logo-icon {{ font-size:2.5rem; display:block; margin-bottom:8px; }}
.sidebar-logo h2 {{ color:white !important; font-size:1.1rem !important; font-weight:800 !important; margin:0 !important; }}
.sidebar-logo p  {{ color:rgba(255,255,255,.6) !important; font-size:.75rem !important; margin:4px 0 0 !important; }}

.app-footer {{ text-align:center; padding:20px; color:{_text_muted}; font-size:.8rem; border-top:1px solid {_border}; }}
.stToggle label p {{ color:{_text} !important; }}
[data-testid="stAlert"] p,[data-testid="stAlert"] span {{ color:{_text} !important; }}
.stCaptionContainer p {{ color:{_text_muted} !important; }}
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
    with CaptureError("save_cache", log_level="debug"):
        st.session_state["cache_data"] = _cache.to_serializable()

# ─────────────────────────────────────────────
# 차트
# ─────────────────────────────────────────────

def render_bar_chart(results: list, questions: list[str], title: str = "AI 엔진별 인용 점유율"):
    if not results:
        return
    short_q = [q[:20] + "..." if len(q) > 22 else q for q in questions]

    def _get(r, k):
        return r.get(k) if isinstance(r, dict) else getattr(r, k, None)

    gpt_rates    = [_get(r, "gpt_rate")    for r in results]
    gemini_rates = [_get(r, "gemini_rate") for r in results]

    fig = go.Figure()
    if any(v is not None for v in gpt_rates):
        fig.add_trace(go.Bar(
            name="GPT", x=short_q,
            y=[v or 0 for v in gpt_rates],
            marker=dict(color="#444444" if _dark else "#111111"),
            text=[f"{v:.1f}%" if v is not None else "" for v in gpt_rates],
            textposition="outside", textfont=dict(color=_plot_font),
        ))
    if any(v is not None for v in gemini_rates):
        fig.add_trace(go.Bar(
            name="Gemini", x=short_q,
            y=[v or 0 for v in gemini_rates],
            marker=dict(color="#888888"),
            text=[f"{v:.1f}%" if v is not None else "" for v in gemini_rates],
            textposition="outside", textfont=dict(color=_plot_font),
        ))

    all_vals = [v for v in gpt_rates + gemini_rates if v is not None]
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color=_plot_font, family="Plus Jakarta Sans"), x=0),
        barmode="group", bargap=0.25,
        plot_bgcolor=_plot_bg, paper_bgcolor=_plot_paper,
        font=dict(family="Plus Jakarta Sans", color=_plot_font),
        xaxis=dict(tickfont=dict(size=11, color=_plot_font), gridcolor=_plot_grid),
        yaxis=dict(
            title="인용 점유율 (%)", ticksuffix="%",
            gridcolor=_plot_grid, tickfont=dict(color=_plot_font),
            range=[0, max(max(all_vals, default=0) + 15, 20)]
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    font=dict(color=_plot_font)),
        margin=dict(t=60, b=40, l=50, r=20), height=380,
    )
    st.plotly_chart(fig, use_container_width=True)


# ─────────────────────────────────────────────
# 전략 렌더링
# ─────────────────────────────────────────────

def render_strategy(strategy: dict, target_url: str):
    domain = extract_domain(target_url)

    # ── 경쟁사 TOP5 ──
    st.markdown("### 🏆 AI 인용 경쟁 현황 (TOP 5)")
    pos_colors = {
        "업계1위":"#10B981","업계 1위":"#10B981",
        "신흥강자":"#F59E0B","신흥 강자":"#F59E0B",
        "틈새전문":"#6366F1","틈새 전문":"#6366F1",
    }
    competitors = strategy.get("competitors", [])[:5]
    if competitors:
        for comp in competitors:
            r      = comp.get("rank", "?")
            d      = comp.get("domain", "")
            b      = comp.get("brand_name", d)
            reason = comp.get("reason", "")
            pos    = comp.get("position", comp.get("market_position", ""))
            is_t   = domain.lower() in d.lower()

            if _dark:
                bg = "linear-gradient(135deg,#2A2A2A,#333)" if is_t else "#1E1E1E"
                bd = "#888" if is_t else "#333"
            else:
                bg = "linear-gradient(135deg,#EEE,#E0E0E0)" if is_t else "#F8F8F8"
                bd = "#111" if is_t else "#DDD"

            lbl = " ← 내 사이트" if is_t else ""
            pc  = pos_colors.get(pos, "#888")
            pb  = (
                f'<span style="background:{pc};color:white;padding:2px 8px;'
                f'border-radius:20px;font-size:.72rem;font-weight:700;margin-left:8px;">{pos}</span>'
                if pos else ""
            )
            st.markdown(f"""
            <div style="display:flex;align-items:center;justify-content:space-between;
                padding:11px 16px;border-radius:10px;margin:5px 0;
                background:{bg};border:1.5px solid {bd};">
                <div style="display:flex;align-items:center;gap:12px;">
                    <div style="width:28px;height:28px;border-radius:8px;
                        background:linear-gradient(135deg,#111,#444);
                        color:white;font-weight:700;font-size:.8rem;
                        display:flex;align-items:center;justify-content:center;">{r}</div>
                    <span style="font-weight:{'700' if is_t else '500'};
                        color:{_text};font-size:.9rem;">
                        {b} <span style="color:{_text_muted};font-size:.78rem;">({d})</span>{lbl}{pb}
                    </span>
                </div>
                <span style="color:{_text_muted};font-size:.8rem;">{reason}</span>
            </div>""", unsafe_allow_html=True)
    else:
        st.caption("⚠️ 경쟁사 정보를 가져오지 못했습니다.")

    st.markdown(
        f"<hr style='border:none;height:1px;background:linear-gradient(90deg,transparent,{_border},transparent);margin:20px 0;'>",
        unsafe_allow_html=True
    )

    c1, c2 = st.columns(2)

    # ── 인용 실패 원인 진단 ──
    with c1:
        st.markdown("### 🔬 인용 실패 원인 진단")
        _icons = ["❌", "⚡", "🔧"]
        for i, d in enumerate(strategy.get("diagnoses", [])):
            col = ["#111" if not _dark else "#DDD", "#555", "#888"][i % 3]
            st.markdown(f"""
            <div class="strategy-item" style="border-left:4px solid {col};">
                <span>{_icons[i % len(_icons)]} {d}</span>
            </div>""", unsafe_allow_html=True)

    # ── 블루오션 키워드 ──
    with c2:
        st.markdown("### 🌊 블루오션 키워드")
        for kw in strategy.get("keywords", []):
            st.markdown(f"""
            <div class="blue-ocean-item">
                <span class="label">NEW</span>
                <span class="kw">{kw}</span>
            </div>""", unsafe_allow_html=True)

    # ── GEO 최적화 가이드 ──
    st.markdown("### 📋 GEO 최적화 가이드")
    for i, g in enumerate(strategy.get("geo_guides", [])):
        g_html = re.sub(r'\*\*(.*?)\*\*', rf'<strong style="color:{_text};">\1</strong>', g)
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
# 사이드바
# ─────────────────────────────────────────────

with st.sidebar:
    st.markdown("""
    <div class="sidebar-logo">
        <span class="logo-icon">🔍</span>
        <h2>AI Citation Analyzer</h2>
        <p>v3.0 — 통합 분석</p>
    </div>""", unsafe_allow_html=True)

    if st.button("🌙 다크 모드" if not _dark else "☀️ 라이트 모드",
                 key="btn_dark", use_container_width=True):
        st.session_state["dark_mode"] = not _dark
        st.rerun()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    openai_key        = st.text_input("OpenAI API Key",  type="password", placeholder="sk-...")
    gemini_key        = st.text_input("Gemini API Key",  type="password", placeholder="AIza...")
    gpt_model         = st.selectbox("GPT 모델",  ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"])
    gemini_model_name = st.selectbox("Gemini 모델", ["models/gemini-2.0-flash", "models/gemini-flash-latest"])

    st.markdown("---")

    sim_count    = st.slider("시뮬레이션 횟수", 10, 100, 30, 10,
                             help="횟수가 낮을수록 빠르고 저렴합니다")
    market_scope = st.radio("경쟁사 범위", ["국내 (대한민국)", "글로벌"], horizontal=True)

    st.markdown("---")

    gpt_ok    = bool(openai_key and openai_key.startswith("sk-"))
    gemini_ok = bool(gemini_key and len(gemini_key) > 10)

    c1, c2 = st.columns(2)
    c1.markdown("🟢 **GPT**"    if gpt_ok    else "⚪ **GPT**")
    c2.markdown("🟢 **Gemini**" if gemini_ok else "🔴 **Gemini**")

    tracker: CostTracker = st.session_state["cost_tracker"]
    cost_summary = tracker.summary()
    if cost_summary["api_calls"] > 0:
        st.markdown(f"""
        <div style="background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.2);
            border-radius:8px;padding:10px 12px;margin-top:8px;font-size:.75rem;color:rgba(255,255,255,.85);">
            💰 누적 비용: ~${cost_summary['estimated_usd']:.4f}<br>
            🔢 API 호출: {cost_summary['api_calls']}회
        </div>""", unsafe_allow_html=True)

    cache_stats = _cache.stats()
    if cache_stats["entries"] > 0:
        st.markdown(f"""
        <div style="background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.2);
            border-radius:8px;padding:8px 12px;margin-top:6px;font-size:.73rem;color:rgba(255,255,255,.75);">
            ⚡ 캐시 히트율: {cache_stats['hit_rate']}% ({cache_stats['entries']}개 저장)
        </div>""", unsafe_allow_html=True)

    if st.button("🗑️ 캐시 초기화", key="btn_clear_cache", use_container_width=True):
        _cache._store.clear()
        st.session_state["cache_data"]   = {}
        st.session_state["cost_tracker"] = CostTracker()
        st.success("캐시 초기화 완료")


# ─────────────────────────────────────────────
# API 클라이언트 초기화
# ─────────────────────────────────────────────

def get_clients():
    client_gpt = client_gemini = None
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
    <h1 style="color:white !important;-webkit-text-fill-color:white !important;
        font-size:2rem !important;font-weight:800 !important;margin:0 !important;">
        🔍 AI 검색 점유율 분석 대시보드</h1>
    <p style="color:rgba(255,255,255,.85) !important;-webkit-text-fill-color:rgba(255,255,255,.85) !important;
        font-size:1rem !important;margin:8px 0 0 !important;">
        GPT &amp; Gemini AI 엔진에서 내 사이트 인용 점유율 측정 — 질문 직접 입력 · 비용 최적화 · 정밀 탐지</p>
</div>""", unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)
col1.metric("분석 엔진",  "GPT + Gemini", "2개 동시")
col2.metric("시뮬레이션", f"{sim_count}회", "적응형 조기종료")
col3.metric("API 연결",   f"{(1 if gpt_ok else 0)+(1 if gemini_ok else 0)}/2", "활성화")
col4.metric("누적 비용",  f"~${tracker.summary()['estimated_usd']:.4f}", "USD 추정")

st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 탭: 분석 / 히스토리
# ─────────────────────────────────────────────

tab_main, tab_hist = st.tabs(["🔍 인용 점유율 분석", "📅 히스토리"])

client_gpt, client_gemini = get_clients()

# ═════════════════════════════════════════════
# 메인 분석 탭
# ═════════════════════════════════════════════

with tab_main:

    # ── 입력 영역 ──
    st.markdown(f"""
    <div class="result-card" style="margin-bottom:20px;">
        <h4 style="margin:0 0 4px 0;">📝 분석 설정</h4>
        <p style="color:{_text_muted};font-size:.85rem;margin:0;">
            사이트 URL · 브랜드명 · 업종을 입력하고, 분석할 질문을 최대 5개까지 직접 입력하세요.
        </p>
    </div>""", unsafe_allow_html=True)

    # URL + 브랜드 + 업종
    col_u, col_b, col_i = st.columns([2, 1, 1])
    with col_u:
        url_input = st.text_input(
            "🌐 사이트 URL *",
            placeholder="예) naver.com",
            key="url_input"
        )
    with col_b:
        brand_input = st.text_input(
            "🏷️ 브랜드명 *",
            placeholder="예) 프로그레스미디어",
            key="brand_input"
        )
    with col_i:
        industry_input = st.text_input(
            "🏭 업종 *",
            placeholder="예) 퍼포먼스 마케팅 광고대행사",
            key="industry_input"
        )

    # 질문 입력
    st.markdown(f"**🎯 분석할 질문 입력** <span style='color:{_text_muted};font-size:.82rem;'>최대 5개 · 실제 사용자가 AI에게 물어볼 법한 질문</span>",
                unsafe_allow_html=True)

    questions_input = []
    q_cols = st.columns(1)
    for idx in range(1, 6):
        q = st.text_input(
            f"Q{idx}",
            placeholder=f"예) 퍼포먼스 마케팅 대행사 ROAS 잘 나오는 곳 추천해줘?" if idx == 1
                        else f"질문 {idx}번 (선택)",
            key=f"q_input_{idx}",
            label_visibility="visible"
        )
        if q.strip():
            questions_input.append(q.strip())

    # 실행 버튼
    col_run, col_clear = st.columns([4, 1])
    with col_run:
        run_btn = st.button("🚀 분석 시작", key="btn_run", use_container_width=True)
    with col_clear:
        if st.button("🗑️ 초기화", key="btn_reset", use_container_width=True):
            for k in ["url_input","brand_input","industry_input"] + [f"q_input_{i}" for i in range(1,6)]:
                if k in st.session_state:
                    del st.session_state[k]
            st.rerun()

    # ── 입력 검증 ──
    if run_btn:
        errors = []
        if not url_input.strip():    errors.append("사이트 URL")
        if not brand_input.strip():  errors.append("브랜드명")
        if not industry_input.strip(): errors.append("업종")
        if not questions_input:      errors.append("질문 (최소 1개)")

        if errors:
            st.error(f"필수 입력 누락: {', '.join(errors)}")
        elif not gpt_ok and not gemini_ok:
            st.error("사이드바에서 API 키를 입력하세요.")
        else:
            target_url  = normalize_url(url_input.strip())
            domain      = extract_domain(target_url)
            brand_name  = brand_input.strip()
            industry    = industry_input.strip()

            # biz_info 구성
            biz_info = BusinessInfo(
                brand_name=brand_name,
                industry=industry,
                industry_category="기타",
                core_product=industry,
                target_audience="잠재 고객",
                confidence="high",
                crawl_tier=0,
            )

            st.markdown("---")

            # ── 진행 상태 ──
            prog = st.progress(0)
            stat = st.empty()

            # ── Step 1: 시뮬레이션 ──
            stat.markdown(f"⚡ **{len(questions_input)}개 질문 × {sim_count}회 시뮬레이션 중...**")
            prog.progress(0.1)

            t0 = time.time()
            all_results: list = run_all_simulations(
                client_gpt, client_gemini,
                questions_input, target_url,
                model_gpt=gpt_model, n=sim_count,
                biz_info=biz_info.to_dict(),
                tracker=tracker,
                use_cache=True,
            )
            elapsed_sim = int(time.time() - t0)
            prog.progress(0.6)

            save_cache()
            st.session_state["cost_tracker"] = tracker

            stat.success(
                f"✅ 시뮬레이션 완료 ({elapsed_sim}초) | "
                f"추정비용 ~${tracker.summary()['estimated_usd']:.4f}"
            )

            # ── 결과 요약 메트릭 ──
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("브랜드",   brand_name)
            c2.metric("업종",     industry[:18])
            c3.metric("질문 수",  f"{len(questions_input)}개")
            c4.metric("분석 엔진", f"{(1 if client_gpt else 0)+(1 if client_gemini else 0)}개")

            # ── 차트 ──
            render_bar_chart(
                [r.to_dict() if hasattr(r, "to_dict") else r for r in all_results],
                questions_input,
                f"'{brand_name}' AI 인용 점유율"
            )

            # ── 질문별 상세 결과 ──
            st.markdown("### 📋 질문별 상세 결과")
            for i, (q, r) in enumerate(zip(questions_input, all_results)):
                gpt_v   = f"{r.gpt_rate}%"    if hasattr(r,"gpt_rate")    and r.gpt_rate    is not None else "—"
                gem_v   = f"{r.gemini_rate}%" if hasattr(r,"gemini_rate") and r.gemini_rate is not None else "—"
                avg     = r.avg_rate if hasattr(r,"avg_rate") and r.avg_rate else 0
                gpt_ci  = r.gpt_ci  if hasattr(r,"gpt_ci")  else (None, None)

                badge_cls = (
                    "share-badge-high" if avg >= 30
                    else "share-badge-mid" if avg >= 10
                    else "share-badge-low"
                )
                with st.expander(
                    f"Q{i+1}. {q[:60]}{'...' if len(q)>60 else ''} — 평균 {avg:.1f}%",
                    expanded=(i == 0)
                ):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("GPT",    gpt_v)
                    c2.metric("Gemini", gem_v)
                    c3.metric("평균",   f"{avg:.1f}%")
                    if gpt_ci and gpt_ci[0] is not None and gpt_ci[1] is not None:
                        c4.metric("95% CI", f"{gpt_ci[0]:.1f}~{gpt_ci[1]:.1f}%")

                    st.markdown(
                        f'<span class="{badge_cls}">점유율 {avg:.1f}%</span>',
                        unsafe_allow_html=True
                    )
                    st.caption(f"질문: {q}")

            prog.progress(0.7)

            # ── Step 2: 전략 분석 ──
            stat.markdown("🧠 **전략 분석 생성 중...**")

            with CaptureError("strategy", log_level="warning") as s_ctx:
                strategy = run_strategy_analysis(
                    client_gpt, client_gemini,
                    biz_info=biz_info,
                    competitors=[],
                    sim_results=all_results,
                    questions=questions_input,
                    tracker=tracker,
                    target_url=target_url,
                    model_gpt=gpt_model,
                    market_scope=market_scope,
                    use_cache=True,
                )

            prog.progress(1.0)

            if s_ctx.ok and strategy:
                st.markdown("---")
                render_strategy(strategy, target_url)
                stat.success("✅ 전략 분석 완료!")
            else:
                st.warning("전략 분석을 완료하지 못했습니다. API 키를 확인하세요.")

            save_cache()
            st.session_state["cost_tracker"] = tracker

            # 히스토리 저장
            import datetime
            st.session_state["history"].append({
                "ts":       datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "domain":   domain,
                "brand":    brand_name,
                "industry": industry,
                "n_q":      len(questions_input),
                "questions": questions_input,
                "results":  [r.to_dict() if hasattr(r,"to_dict") else r for r in all_results],
            })


# ═════════════════════════════════════════════
# 히스토리 탭
# ═════════════════════════════════════════════

with tab_hist:
    history = st.session_state.get("history", [])
    if not history:
        st.markdown(f"""
        <div style="text-align:center;padding:60px 20px;">
            <div style="font-size:3rem;margin-bottom:12px;">📭</div>
            <p style="color:{_text_muted};font-size:1rem;">아직 분석 기록이 없습니다.</p>
            <p style="color:{_text_muted};font-size:.85rem;">분석을 실행하면 여기에 기록됩니다.</p>
        </div>""", unsafe_allow_html=True)
    else:
        for h in reversed(history[-20:]):
            with st.expander(
                f"🕐 {h.get('ts','')} — {h.get('brand','')} ({h.get('industry','')}) | {h.get('n_q',0)}개 질문",
                expanded=False
            ):
                if h.get("questions") and h.get("results"):
                    render_bar_chart(
                        h["results"], h["questions"],
                        f"{h.get('brand','')} 인용 점유율"
                    )
                    for i, (q, r) in enumerate(zip(h["questions"], h["results"])):
                        avg = r.get("avg_rate") or 0
                        st.caption(f"Q{i+1}. {q} → 평균 {avg:.1f}%")
                else:
                    st.json(h)


# ─────────────────────────────────────────────
# 푸터
# ─────────────────────────────────────────────

st.markdown(f"""
<div class="app-footer">
    AI Citation Analyzer v3.0 &nbsp;|&nbsp;
    <span style="color:{_text_muted};">Powered by GPT &amp; Gemini</span> &nbsp;|&nbsp;
    <span style="color:{_text_muted};">질문 직접 입력 · 비용 최적화 · TTL 캐시</span>
</div>""", unsafe_allow_html=True)
