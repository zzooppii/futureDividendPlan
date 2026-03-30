"""사이드바 필터 위젯."""
import streamlit as st


def investment_profile_sidebar() -> dict:
    """투자 프로필 입력 사이드바."""
    st.sidebar.header("💼 투자 프로필 설정")

    currency = st.sidebar.selectbox("통화", ["USD ($)", "KRW (₩)"], key="currency")
    is_krw = currency == "KRW (₩)"

    if is_krw:
        amount_krw = st.sidebar.number_input(
            "투자 금액 (만원)", min_value=100, max_value=100_000, value=3_000, step=100
        )
        amount_usd = amount_krw * 10_000 / 1350
    else:
        amount_usd = st.sidebar.number_input(
            "투자 금액 ($)", min_value=1_000, max_value=10_000_000, value=50_000, step=1_000
        )

    goal = st.sidebar.selectbox(
        "투자 목표",
        ["월수입 극대화", "안정적 노후 대비", "배당 성장 + 자산 증식", "종합 균형"],
    )
    horizon = st.sidebar.slider("투자 기간 (년)", min_value=1, max_value=30, value=10)
    risk = st.sidebar.select_slider(
        "위험 성향", options=["매우 보수적", "보수적", "중립", "적극적", "매우 적극적"], value="중립"
    )

    return {
        "amount_usd": amount_usd,
        "is_krw": is_krw,
        "goal": goal,
        "horizon": horizon,
        "risk": risk,
    }


def strategy_selector(default: str = "월배당 최대화") -> str:
    strategies = ["월배당 최대화", "실버 연금 배당", "장기 배당 성장", "퀄리티 배당 코어", "커버드콜 배당"]
    return st.sidebar.selectbox("전략 선택", strategies, index=strategies.index(default))


def backtest_config_sidebar() -> dict:
    st.sidebar.header("⚙️ 백테스트 설정")
    start = st.sidebar.text_input("시작일", "2010-01-01")
    end = st.sidebar.text_input("종료일", "2026-03-01")
    capital = st.sidebar.number_input("초기 투자금 ($)", 10_000, 10_000_000, 100_000, 10_000)
    rebalance = st.sidebar.selectbox("리밸런싱 주기", ["monthly", "quarterly", "annual"])
    reinvest = st.sidebar.checkbox("배당 재투자", value=True)
    max_pos = st.sidebar.slider("최대 보유 종목", 5, 30, 15)
    return {
        "start_date": start,
        "end_date": end,
        "initial_capital": capital,
        "rebalance_frequency": rebalance,
        "reinvest_dividends": reinvest,
        "max_positions": max_pos,
    }


def universe_filter_sidebar() -> list[str]:
    from data.ticker_list import get_full_universe, get_small_universe
    mode = st.sidebar.radio("유니버스", ["소규모 (빠름)", "전체"])
    return get_small_universe() if mode == "소규모 (빠름)" else get_full_universe()
