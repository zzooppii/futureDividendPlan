"""페이지 1: 배당 수입 예측."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import numpy as np
import pandas as pd
import streamlit as st

st.title("📈 배당 수입 예측")
st.markdown("선택한 종목/전략의 미래 배당 수입을 예측합니다.")

# ── 데이터 로딩 ───────────────────────────────────────────────────
@st.cache_resource
def get_fetcher():
    from data.cache import DataCache
    from data.fetcher import YFinanceFetcher
    return YFinanceFetcher(DataCache())


fetcher = get_fetcher()

# ── 시뮬레이션 설정 (사이드바) ────────────────────────────────────
st.sidebar.header("⚙️ 시뮬레이션 설정")
investment = st.sidebar.number_input("투자금액 ($)", 1_000, 10_000_000, 100_000, 1_000)
horizon = st.sidebar.slider("예측 기간 (년)", 1, 30, 10)
div_growth_rate = st.sidebar.slider("연간 배당 성장률 (%)", 0, 20, 5) / 100
price_growth_rate = st.sidebar.slider("연간 주가 성장률 (%)", 0, 20, 4) / 100
reinvest = st.sidebar.checkbox("배당 재투자", True)

# ── 종목 선택 (메인 영역 상단) ────────────────────────────────────
from dashboard.components.stock_picker import stock_picker

symbols = stock_picker(fetcher)

st.divider()

if st.sidebar.button("📊 분석 실행", type="primary"):
    st.session_state["proj_run"] = True

if st.session_state.get("proj_run") or symbols:
    # 각 종목 정보 조회
    ticker_data = []
    progress = st.progress(0)
    for i, sym in enumerate(symbols):
        try:
            info = fetcher.get_ticker_info(sym)
            yld = info.get("dividendYield") or info.get("trailingAnnualDividendYield") or 0.0
            if yld > 0.20:
                yld = yld / 100
            name = info.get("shortName") or info.get("longName") or sym
            ticker_data.append({
                "symbol": sym,
                "name": name,
                "yield": yld,
                "price": info.get("currentPrice") or info.get("regularMarketPrice") or 0.0,
                "sector": info.get("sector", "-"),
            })
        except Exception:
            pass
        progress.progress((i + 1) / len(symbols))
    progress.empty()

    if not ticker_data:
        st.error("데이터를 가져올 수 없습니다.")
        st.stop()

    # ── 요약 ────────────────────────────────────────────────────────
    n = len(ticker_data)
    avg_yield = np.mean([t["yield"] for t in ticker_data]) if ticker_data else 0.0
    per_stock = investment / n if n > 0 else 0.0
    annual_div = investment * avg_yield
    monthly_div = annual_div / 12

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("종목 수", f"{n}개")
    col2.metric("평균 배당수익률", f"{avg_yield:.2%}")
    col3.metric("예상 연간 배당", f"${annual_div:,.0f}")
    col4.metric("예상 월 배당", f"${monthly_div:,.0f}")

    st.divider()

    # ── 종목별 현황 ──────────────────────────────────────────────────
    st.subheader("📋 종목별 배당 현황")
    rows = []
    for t in ticker_data:
        alloc = per_stock
        rows.append({
            "종목": t["symbol"],
            "종목명": t["name"][:20],
            "배분금액": f"${alloc:,.0f}",
            "배당수익률": f"{t['yield']:.2%}",
            "연간 배당 예상": f"${alloc * t['yield']:,.0f}",
            "월간 배당 예상": f"${alloc * t['yield'] / 12:,.0f}",
            "섹터": t["sector"],
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ── 복리 성장 시뮬레이션 ─────────────────────────────────────────
    st.subheader("📉 배당 수입 성장 시뮬레이션")

    year_labels = list(range(horizon + 1))
    portfolio_values_r = [investment]
    portfolio_values_nr = [investment]
    annual_divs_r = []
    annual_divs_nr = []
    current_yield = avg_yield

    for y in range(1, horizon + 1):
        # 재투자
        d_r = portfolio_values_r[-1] * current_yield
        annual_divs_r.append(d_r)
        portfolio_values_r.append(portfolio_values_r[-1] * (1 + price_growth_rate) + d_r)

        # 미재투자
        d_nr = portfolio_values_nr[-1] * current_yield
        annual_divs_nr.append(d_nr)
        portfolio_values_nr.append(portfolio_values_nr[-1] * (1 + price_growth_rate))

        price_growth_adj = 1 + price_growth_rate if price_growth_rate > 0 else 1.0
        current_yield = min(current_yield * (1 + div_growth_rate) / price_growth_adj, 0.15)

    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=["포트폴리오 가치 성장", "연간 배당 수입", "월간 배당 수입", "누적 배당 수입"],
    )

    # 포트폴리오 가치
    fig.add_trace(go.Scatter(x=year_labels, y=portfolio_values_r, name="재투자", line=dict(color="#2ca02c", width=2)),
                  row=1, col=1)
    fig.add_trace(go.Scatter(x=year_labels, y=portfolio_values_nr, name="수령", line=dict(color="#1f77b4", width=2)),
                  row=1, col=1)

    # 연간 배당
    fig.add_trace(go.Bar(x=list(range(1, horizon + 1)), y=annual_divs_r, name="재투자 시",
                         marker_color="#2ca02c", showlegend=False), row=1, col=2)

    # 월간 배당
    monthly_divs = [d / 12 for d in annual_divs_r]
    fig.add_trace(go.Scatter(x=list(range(1, horizon + 1)), y=monthly_divs, name="월 배당 (재투자)",
                             line=dict(color="#ff7f0e", width=2), showlegend=False), row=2, col=1)

    # 누적 배당
    cumul = np.cumsum(annual_divs_nr)
    fig.add_trace(go.Scatter(x=list(range(1, horizon + 1)), y=cumul, name="누적 배당 (수령)",
                             fill="tozeroy", line=dict(color="#9467bd"), showlegend=False), row=2, col=2)

    fig.update_layout(template="plotly_dark", height=600, showlegend=True)
    st.plotly_chart(fig, use_container_width=True)

    # ── 상세 테이블 ──────────────────────────────────────────────────
    st.subheader("📅 연도별 상세 예측")
    detail_rows = []
    for y in range(1, horizon + 1):
        detail_rows.append({
            "연도": f"투자 {y}년차",
            "포트폴리오 가치 (재투자)": f"${portfolio_values_r[y]:,.0f}",
            "연간 배당 (재투자)": f"${annual_divs_r[y-1]:,.0f}",
            "월 배당 (재투자)": f"${annual_divs_r[y-1]/12:,.0f}",
            "포트폴리오 가치 (수령)": f"${portfolio_values_nr[y]:,.0f}",
            "연간 배당 (수령)": f"${annual_divs_nr[y-1]:,.0f}",
        })
    st.dataframe(pd.DataFrame(detail_rows), use_container_width=True, hide_index=True)
