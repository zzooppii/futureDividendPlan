"""페이지 2: 포트폴리오 배분."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import pandas as pd
import streamlit as st


@st.cache_resource
def get_fetcher():
    from data.cache import DataCache
    from data.fetcher import YFinanceFetcher
    return YFinanceFetcher(DataCache())


st.title("🥧 포트폴리오 배분 분석")

fetcher = get_fetcher()

from dashboard.shared_state import portfolio_banner, symbol_selector_sidebar, get_amount_usd

portfolio_banner()

st.sidebar.header("⚙️ 포트폴리오 설정")
symbols = symbol_selector_sidebar("alloc")
investment = st.sidebar.number_input("총 투자금액 ($)", 1_000, 10_000_000,
                                     int(get_amount_usd()), 1_000)

if st.sidebar.button("📊 분석", type="primary") or symbols:
    portfolio_data = []
    with st.spinner("데이터 로딩 중..."):
        for sym in symbols:
            try:
                info = fetcher.get_ticker_info(sym)
                yld = info.get("dividendYield") or info.get("trailingAnnualDividendYield") or 0.0
                if yld > 0.20:
                    yld = yld / 100
                portfolio_data.append({
                    "symbol": sym,
                    "name": (info.get("shortName") or sym)[:20],
                    "sector": info.get("sector") or "기타",
                    "industry": info.get("industry") or "-",
                    "yield": yld,
                    "market_cap": info.get("marketCap") or 0,
                    "beta": info.get("beta") or 0,
                    "payout_ratio": info.get("payoutRatio") or 0,
                })
            except Exception:
                pass

    if not portfolio_data:
        st.error("데이터를 가져올 수 없습니다.")
        st.stop()

    n = len(portfolio_data)
    weight = 1.0 / n
    per_stock = investment * weight

    # ── 요약 지표 ────────────────────────────────────────────────────
    avg_yield = sum(d["yield"] for d in portfolio_data) / n
    avg_beta = sum(d["beta"] for d in portfolio_data) / n
    avg_payout = sum(d["payout_ratio"] for d in portfolio_data) / n
    annual_div = investment * avg_yield

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("종목 수", f"{n}개")
    col2.metric("포트폴리오 수익률", f"{avg_yield:.2%}")
    col3.metric("평균 베타", f"{avg_beta:.2f}")
    col4.metric("연간 예상 배당", f"${annual_div:,.0f}")

    st.divider()

    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    from dashboard.components.charts import allocation_pie

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("종목별 배분")
        names = [d["symbol"] for d in portfolio_data]
        weights = [weight] * n
        st.plotly_chart(allocation_pie(names, weights, "균등 배분"), use_container_width=True)

    with col2:
        st.subheader("섹터별 배분")
        from collections import Counter
        sector_counts = Counter(d["sector"] for d in portfolio_data)
        fig_sector = go.Figure(go.Pie(
            labels=list(sector_counts.keys()),
            values=list(sector_counts.values()),
            hole=0.4, textinfo="label+percent",
        ))
        fig_sector.update_layout(template="plotly_dark", height=400, title="섹터 비중")
        st.plotly_chart(fig_sector, use_container_width=True)

    # ── 배당수익률 vs 베타 산점도 ──────────────────────────────────
    st.subheader("📐 배당수익률 vs 베타 (Risk-Return 분석)")
    fig_scatter = go.Figure(go.Scatter(
        x=[d["beta"] for d in portfolio_data],
        y=[d["yield"] * 100 for d in portfolio_data],
        mode="markers+text",
        text=[d["symbol"] for d in portfolio_data],
        textposition="top center",
        marker=dict(size=12, color=[d["yield"] * 100 for d in portfolio_data],
                    colorscale="Viridis", showscale=True, colorbar=dict(title="수익률(%)")),
        hovertemplate="<b>%{text}</b><br>베타: %{x:.2f}<br>배당수익률: %{y:.2f}%<extra></extra>",
    ))
    fig_scatter.add_vline(x=1.0, line_dash="dash", line_color="gray", annotation_text="β=1")
    fig_scatter.update_layout(
        xaxis_title="베타 (낮을수록 안정적)", yaxis_title="배당수익률 (%)",
        template="plotly_dark", height=450,
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

    # ── 종목별 상세 테이블 ────────────────────────────────────────
    st.subheader("📋 종목 상세")
    rows = []
    for d in portfolio_data:
        rows.append({
            "종목": d["symbol"],
            "종목명": d["name"],
            "섹터": d["sector"],
            "투자금액": f"${per_stock:,.0f}",
            "배당수익률": f"{d['yield']:.2%}",
            "예상 연간 배당": f"${per_stock * d['yield']:,.0f}",
            "예상 월 배당": f"${per_stock * d['yield'] / 12:,.0f}",
            "베타": f"{d['beta']:.2f}",
            "배당성향": f"{d['payout_ratio']:.1%}" if d["payout_ratio"] > 0 else "-",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
