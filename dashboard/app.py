"""Streamlit 대시보드 홈 페이지.

실행: streamlit run dashboard/app.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

st.set_page_config(
    page_title="배당 투자 리서치 시스템",
    page_icon="💹",
    layout="wide",
    initial_sidebar_state="expanded",
)


def home():
    st.title("💹 나스닥 배당 투자 리서치 시스템")

    # ── 클릭 가능한 카드 ───────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("💰 **내 투자 플래너**\n\n투자금액을 입력하면 맞춤형 전략과 시뮬레이션을 제공합니다.")
        st.page_link("pages/0_my_investment.py", label="→ 바로 가기", icon="💰")
    with col2:
        st.success("📊 **5가지 전략**\n\n월배당·실버연금·배당성장·퀄리티코어·커버드콜")
        st.page_link("pages/4_strategy_comparison.py", label="→ 전략 비교 보기", icon="⚔️")
    with col3:
        st.warning("⚠️ **데이터 출처**\n\nyfinance (무료) 기반. 투자 결정 전 전문가 상담 권장.")
        st.page_link("pages/5_growth_visualization.py", label="→ 종목 분석 보기", icon="🌱")

    st.divider()

    # ── 페이지 바로가기 그리드 ─────────────────────────────────────
    st.subheader("🚀 페이지 바로가기")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.page_link("pages/0_my_investment.py",          label="💰 내 투자 플래너")
        st.page_link("pages/1_dividend_projection.py",    label="📈 배당 수입 예측")
    with c2:
        st.page_link("pages/2_allocation.py",             label="🥧 포트폴리오 배분")
        st.page_link("pages/3_monthly_calendar.py",       label="📅 배당 캘린더")
    with c3:
        st.page_link("pages/4_strategy_comparison.py",    label="⚔️ 전략 비교")
        st.page_link("pages/5_growth_visualization.py",   label="🌱 성장 분석")
    with c4:
        st.page_link("pages/6_covered_call_simulator.py", label="📞 커버드콜")


pg = st.navigation(
    {
        "홈": [
            st.Page(home, title="🏠 홈 (Home)", default=True),
        ],
        "전략 & 분석": [
            st.Page("pages/0_my_investment.py",          title="💰 내 투자 플래너 (My Investment)"),
            st.Page("pages/1_dividend_projection.py",    title="📈 배당 수입 예측 (Dividend Projection)"),
            st.Page("pages/2_allocation.py",             title="🥧 포트폴리오 배분 (Allocation)"),
            st.Page("pages/3_monthly_calendar.py",       title="📅 배당 캘린더 (Monthly Calendar)"),
            st.Page("pages/4_strategy_comparison.py",    title="⚔️ 전략 비교 (Strategy Comparison)"),
            st.Page("pages/5_growth_visualization.py",   title="🌱 성장 분석 (Growth Visualization)"),
            st.Page("pages/6_covered_call_simulator.py", title="📞 커버드콜 (Covered Call Simulator)"),
        ],
    }
)
pg.run()
