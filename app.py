"""
AdCS Pro — 대대행 대응 자동화 솔루션
실행: streamlit run adcs_pro.py
필요 패키지: pip install streamlit google-generativeai PyPDF2 openpyxl python-docx
"""

import streamlit as st
import google.generativeai as genai
import io
import re
from datetime import datetime

# ─── Page Config ───────────────────────────────────────────────
st.set_page_config(
    page_title="AdCS Pro | 대대행 대응 자동화",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ────────────────────────────────────────────────
st.markdown("""
<style>
/* Import fonts */
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Noto Sans KR', sans-serif;
}

/* Hide default streamlit elements */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1.5rem; padding-bottom: 2rem; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #1a1a2e;
}
[data-testid="stSidebar"] * {
    color: #e8e6df !important;
}
[data-testid="stSidebar"] .stTextInput input {
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
    color: #e8e6df !important;
    font-size: 12px !important;
    border-radius: 8px !important;
}
[data-testid="stSidebar"] .stFileUploader {
    background: rgba(255,255,255,0.04) !important;
    border: 1.5px dashed rgba(255,255,255,0.15) !important;
    border-radius: 8px !important;
}
[data-testid="stSidebar"] label {
    font-size: 11px !important;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    font-weight: 600 !important;
    color: #8a8899 !important;
}
[data-testid="stSidebar"] .stMarkdown h3 {
    color: #ffffff !important;
    font-size: 17px !important;
}

/* ── Main Area ── */
.main-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 1.5rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid #e5e3dc;
}
.main-title {
    font-size: 20px;
    font-weight: 700;
    color: #1a1917;
}
.badge {
    font-size: 10px;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 20px;
    background: #dbeafe;
    color: #2563eb;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}

/* ── Detected media chips ── */
.chip-wrap { display: flex; gap: 6px; flex-wrap: wrap; margin: 6px 0 12px; }
.chip {
    font-size: 11px;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 20px;
    letter-spacing: 0.3px;
    display: inline-block;
}
.chip-naver  { background: rgba(3,199,90,0.12); color: #039950; }
.chip-kakao  { background: rgba(249,224,0,0.20); color: #9a7c00; }
.chip-daangn { background: rgba(255,111,15,0.12); color: #c25000; }
.chip-google { background: rgba(66,133,244,0.12); color: #1a56cc; }
.chip-meta   { background: rgba(24,119,242,0.12); color: #1877f2; }

/* ── Result box ── */
.result-box {
    background: #ffffff;
    border: 1px solid #e5e3dc;
    border-radius: 12px;
    padding: 22px 26px;
    margin-top: 0;
    box-shadow: 0 4px 16px rgba(0,0,0,0.07);
    line-height: 1.85;
    color: #1a1917;
    font-size: 14px;
    white-space: pre-wrap;
    word-break: keep-all;
}
.result-header-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: linear-gradient(to right, #f0f7ff, #fff);
    border: 1px solid #e5e3dc;
    border-bottom: none;
    border-radius: 12px 12px 0 0;
    padding: 12px 20px;
}
.result-label {
    font-size: 11px;
    font-weight: 700;
    color: #2563eb;
    text-transform: uppercase;
    letter-spacing: 0.8px;
}
.result-time {
    font-size: 10px;
    color: #8a8680;
}
.result-box-body {
    background: #ffffff;
    border: 1px solid #e5e3dc;
    border-top: none;
    border-radius: 0 0 12px 12px;
    padding: 20px 24px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.06);
}

/* ── Sources ── */
.sources-box {
    background: #f9f8f5;
    border: 1px solid #e5e3dc;
    border-radius: 8px;
    padding: 14px 16px;
    margin-top: 12px;
    font-size: 12px;
}
.sources-title {
    font-size: 10px;
    font-weight: 700;
    color: #8a8680;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 8px;
}

/* ── Loading steps ── */
.step-done   { color: #059669; font-weight: 500; }
.step-active { color: #2563eb; font-weight: 600; }
.step-idle   { color: #8a8680; }

/* ── Tips ── */
.tip-card {
    background: #fff;
    border: 1px solid #e5e3dc;
    border-radius: 10px;
    padding: 14px 16px;
    cursor: pointer;
    transition: all 0.2s;
    font-size: 13px;
    color: #4a4845;
    margin-bottom: 6px;
}
.tip-card:hover { border-color: #2563eb; background: #f0f7ff; }
.tip-media-label {
    font-size: 10px;
    font-weight: 700;
    color: #8a8680;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-bottom: 4px;
}

/* ── Stbutton overrides ── */
div[data-testid="stButton"] > button {
    border-radius: 8px !important;
    font-family: 'Noto Sans KR', sans-serif !important;
    font-weight: 500 !important;
    font-size: 13px !important;
    transition: all 0.18s !important;
}
div[data-testid="stButton"] > button[kind="primary"] {
    background: #2563eb !important;
    color: white !important;
    box-shadow: 0 2px 8px rgba(37,99,235,0.25) !important;
}
div[data-testid="stButton"] > button[kind="primary"]:hover {
    background: #1d4ed8 !important;
    box-shadow: 0 4px 12px rgba(37,99,235,0.35) !important;
}
div[data-testid="stButton"] > button[kind="secondary"] {
    border: 1px solid #dbeafe !important;
    color: #2563eb !important;
    background: #f8faff !important;
}

/* ── History items ── */
.hist-item {
    background: rgba(255,255,255,0.05);
    border-radius: 6px;
    padding: 7px 10px;
    margin-bottom: 4px;
    font-size: 11px;
    color: #a8a6b8;
    border: 1px solid transparent;
    word-break: keep-all;
    cursor: default;
}
.hist-item:hover { background: rgba(79,142,247,0.1); border-color: rgba(79,142,247,0.2); }

/* ── Error / Warning ── */
div[data-testid="stAlert"] {
    border-radius: 8px !important;
}

/* ── Mode selector ── */
.mode-bar {
    display: flex;
    gap: 0;
    background: #f1f0ec;
    border-radius: 10px;
    padding: 4px;
    margin-bottom: 16px;
}
.mode-btn {
    flex: 1;
    text-align: center;
    padding: 8px 12px;
    border-radius: 7px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    color: #8a8680;
    border: none;
    background: transparent;
}
.mode-btn.active-normal {
    background: #fff;
    color: #1a1917;
    box-shadow: 0 1px 4px rgba(0,0,0,0.1);
}
.mode-btn.active-precise {
    background: #2563eb;
    color: #fff;
    box-shadow: 0 2px 8px rgba(37,99,235,0.3);
}

/* ── Mode info card ── */
.mode-info {
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 16px;
    font-size: 12px;
    line-height: 1.7;
    display: flex;
    gap: 10px;
    align-items: flex-start;
}
.mode-info-normal {
    background: #f9f8f5;
    border: 1px solid #e5e3dc;
    color: #4a4845;
}
.mode-info-precise {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    color: #1e40af;
}
.mode-info-icon { font-size: 18px; flex-shrink: 0; margin-top: 1px; }
.mode-info-title { font-weight: 700; margin-bottom: 2px; font-size: 13px; }
.mode-tag {
    display: inline-block;
    font-size: 10px;
    font-weight: 700;
    padding: 1px 7px;
    border-radius: 20px;
    margin-left: 6px;
    vertical-align: middle;
}
.tag-free { background: #d1fae5; color: #065f46; }
.tag-paid { background: #dbeafe; color: #1e40af; }

/* ── Sidebar guideline highlight ── */
.guide-highlight {
    border: 1.5px solid #4f8ef7 !important;
    border-radius: 8px;
    padding: 10px;
    background: rgba(79,142,247,0.06);
}
.guide-dim {
    opacity: 0.45;
    pointer-events: none;
}

/* ── Result mode badge ── */
.result-mode-badge {
    font-size: 10px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 20px;
    letter-spacing: 0.3px;
}
.badge-normal  { background: #f3f4f6; color: #6b7280; }
.badge-precise { background: #dbeafe; color: #1d4ed8; }
</style>
""", unsafe_allow_html=True)


# ─── Session State Init ────────────────────────────────────────
defaults = {
    "answer": None,
    "sources": [],
    "gen_count": 0,
    "current_question": "",
    "conversation": [],
    "query_history": [],
    "guideline_text": "",
    "show_answer": False,
    "analysis_mode": "일반 모드",
    "last_mode": "일반 모드",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ─── Helper: extract text from uploaded files ──────────────────
def extract_file_text(uploaded_file) -> str:
    name = uploaded_file.name.lower()
    content = ""
    try:
        if name.endswith(".txt"):
            content = uploaded_file.read().decode("utf-8", errors="ignore")

        elif name.endswith(".pdf"):
            try:
                import PyPDF2
                reader = PyPDF2.PdfReader(io.BytesIO(uploaded_file.read()))
                content = "\n".join(
                    page.extract_text() or "" for page in reader.pages
                )
            except ImportError:
                content = "[PDF 파싱 불가 — pip install PyPDF2]"

        elif name.endswith((".xlsx", ".xls")):
            try:
                import openpyxl
                wb = openpyxl.load_workbook(io.BytesIO(uploaded_file.read()), data_only=True)
                rows = []
                for ws in wb.worksheets:
                    for row in ws.iter_rows(values_only=True):
                        rows.append("\t".join(str(c) if c is not None else "" for c in row))
                content = "\n".join(rows)
            except ImportError:
                content = "[XLSX 파싱 불가 — pip install openpyxl]"

        elif name.endswith((".docx", ".doc")):
            try:
                from docx import Document
                doc = Document(io.BytesIO(uploaded_file.read()))
                content = "\n".join(p.text for p in doc.paragraphs)
            except ImportError:
                content = "[DOCX 파싱 불가 — pip install python-docx]"

    except Exception as e:
        content = f"[파일 읽기 오류: {e}]"

    return content[:6000]  # token safety


# ─── Helper: detect media keywords ────────────────────────────
MEDIA_MAP = {
    "네이버": ("chip-naver", "🟢 네이버"),
    "당근": ("chip-daangn", "🟠 당근"),
    "카카오": ("chip-kakao", "🟡 카카오"),
    "구글": ("chip-google", "🔵 구글"),
    "메타": ("chip-meta", "🔵 메타"),
    "인스타": ("chip-meta", "🔵 메타"),
    "페이스북": ("chip-meta", "🔵 메타"),
    "틱톡": ("chip-meta", "⚫ 틱톡"),
    "유튜브": ("chip-google", "🔴 유튜브"),
}

def detect_media(text: str):
    found, seen = [], set()
    for kw, (cls, label) in MEDIA_MAP.items():
        if kw in text and label not in seen:
            found.append((cls, label))
            seen.add(label)
    return found


# ─── Helper: parse sources from answer ────────────────────────
def parse_sources(text: str):
    match = re.search(r"📌\s*참고 출처[:\s]*([\s\S]*?)$", text)
    if not match:
        return text, []
    main = text[: text.index(match.group(0))].strip()
    lines = [l.strip() for l in match.group(1).strip().split("\n") if l.strip()]
    return main, lines


# ─── Helper: build system prompt (mode-aware) ─────────────────
def build_system_prompt(question: str, guideline: str, gen_count: int, mode: str) -> str:
    media_found = detect_media(question)
    regen_note = (
        f"\n\n⚠️ 이전 답변과 완전히 다른 논리와 구성으로 새 답변을 생성하세요 ({gen_count}회차)."
        if gen_count > 1 else ""
    )

    if mode == "일반 모드":
        return f"""당신은 광고 대행사의 전문 CS 담당자입니다. 대대행사의 기술 질문에 대해 **마케팅 상식과 대행사 응대 노하우**만을 활용해 단 하나의 최적 답변을 제공합니다.

# 일반 모드 원칙
- 별도 파일 분석이나 실시간 검색 없이, AI가 보유한 광고 업계 지식으로만 답변합니다.
- 확실하지 않은 수치는 "일반적으로", "통상적으로" 등의 표현으로 명확히 구분하세요.
- 복수의 답변을 나열하지 않고, 가장 완벽한 단 하나의 답변만 제공합니다.
- 전문적이되 대대행사 담당자가 이해하기 쉬운 명확한 언어를 사용합니다.
{regen_note}

# 출력 형식
- 명확한 구조로 작성 (## 소제목 + 내용)
- 수치나 정책은 **굵게** 표시
- 답변 첫 줄: "> 💡 일반 상식 기반의 답변입니다. 정확한 수치는 매체 공식 공지를 확인해 주세요."
- 어체: 정중하고 전문적인 B2B 커뮤니케이션 스타일
- 출처 섹션 불필요 (일반 모드에서는 생략)"""

    # ── 정밀 분석 모드 ──
    media_note = (
        f"질문에 {', '.join(label for _, label in media_found)} 매체가 언급되어 있습니다. "
        "해당 매체의 최신 공식 정책과 공지사항을 기반으로 답변하고, "
        "답변 말미에 참고한 출처 URL을 '📌 참고 출처:' 섹션에 반드시 명시하세요."
        if media_found else
        "특정 매체가 명시적으로 언급되지 않았습니다. 일반적인 광고 운영 기준으로 답변하되 관련 출처를 포함하세요."
    )
    guideline_note = (
        f"다음은 회사 가이드라인 내용입니다. 이 말투와 기준에 맞게 답변하세요:\n\n{guideline}"
        if guideline else
        "별도 가이드라인 없음. 전문적이고 친절한 B2B 광고 대행사 어체를 사용하세요."
    )

    return f"""당신은 광고 대행사의 전문 CS 담당자입니다. 대대행사의 날카로운 기술 질문에 대해 **가이드라인과 최신 매체 정책**을 100% 반영한 팩트 중심의 단 하나의 최적 답변을 제공합니다.

# 정밀 분석 모드 원칙
- 광고 매체(네이버, 카카오, 당근마켓, 구글, 메타 등)의 최신 정책과 스펙을 정확히 반영합니다.
- 사내 가이드라인의 말투, 기준, 단가를 우선 적용합니다.
- 복수의 답변을 나열하지 않고, 가장 완벽한 단 하나의 답변만 제공합니다.
- 모든 수치와 정책 기준은 반드시 출처와 함께 제공합니다.

# 가이드라인
{guideline_note}

# 매체 감지 결과
{media_note}
{regen_note}

# 출력 형식
- 명확한 구조로 작성 (## 소제목 + 내용)
- 수치나 정책은 **굵게** 표시
- 답변 마지막에 "📌 참고 출처:" 섹션 반드시 포함
- 출처는 실제 공식 URL 형식으로 작성
- 답변 첫 줄: "> 🔬 가이드라인 및 실시간 검색 기반의 정밀 답변입니다."
- 어체: 정중하고 전문적인 B2B 커뮤니케이션 스타일"""


# ─── Helper: call Gemini API ──────────────────────────────────
def call_gemini(api_key: str, question: str, guideline: str, gen_count: int, mode: str) -> str:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        system_instruction=build_system_prompt(question, guideline, gen_count, mode),
    )

    # Build history for multi-turn (regen)
    history = []
    for msg in st.session_state.conversation:
        role = "user" if msg["role"] == "user" else "model"
        history.append({"role": role, "parts": [msg["content"]]})

    chat = model.start_chat(history=history)

    if gen_count > 1:
        user_msg = f"이전 답변({gen_count-1}회차)과는 다른 논리와 구성으로 새로운 최적 답변을 생성해주세요. 원래 질문: {question}"
    else:
        user_msg = question

    response = chat.send_message(user_msg)
    return response.text


# ══════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### 🎯 AdCS Pro")
    st.markdown(
        "<p style='font-size:11px;color:#6b6a80;text-transform:uppercase;"
        "letter-spacing:0.8px;margin-top:-8px;'>대대행 대응 자동화 솔루션</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # API Key
    st.markdown("**🔑 Gemini API Key**")
    api_key = st.text_input(
        "API Key",
        type="password",
        placeholder="AIzaSy...",
        label_visibility="collapsed",
    )
    if api_key:
        if api_key.startswith("AIza") and len(api_key) > 20:
            st.markdown(
                "<p style='font-size:11px;color:#34d399;margin-top:4px;'>● 연결됨</p>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<p style='font-size:11px;color:#f87171;margin-top:4px;'>● 키 형식 확인 필요</p>",
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            "<p style='font-size:11px;color:#6b6a80;margin-top:4px;'>● 미연결</p>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # File Upload — highlighted only in 정밀 분석 모드
    is_precise = st.session_state.get("analysis_mode") == "정밀 분석 모드"
    if is_precise:
        st.markdown(
            "<p style='font-size:11px;color:#4f8ef7;font-weight:700;"
            "text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px;'>"
            "📎 가이드라인 파일 <span style='font-size:10px;background:#4f8ef7;color:#fff;"
            "padding:1px 6px;border-radius:20px;'>정밀 분석 필수</span></p>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<p style='font-size:11px;color:#6b6a80;font-weight:600;"
            "text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px;'>"
            "📎 가이드라인 파일 <span style='font-size:10px;color:#4a4860;'>(정밀 모드 전용)</span></p>",
            unsafe_allow_html=True,
        )

    uploaded_files = st.file_uploader(
        "파일 업로드",
        accept_multiple_files=True,
        type=["pdf", "txt", "xlsx", "xls", "docx", "doc"],
        label_visibility="collapsed",
        disabled=not is_precise,
    )

    guideline_text = ""
    if uploaded_files:
        file_texts = []
        for f in uploaded_files:
            txt = extract_file_text(f)
            if txt:
                file_texts.append(f"=== {f.name} ===\n{txt}")
            st.markdown(
                f"<div class='hist-item'>📄 {f.name}</div>",
                unsafe_allow_html=True,
            )
        guideline_text = "\n\n".join(file_texts)
        st.session_state.guideline_text = guideline_text
    else:
        st.markdown(
            "<p style='font-size:11px;color:#6b6a80;'>PDF · TXT · XLSX · DOCX 지원</p>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # Supported media
    st.markdown("**📡 실시간 서칭 지원 매체**")
    st.markdown(
        """<div class='chip-wrap'>
        <span class='chip chip-naver'>네이버</span>
        <span class='chip chip-kakao'>카카오</span>
        <span class='chip chip-daangn'>당근</span>
        <span class='chip chip-google'>구글</span>
        <span class='chip chip-meta'>메타</span>
        </div>""",
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # Query history
    st.markdown("**🕐 최근 질문 기록**")
    if st.session_state.query_history:
        for q in st.session_state.query_history[-6:][::-1]:
            short = q[:45] + "..." if len(q) > 45 else q
            st.markdown(f"<div class='hist-item'>{short}</div>", unsafe_allow_html=True)
    else:
        st.markdown(
            "<p style='font-size:11px;color:#6b6a80;'>답변 생성 시 기록됩니다.</p>",
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown(
        "<p style='font-size:10px;color:#6b6a80;line-height:1.6;'>"
        "Powered by Gemini API<br>"
        "질문에 매체명이 포함되면<br>자동으로 공지를 검색합니다.</p>",
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════
#  MAIN CONTENT
# ══════════════════════════════════════════════════════════════
st.markdown(
    "<div class='main-header'>"
    "<span style='font-size:22px;'>📋</span>"
    "<span class='main-title'>CS 매체 대응 자동화</span>"
    "<span class='badge'>BETA</span>"
    "</div>",
    unsafe_allow_html=True,
)

# ── Mode Selector ─────────────────────────────────────────────
selected_mode = st.radio(
    "응대 모드 선택",
    options=["일반 모드", "정밀 분석 모드"],
    index=0 if st.session_state.analysis_mode == "일반 모드" else 1,
    horizontal=True,
    label_visibility="collapsed",
)

# Sync mode to session state and reset if mode changed
if selected_mode != st.session_state.analysis_mode:
    st.session_state.analysis_mode = selected_mode
    # Reset answer when mode switches
    st.session_state.show_answer = False
    st.session_state.answer = None
    st.session_state.sources = []
    st.session_state.gen_count = 0
    st.session_state.conversation = []
    st.rerun()

# Mode info card
if selected_mode == "일반 모드":
    st.markdown(
        "<div class='mode-info mode-info-normal'>"
        "<div class='mode-info-icon'>🧠</div>"
        "<div>"
        "<div class='mode-info-title'>일반 모드"
        "<span class='mode-tag tag-free'>API 비용 0원</span></div>"
        "가이드라인 파일·실시간 검색 없이 AI의 마케팅 상식과 대행사 응대 노하우로 즉시 답변합니다. "
        "429 쿼터 초과 위험이 낮고 빠른 응답에 적합합니다."
        "</div></div>",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        "<div class='mode-info mode-info-precise'>"
        "<div class='mode-info-icon'>🔬</div>"
        "<div>"
        "<div class='mode-info-title'>정밀 분석 모드"
        "<span class='mode-tag tag-paid'>건당 ~10원</span></div>"
        "업로드된 가이드라인을 정밀 분석하고 최신 매체 공지를 실시간 반영합니다. "
        "팩트 중심의 출처 포함 답변이 필요할 때 사용하세요. <b>좌측에서 가이드라인 파일을 업로드하세요.</b>"
        "</div></div>",
        unsafe_allow_html=True,
    )

# ── Question Input ─────────────────────────────────────────────
st.markdown("**대대행사 질문 입력**")
question = st.text_area(
    "질문",
    height=130,
    placeholder="예) 네이버 쇼핑 검색광고에서 최근 입찰가 최저 기준이 변경됐다고 하던데, "
                "현재 최소 입찰가 기준과 노출 조건이 어떻게 되나요? "
                "브랜드 키워드 제한 정책도 함께 알려주세요.",
    label_visibility="collapsed",
)

# Detected media chips
if question:
    media = detect_media(question)
    if media:
        chips_html = "<div class='chip-wrap'><span style='font-size:11px;color:#8a8680;margin-right:4px;'>감지:</span>"
        for cls, label in media:
            chips_html += f"<span class='chip {cls}'>{label}</span>"
        chips_html += "</div>"
        st.markdown(chips_html, unsafe_allow_html=True)

# ── Action buttons ────────────────────────────────────────────
col_gen, col_regen, col_clear = st.columns([2, 2, 1])

with col_gen:
    btn_label = "🧠 일반 답변 생성" if selected_mode == "일반 모드" else "🔬 정밀 답변 생성"
    generate_clicked = st.button(
        btn_label,
        type="primary",
        use_container_width=True,
    )

with col_regen:
    regen_clicked = False
    if st.session_state.show_answer:
        regen_clicked = st.button(
            "🔄 다른 논리로 답변 생성",
            type="secondary",
            use_container_width=True,
        )

with col_clear:
    if st.button("↺ 초기화", use_container_width=True):
        for k in ["answer", "sources", "gen_count", "current_question",
                  "conversation", "show_answer"]:
            st.session_state[k] = [] if k in ("sources", "conversation") else (
                0 if k == "gen_count" else (False if k == "show_answer" else (None if k == "answer" else ""))
            )
        st.rerun()

st.markdown("")

# ── Example prompts ───────────────────────────────────────────
EXAMPLES = [
    ("🟢 네이버", "네이버 GFA 영상광고 사이즈 정책이 최근 변경됐나요? 현재 지원 포맷과 해상도, 파일 용량 제한을 상세히 알려주세요."),
    ("🟠 당근", "당근마켓 지역 타겟팅 광고에서 반경 설정 최솟값이 어떻게 되나요? 최근 정책 변경 내용도 포함해 주세요."),
    ("🟡 카카오", "카카오모먼트 디스플레이 광고 소재 심사 기준 중 텍스트 비율 제한이 있나요? 예외 사항도 설명해 주세요."),
    ("🔵 구글", "구글 PMax 캠페인 전환 추적 설정 시 주의해야 할 최신 정책 변경 사항이 있나요? Enhanced Conversion 관련 내용도 포함해 주세요."),
]

if not st.session_state.show_answer:
    st.markdown(
        "<p style='font-size:11px;font-weight:600;color:#8a8680;"
        "text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;'>"
        "💡 예시 질문</p>",
        unsafe_allow_html=True,
    )
    ecols = st.columns(2)
    for i, (label, text) in enumerate(EXAMPLES):
        with ecols[i % 2]:
            if st.button(f"{label}\n{text[:55]}…", key=f"ex_{i}", use_container_width=True):
                st.session_state["_example_text"] = text
                st.rerun()

    if "_example_text" in st.session_state:
        question = st.session_state.pop("_example_text")
        st.session_state["_prefill"] = question
        st.rerun()

# ── Handle generation ─────────────────────────────────────────
def run_generation(q: str, is_regen: bool):
    if not api_key:
        st.error("⚠️ 왼쪽 사이드바에서 Gemini API Key를 먼저 입력해주세요.")
        return
    if not q.strip():
        st.error("⚠️ 질문을 입력해주세요.")
        return

    mode = st.session_state.analysis_mode

    if not is_regen:
        st.session_state.gen_count = 0
        st.session_state.current_question = q
        st.session_state.conversation = []
        st.session_state.last_mode = mode

    st.session_state.gen_count += 1

    # Loading steps differ by mode
    if mode == "일반 모드":
        steps = [
            "🧠 질문 분석 및 매체 키워드 파악 중...",
            "📚 마케팅 상식 기반 논리 구성 중...",
            "✍️ 최적 답변 초안 작성 중...",
            "✅ 품질 검토 완료!",
        ]
    else:
        steps = [
            "🔍 질문 분석 및 매체 감지 중...",
            "📂 가이드라인 파일 정밀 분석 중...",
            "🌐 최신 매체 공지사항 검색 중...",
            "✅ 팩트 검증 및 출처 정리 완료!",
        ]

    with st.status("답변을 생성하는 중...", expanded=True) as status:
        for step in steps[:-1]:
            st.write(step)

        guideline = st.session_state.guideline_text if mode == "정밀 분석 모드" else ""

        try:
            raw = call_gemini(
                api_key=api_key,
                question=q,
                guideline=guideline,
                gen_count=st.session_state.gen_count,
                mode=mode,
            )
        except Exception as e:
            status.update(label="오류 발생", state="error")
            err_msg = str(e)
            if "API_KEY_INVALID" in err_msg or "invalid" in err_msg.lower():
                st.error("API Key가 올바르지 않습니다. Gemini API Key를 다시 확인해 주세요.")
            elif "429" in err_msg or "quota" in err_msg.lower():
                st.error("⚠️ API 쿼터 한도 초과(429). 일반 모드로 전환하거나 잠시 후 다시 시도해 주세요.")
            else:
                st.error(f"답변 생성 중 오류가 발생했습니다: {e}")
            return

        st.write(steps[-1])
        status.update(label="답변 생성 완료 ✓", state="complete")

    main_text, sources = parse_sources(raw)

    st.session_state.answer = main_text
    st.session_state.sources = sources
    st.session_state.show_answer = True

    user_msg = (
        f"다른 답변 생성 요청 ({st.session_state.gen_count}회차)" if is_regen else q
    )
    st.session_state.conversation.append({"role": "user", "content": user_msg})
    st.session_state.conversation.append({"role": "assistant", "content": raw})

    if not is_regen and q not in st.session_state.query_history:
        st.session_state.query_history.append(q)


if generate_clicked and question:
    run_generation(question, is_regen=False)

if regen_clicked and st.session_state.current_question:
    run_generation(st.session_state.current_question, is_regen=True)

# ── Display answer ────────────────────────────────────────────
if st.session_state.show_answer and st.session_state.answer:
    gen_n = st.session_state.gen_count
    now_str = datetime.now().strftime("%H:%M")
    last_mode = st.session_state.get("last_mode", selected_mode)
    is_precise_result = last_mode == "정밀 분석 모드"

    label_txt = "최적 답변" + (f" (재생성 {gen_n}회차)" if gen_n > 1 else "")
    mode_badge = (
        "<span class='result-mode-badge badge-precise'>🔬 정밀 분석</span>"
        if is_precise_result else
        "<span class='result-mode-badge badge-normal'>🧠 일반 모드</span>"
    )
    header_gradient = "linear-gradient(to right, #eff6ff, #fff)" if is_precise_result else "linear-gradient(to right, #f9f8f5, #fff)"

    st.markdown(
        f"<div class='result-header-bar' style='background:{header_gradient};'>"
        f"<span class='result-label'>✅ {label_txt}</span>"
        f"<span style='display:flex;align-items:center;gap:8px;'>{mode_badge}"
        f"<span class='result-time'>{now_str} 생성</span></span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    with st.container():
        st.markdown("<div class='result-box-body'>", unsafe_allow_html=True)
        st.markdown(st.session_state.answer)
        st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.sources:
        st.markdown(
            "<div class='sources-box'><div class='sources-title'>🔗 참고 출처</div>",
            unsafe_allow_html=True,
        )
        for i, src in enumerate(st.session_state.sources, 1):
            url_match = re.search(r"(https?://[^\s]+)", src)
            if url_match:
                url = url_match.group(1)
                label = src.replace(url, "").strip().lstrip("-•*0123456789. ") or url
                st.markdown(f"**{i}.** [{label}]({url})")
            else:
                st.markdown(f"**{i}.** {src}")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("")
    st.text_area(
        "📋 답변 복사용 (전체 선택 후 복사)",
        value=st.session_state.answer + (
            "\n\n📌 참고 출처:\n" + "\n".join(st.session_state.sources)
            if st.session_state.sources else ""
        ),
        height=100,
        label_visibility="visible",
    )

    if gen_n > 1:
        st.caption(f"총 {gen_n}회 생성됨")
