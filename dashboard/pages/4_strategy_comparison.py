"""페이지 4: 전략 비교 + 백테스트."""
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


@st.cache_data(ttl=3600, show_spinner=False)
def run_backtest_cached(strategy_name: str, universe_size: str, start: str, end: str,
                        capital: float, rebalance: str, reinvest: bool, max_pos: int):
    from data.cache import DataCache
    from data.fetcher import YFinanceFetcher
    from data.ticker_list import get_small_universe, get_strategy_universe
    from backtest.engine import BacktestConfig, BacktestEngine

    fetcher = YFinanceFetcher(DataCache())
    universe = get_small_universe() if universe_size == "소규모" else get_strategy_universe(strategy_name)

    strategy_map = {
        "월배당 최대화": "max_monthly",
        "실버 연금 배당": "silver_pension",
        "장기 배당 성장": "dividend_growth",
        "퀄리티 배당 코어": "quality_core",
        "커버드콜 배당": "covered_call",
    }

    from strategies.max_monthly_dividend import MaxMonthlyDividendStrategy
    from strategies.silver_pension import SilverPensionStrategy
    from strategies.dividend_growth import DividendGrowthStrategy
    from strategies.quality_core import QualityCoreStrategy
    from strategies.covered_call import CoveredCallStrategy

    strat_obj_map = {
        "월배당 최대화": MaxMonthlyDividendStrategy(),
        "실버 연금 배당": SilverPensionStrategy(),
        "장기 배당 성장": DividendGrowthStrategy(),
        "퀄리티 배당 코어": QualityCoreStrategy(),
        "커버드콜 배당": CoveredCallStrategy(),
    }

    cfg = BacktestConfig(
        start_date=start, end_date=end,
        initial_capital=capital,
        rebalance_frequency=rebalance,
        reinvest_dividends=reinvest,
        max_positions=max_pos,
    )
    engine = BacktestEngine(cfg, fetcher)
    strategy = strat_obj_map[strategy_name]
    return engine.run(strategy, universe)


st.title("⚔️ 전략 성과 비교")
st.markdown("각 배당 전략의 백테스트 결과를 비교합니다.")

# ── 설정 ──────────────────────────────────────────────────────────
st.sidebar.header("⚙️ 백테스트 설정")
selected_strategies = st.sidebar.multiselect(
    "비교할 전략",
    ["월배당 최대화", "실버 연금 배당", "장기 배당 성장", "퀄리티 배당 코어", "커버드콜 배당"],
    default=["월배당 최대화", "실버 연금 배당", "장기 배당 성장"],
)
universe_size = st.sidebar.radio("유니버스", ["소규모 (빠름)", "전체"])
start_date = st.sidebar.text_input("시작일", "2015-01-01")
end_date = st.sidebar.text_input("종료일", "2026-03-01")
capital = st.sidebar.number_input("초기 투자금 ($)", 10_000, 10_000_000, 100_000, 10_000)
rebalance = st.sidebar.selectbox("리밸런싱 주기", ["quarterly", "monthly", "annual"])
reinvest = st.sidebar.checkbox("배당 재투자", True)
max_pos = st.sidebar.slider("최대 종목 수", 5, 20, 10)

run_btn = st.button("🚀 백테스트 실행", type="primary")

if run_btn and selected_strategies:
    results = {}
    progress_bar = st.progress(0)
    status = st.empty()

    for i, strat_name in enumerate(selected_strategies):
        status.text(f"백테스트 실행 중: {strat_name}...")
        try:
            res = run_backtest_cached(
                strat_name,
                "소규모" if universe_size == "소규모 (빠름)" else "전체",
                start_date, end_date,
                capital, rebalance, reinvest, max_pos,
            )
            results[strat_name] = res
        except Exception as e:
            st.error(f"{strat_name} 오류: {e}")
        progress_bar.progress((i + 1) / len(selected_strategies))

    status.empty()
    progress_bar.empty()

    if not results:
        st.error("실행된 백테스트가 없습니다.")
        st.stop()

    # ── 비교 지표 카드 ────────────────────────────────────────────
    st.subheader("📊 성과 비교 요약")
    cols = st.columns(len(results))
    for col, (name, res) in zip(cols, results.items()):
        m = res.metrics
        col.metric(name, f"{m.total_return:.1%}", f"CAGR {m.cagr:.1%}")

    # ── 수익곡선 ─────────────────────────────────────────────────
    st.subheader("📈 포트폴리오 수익 곡선")
    from dashboard.components.charts import equity_curve_chart
    st.plotly_chart(equity_curve_chart(results), use_container_width=True)

    # ── 낙폭 비교 ────────────────────────────────────────────────
    st.subheader("📉 낙폭 비교")
    import plotly.graph_objects as go
    fig_dd = go.Figure()
    for name, res in results.items():
        if not res.drawdown_series.empty:
            from dashboard.components.charts import STRATEGY_COLORS
            color = STRATEGY_COLORS.get(name, "#aaaaaa")
            fig_dd.add_trace(go.Scatter(
                x=res.drawdown_series.index,
                y=res.drawdown_series.values * 100,
                name=name, fill="tozeroy",
                line=dict(color=color),
            ))
    fig_dd.update_layout(template="plotly_dark", height=300,
                         xaxis_title="날짜", yaxis_title="낙폭 (%)")
    st.plotly_chart(fig_dd, use_container_width=True)

    # ── 상세 지표 테이블 ──────────────────────────────────────────
    st.subheader("📋 상세 성과 지표")
    from backtest.report import compare_strategies
    compare_df = compare_strategies(results)
    st.dataframe(compare_df, use_container_width=True, hide_index=True)

    # ── 레이더 차트 ───────────────────────────────────────────────
    st.subheader("🕸️ 전략 특성 레이더")
    from dashboard.components.charts import radar_chart

    categories = ["수익률", "배당수입", "샤프", "저낙폭", "안정성"]
    all_vals = []
    names_list = list(results.keys())

    for name, res in results.items():
        m = res.metrics
        total_ret_score = min(max(m.total_return * 100 + 50, 0), 100)
        div_score = min(m.yield_on_cost * 500, 100)
        sharpe_score = min(max(m.sharpe_ratio * 33, 0), 100)
        drawdown_score = max(0, 100 + m.max_drawdown * 200)
        stability = max(0, 100 - m.annual_volatility * 300)
        all_vals.append([total_ret_score, div_score, sharpe_score, drawdown_score, stability])

    st.plotly_chart(radar_chart(names_list, categories, all_vals), use_container_width=True)

    # ── 면책조항 ─────────────────────────────────────────────────
    st.warning(list(results.values())[0].disclaimer)
