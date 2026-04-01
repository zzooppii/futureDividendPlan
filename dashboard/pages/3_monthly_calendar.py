"""페이지 3: 월별 배당 캘린더."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import pandas as pd
import numpy as np
import streamlit as st


@st.cache_resource
def get_fetcher():
    from data.cache import DataCache
    from data.fetcher import YFinanceFetcher
    return YFinanceFetcher(DataCache())


st.title("📅 월별 배당 캘린더")
st.markdown("보유 종목의 배당 지급 패턴을 월별로 시각화합니다.")

fetcher = get_fetcher()

from dashboard.shared_state import portfolio_banner, symbol_selector_sidebar, get_amount_usd

portfolio_banner()

st.sidebar.header("⚙️ 설정")
symbols = symbol_selector_sidebar("cal")
investment = st.sidebar.number_input("총 투자금액 ($)", 1_000, 10_000_000,
                                     int(get_amount_usd()), 1_000)

if st.sidebar.button("📊 캘린더 생성", type="primary") or symbols:
    calendar_data = {}
    div_freq = {}
    next_exdiv = {}

    with st.spinner("배당 이력 분석 중..."):
        for sym in symbols:
            try:
                divs = fetcher.get_dividends(sym)
                if divs.empty:
                    continue
                info = fetcher.get_ticker_info(sym)
                price = info.get("currentPrice") or info.get("regularMarketPrice") or 0.0

                # 최근 1년 배당 내역
                now = divs.index.max()
                recent = divs[divs.index >= now - pd.DateOffset(years=1)]

                monthly_divs = {}
                for dt, amt in recent.items():
                    m = dt.month
                    monthly_divs[m] = monthly_divs.get(m, 0.0) + amt

                # 배당 빈도 추정
                annual_count = len(recent)
                if annual_count >= 11:
                    freq = "월배당"
                elif annual_count >= 4:
                    freq = "분기배당"
                elif annual_count >= 2:
                    freq = "반기배당"
                elif annual_count >= 1:
                    freq = "연배당"
                else:
                    freq = "불규칙"

                div_freq[sym] = freq
                calendar_data[sym] = monthly_divs

                # 다음 배당 예상일 (최근 배당락일 기준 추정)
                last_dt = divs.index.max()
                if annual_count >= 11:
                    next_est = last_dt + pd.DateOffset(months=1)
                elif annual_count >= 4:
                    next_est = last_dt + pd.DateOffset(months=3)
                else:
                    next_est = last_dt + pd.DateOffset(years=1)
                next_exdiv[sym] = next_est.strftime("%Y-%m-%d")

            except Exception:
                pass

    if not calendar_data:
        st.warning("배당 데이터를 가져올 수 없습니다.")
        st.stop()

    # ── 월별 합계 바차트 ─────────────────────────────────────────
    # 투자금 기준으로 실제 배당금 계산
    month_totals = {m: 0.0 for m in range(1, 13)}
    per_stock = investment / len(calendar_data)

    for sym, monthly in calendar_data.items():
        try:
            info = fetcher.get_ticker_info(sym)
            price = info.get("currentPrice") or 1.0
            yld = info.get("dividendYield") or info.get("trailingAnnualDividendYield") or 0.0
            if yld > 0.20:
                yld = yld / 100
            shares = per_stock / price if price > 0 else 0.0
        except Exception:
            shares = 0.0
            yld = 0.0

        for m, div_per_share in monthly.items():
            month_totals[m] = month_totals.get(m, 0.0) + shares * div_per_share

    import plotly.graph_objects as go

    st.subheader("📊 월별 예상 배당 수입")
    months_kr = ["1월", "2월", "3월", "4월", "5월", "6월",
                 "7월", "8월", "9월", "10월", "11월", "12월"]

    values = [month_totals.get(m, 0.0) for m in range(1, 13)]
    max_val = max(values) if any(v > 0 for v in values) else 1

    colors = ["#2ca02c" if v > max_val * 0.7
              else "#ff7f0e" if v > max_val * 0.3
              else "#1f77b4"
              for v in values]

    fig = go.Figure(go.Bar(
        x=months_kr, y=values,
        marker_color=colors,
        text=[f"${v:,.0f}" for v in values],
        textposition="outside",
    ))
    fig.update_layout(
        title="월별 예상 배당 수입 ($)",
        xaxis_title="월", yaxis_title="배당 수입 ($)",
        template="plotly_dark", height=400,
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── 히트맵 ───────────────────────────────────────────────────
    st.subheader("🗓️ 종목별 배당 히트맵")
    heatmap_data = []
    for sym in calendar_data:
        row = []
        for m in range(1, 13):
            # 있으면 1 (배당 지급), 없으면 0
            row.append(1 if m in calendar_data[sym] else 0)
        heatmap_data.append(row)

    if heatmap_data:
        from dashboard.components.charts import monthly_dividend_heatmap
        df_heatmap = pd.DataFrame(
            heatmap_data,
            index=list(calendar_data.keys()),
            columns=range(1, 13),
        )
        st.plotly_chart(monthly_dividend_heatmap(df_heatmap), use_container_width=True)

    # ── 배당 빈도 및 다음 예상 배당일 ────────────────────────────
    st.subheader("📋 종목별 배당 현황")
    rows = []
    for sym in calendar_data:
        freq = div_freq.get(sym, "-")
        next_dt = next_exdiv.get(sym, "-")
        months_with_div = sorted([m for m, v in calendar_data[sym].items() if v > 0])
        months_str = ", ".join([f"{m}월" for m in months_with_div])
        rows.append({
            "종목": sym,
            "배당 주기": freq,
            "배당 지급 월": months_str,
            "다음 배당 예상일": next_dt,
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ── 현금흐름 고름 분석 ────────────────────────────────────────
    st.subheader("⚖️ 월별 현금흐름 균등화 분석")
    nonzero = [v for v in values if v > 0]
    if nonzero:
        avg_monthly = sum(values) / 12
        empty_months = sum(1 for v in values if v < avg_monthly * 0.1)
        cv = np.std(values) / np.mean(values) if np.mean(values) > 0 else 0

        col1, col2, col3 = st.columns(3)
        col1.metric("연간 총 배당 예상", f"${sum(values):,.0f}")
        col2.metric("월평균 배당", f"${avg_monthly:,.0f}")
        col3.metric("현금흐름 불균등 지수", f"{cv:.2f}", help="낮을수록 균등 (0에 가까울수록 좋음)")

        if empty_months > 0:
            st.warning(f"⚠️ 배당이 없거나 적은 달이 {empty_months}개월 있습니다. 월배당 ETF 추가를 고려해보세요.")
        else:
            st.success("✅ 연중 비교적 고른 배당 현금흐름입니다.")
