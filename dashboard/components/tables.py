"""데이터프레임 렌더링 유틸."""
import pandas as pd
import streamlit as st


def show_screening_results(results: list, fetcher=None) -> None:
    if not results:
        st.warning("스크리닝 통과 종목이 없습니다.")
        return

    rows = []
    for r in results:
        row = {"종목": r.symbol, "전략": r.name, "점수": f"{r.score:.1f}"}
        m = r.metrics
        if "dividend_yield" in m:
            row["배당수익률"] = f"{m['dividend_yield']:.2%}"
        if "market_cap" in m and m["market_cap"]:
            row["시가총액"] = f"${m['market_cap']/1e9:.1f}B"
        if "beta" in m:
            row["베타"] = f"{m['beta']:.2f}"
        if "payout_ratio" in m and m["payout_ratio"]:
            row["배당성향"] = f"{m['payout_ratio']:.1%}"
        if "div_cagr_5yr" in m:
            row["5년 CAGR"] = f"{m['div_cagr_5yr']:.2%}"
        if "dividend_years" in m:
            row["배당 연수"] = f"{int(m['dividend_years'])}년"
        rows.append(row)

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def show_metrics_table(metrics) -> None:
    from backtest.report import format_metrics_table
    df = format_metrics_table(metrics)
    st.dataframe(df, use_container_width=True, hide_index=True)


def show_portfolio_table(holdings: list[str], weights: list[float], fetcher=None) -> None:
    if not holdings:
        st.warning("보유 종목이 없습니다.")
        return
    rows = []
    for sym, w in zip(holdings, weights):
        row = {"종목": sym, "비중": f"{w:.1%}"}
        if fetcher:
            info = fetcher.get_ticker_info(sym)
            row["배당수익률"] = f"{(info.get('dividendYield') or 0):.2%}"
            row["섹터"] = info.get("sector", "-")
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def metric_cards(data: list[tuple[str, str, str | None]]) -> None:
    """data: list of (label, value, delta)"""
    cols = st.columns(len(data))
    for col, (label, value, delta) in zip(cols, data):
        col.metric(label, value, delta)
