"""백테스트 결과 포매팅."""
import pandas as pd

from backtest.engine import BacktestResult
from backtest.metrics import BacktestMetrics


def format_metrics_table(metrics: BacktestMetrics) -> pd.DataFrame:
    """지표를 읽기 쉬운 DataFrame으로 변환."""
    rows = [
        ("기간", f"{metrics.start_date} ~ {metrics.end_date} ({metrics.years:.1f}년)"),
        ("총 수익률", f"{metrics.total_return:.2%}"),
        ("연평균 수익률 (CAGR)", f"{metrics.cagr:.2%}"),
        ("연간 변동성", f"{metrics.annual_volatility:.2%}"),
        ("샤프 비율", f"{metrics.sharpe_ratio:.3f}"),
        ("소르티노 비율", f"{metrics.sortino_ratio:.3f}"),
        ("칼마 비율", f"{metrics.calmar_ratio:.3f}"),
        ("최대 낙폭 (MDD)", f"{metrics.max_drawdown:.2%}"),
        ("MDD 지속 기간", f"{metrics.max_drawdown_duration}일"),
        ("총 배당 수입", f"${metrics.total_dividend_income:,.0f}"),
        ("연평균 배당 수입", f"${metrics.avg_annual_dividend:,.0f}"),
        ("투자원금 대비 배당 수익률", f"{metrics.yield_on_cost:.2%}"),
        ("총 거래 횟수", f"{metrics.total_trades}회"),
    ]
    return pd.DataFrame(rows, columns=["지표", "값"])


def compare_strategies(results: dict[str, BacktestResult]) -> pd.DataFrame:
    """여러 전략 결과를 비교 테이블로 반환."""
    rows = []
    for name, res in results.items():
        m = res.metrics
        rows.append({
            "전략": name,
            "총 수익률": f"{m.total_return:.2%}",
            "CAGR": f"{m.cagr:.2%}",
            "샤프": f"{m.sharpe_ratio:.2f}",
            "소르티노": f"{m.sortino_ratio:.2f}",
            "MDD": f"{m.max_drawdown:.2%}",
            "배당 수입": f"${m.total_dividend_income:,.0f}",
            "YOC": f"{m.yield_on_cost:.2%}",
        })
    return pd.DataFrame(rows)


def get_top_dividend_payers(dividends_df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    if dividends_df.empty:
        return pd.DataFrame()
    by_symbol = dividends_df.groupby("symbol")["total"].sum().sort_values(ascending=False)
    return by_symbol.head(top_n).reset_index().rename(columns={"symbol": "종목", "total": "총 배당 수입($)"})


def get_annual_dividend_table(dividends_df: pd.DataFrame) -> pd.DataFrame:
    if dividends_df.empty:
        return pd.DataFrame()
    df = dividends_df.copy()
    df["year"] = pd.to_datetime(df["date"]).dt.year
    return df.groupby("year")["total"].sum().reset_index().rename(
        columns={"year": "연도", "total": "배당 수입($)"}
    )
