"""페이지 6: 커버드콜 수입 시뮬레이터."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


@st.cache_resource
def get_fetcher():
    from data.cache import DataCache
    from data.fetcher import YFinanceFetcher
    return YFinanceFetcher(DataCache())


def black_scholes_call(S, K, T, r, sigma):
    from scipy.stats import norm
    if T <= 0 or sigma <= 0:
        return max(S - K, 0.0)
    d1 = (math.log(S / K) + (r + sigma ** 2 / 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)


def simulate_covered_call(price, iv, annual_div_yield, contracts, dte, strike_pct, r, months):
    """커버드콜 전략 시뮬레이션."""
    share_per_contract = 100
    total_shares = contracts * share_per_contract
    position_value = total_shares * price

    monthly_div = position_value * annual_div_yield / 12
    strike = price * (1 + strike_pct / 100)
    T = dte / 365
    premium_per_share = black_scholes_call(price, strike, T, r, iv)
    total_premium = premium_per_share * total_shares

    results = []
    cumul_div = 0.0
    cumul_premium = 0.0
    current_price = price

    for m in range(1, months + 1):
        # 가격 변동 (랜덤 워크 시뮬레이션)
        monthly_vol = iv / math.sqrt(12)
        price_change = np.random.normal(0.003, monthly_vol)  # 월 0.3% 상승 가정
        current_price = current_price * (1 + price_change)

        # 커버드콜 만기 처리
        if current_price > strike:
            # 주식 콜되면 재매수 비용 발생
            buyback_cost = (current_price - strike) * total_shares
        else:
            buyback_cost = 0.0

        premium = black_scholes_call(current_price, current_price * (1 + strike_pct / 100), T, r, iv) * total_shares
        div = total_shares * (current_price * annual_div_yield / 12)

        cumul_div += div
        cumul_premium += premium
        results.append({
            "월": m,
            "주가": current_price,
            "월 배당": div,
            "월 프리미엄": premium,
            "월 총 수입": div + premium,
            "누적 배당": cumul_div,
            "누적 프리미엄": cumul_premium,
            "누적 총 수입": cumul_div + cumul_premium,
        })

    return pd.DataFrame(results)


st.title("📞 커버드콜 배당 수입 시뮬레이터")
st.markdown(
    "고배당 주식에 커버드콜 전략을 결합한 시나리오를 시뮬레이션합니다. "
    "**주의:** Black-Scholes 모델 기반 추정치입니다."
)

fetcher = get_fetcher()

# ── 입력 ──────────────────────────────────────────────────────────
col_input, col_info = st.columns([1, 2])

with col_input:
    st.subheader("📝 파라미터 설정")

    symbol = st.text_input("종목 심볼", "AAPL")
    use_live = st.checkbox("실시간 데이터 사용", True)

    if use_live and symbol:
        with st.spinner("데이터 로딩..."):
            try:
                info = fetcher.get_ticker_info(symbol)
                live_price = info.get("currentPrice") or info.get("regularMarketPrice") or 150.0
                _raw_yield = info.get("dividendYield") or info.get("trailingAnnualDividendYield") or 0.005
                live_yield = _raw_yield / 100 if _raw_yield > 0.20 else _raw_yield
                # 히스토리컬 변동성으로 IV 추정
                price_df = fetcher.get_price_history(symbol)
                if not price_df.empty and len(price_df) > 30:
                    returns = price_df["Close"].pct_change().dropna()
                    live_iv = float(returns.iloc[-30:].std() * math.sqrt(252))
                else:
                    live_iv = 0.25
                st.success(f"현재가: ${live_price:.2f} | 배당수익률: {live_yield:.2%} | HV: {live_iv:.2%}")
            except Exception:
                live_price, live_yield, live_iv = 150.0, 0.01, 0.25
                st.warning("데이터 로딩 실패. 기본값 사용")
    else:
        live_price, live_yield, live_iv = 150.0, 0.01, 0.25

    price = st.number_input("현재 주가 ($)", 1.0, 10000.0, float(f"{live_price:.2f}"), 0.01)
    annual_yield = st.number_input("연간 배당수익률 (%)", 0.0, 50.0, float(f"{live_yield*100:.2f}"), 0.1) / 100
    iv = st.number_input("내재변동성 (%)", 5.0, 150.0, float(f"{live_iv*100:.1f}"), 0.5) / 100
    contracts = st.number_input("계약 수 (1계약=100주)", 1, 1000, 10)
    dte = st.slider("만기까지 일수 (DTE)", 7, 90, 30)
    strike_pct = st.slider("행사가 프리미엄 (%)", -10, 20, 5)
    months = st.slider("시뮬레이션 기간 (월)", 1, 60, 12)
    r = st.number_input("무위험 이자율 (%)", 0.0, 10.0, 4.0, 0.1) / 100

    run_btn = st.button("🚀 시뮬레이션 실행", type="primary", use_container_width=True)

with col_info:
    st.subheader("💡 커버드콜 전략 설명")
    st.info("""
**커버드콜 전략**이란:
1. 배당주를 보유하면서
2. 해당 주식의 콜옵션을 매도하여
3. 옵션 프리미엄 수입을 추가로 얻는 전략입니다.

**수익 구조:**
- ✅ 주가가 행사가 아래: 배당 + 프리미엄 수취
- ⚠️ 주가가 행사가 위: 배당 + 프리미엄 수취, 단 상승분 포기

**적합한 종목:**
- 높은 배당수익률 (2% 이상)
- 높은 옵션 거래량 (유동성)
- 적정 변동성 (너무 낮으면 프리미엄 적음)
    """)

    # 현재 설정의 예상 수익률
    if 'price' in dir() and price > 0:
        total_shares = contracts * 100
        position_value = total_shares * price
        strike_price = price * (1 + strike_pct / 100)
        T = dte / 365
        premium = black_scholes_call(price, strike_price, T, r, iv)
        premium_annualized = premium / price * (365 / dte)
        monthly_div_amt = position_value * annual_yield / 12
        monthly_premium = premium * total_shares

        st.subheader("현재 설정 요약")
        c1, c2 = st.columns(2)
        c1.metric("포지션 가치", f"${position_value:,.0f}")
        c2.metric("ATM 콜 프리미엄", f"${premium:.2f}/주")
        c1.metric("월 배당 수입", f"${monthly_div_amt:,.0f}")
        c2.metric("월 프리미엄 수입", f"${monthly_premium:,.0f}")
        combined = (annual_yield + premium_annualized) * 100
        st.metric("합산 연환산 수익률", f"{combined:.1f}%",
                  f"+{premium_annualized*100:.1f}% (커버드콜 추가)")

# ── 시뮬레이션 실행 ────────────────────────────────────────────────
if run_btn:
    np.random.seed(42)
    sim_df = simulate_covered_call(price, iv, annual_yield, contracts, dte, strike_pct, r, months)

    st.divider()
    st.subheader("📊 시뮬레이션 결과")

    # 요약 지표
    total_div_income = sim_df["누적 배당"].iloc[-1]
    total_premium_income = sim_df["누적 프리미엄"].iloc[-1]
    total_income = sim_df["누적 총 수입"].iloc[-1]
    position_value = contracts * 100 * price
    total_return_pct = total_income / position_value

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("총 배당 수입", f"${total_div_income:,.0f}")
    col2.metric("총 프리미엄 수입", f"${total_premium_income:,.0f}")
    col3.metric("합산 수입", f"${total_income:,.0f}")
    col4.metric("투자 대비 수익률", f"{total_return_pct:.1%}",
                f"연환산 {total_return_pct/months*12:.1%}")

    # 월별 수입 분포
    fig1 = go.Figure()
    fig1.add_trace(go.Bar(x=sim_df["월"], y=sim_df["월 배당"], name="월 배당", marker_color="#1f77b4"))
    fig1.add_trace(go.Bar(x=sim_df["월"], y=sim_df["월 프리미엄"], name="월 프리미엄", marker_color="#2ca02c"))
    fig1.update_layout(barmode="stack", title="월별 수입 분포 (배당 + 프리미엄)",
                       template="plotly_dark", height=350,
                       xaxis_title="월차", yaxis_title="수입 ($)")
    st.plotly_chart(fig1, use_container_width=True)

    # 누적 수입 비교
    col1, col2 = st.columns(2)
    with col1:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=sim_df["월"], y=sim_df["누적 배당"],
                                  name="배당만", line=dict(color="#1f77b4", width=2)))
        fig2.add_trace(go.Scatter(x=sim_df["월"], y=sim_df["누적 총 수입"],
                                  name="배당+커버드콜", line=dict(color="#2ca02c", width=3),
                                  fill="tonexty"))
        fig2.update_layout(title="누적 수입 비교", template="plotly_dark", height=350)
        st.plotly_chart(fig2, use_container_width=True)

    with col2:
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=sim_df["월"], y=sim_df["주가"],
                                  name="주가", line=dict(color="#ff7f0e", width=2)))
        strike_line = price * (1 + strike_pct / 100)
        fig3.add_hline(y=strike_line, line_dash="dash", line_color="red",
                       annotation_text=f"행사가 ${strike_line:.2f}")
        fig3.add_hline(y=price, line_dash="dash", line_color="gray",
                       annotation_text=f"매수가 ${price:.2f}")
        fig3.update_layout(title="주가 시뮬레이션 (랜덤 워크)", template="plotly_dark", height=350)
        st.plotly_chart(fig3, use_container_width=True)

    # 상세 테이블
    st.subheader("📋 월별 상세 내역")
    display_df = sim_df.copy()
    for col in ["주가", "월 배당", "월 프리미엄", "월 총 수입", "누적 배당", "누적 프리미엄", "누적 총 수입"]:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(lambda x: f"${x:,.2f}")
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.caption(
        "⚠️ 위 시뮬레이션은 Black-Scholes 모델과 가격 랜덤 워크를 기반으로 한 추정치입니다. "
        "실제 옵션 프리미엄은 변동성 스마일, 유동성, 시장 상황에 따라 다를 수 있습니다."
    )
