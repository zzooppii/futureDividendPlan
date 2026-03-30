"""백테스트 성과 지표 계산."""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from config import RISK_FREE_RATE


@dataclass
class BacktestMetrics:
    # 기간
    start_date: str
    end_date: str
    years: float

    # 수익률
    total_return: float
    cagr: float
    buy_hold_return: float       # 단순 보유 시 수익률 (비교용)

    # 리스크 조정 지표
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float

    # 낙폭
    max_drawdown: float
    max_drawdown_duration: int   # 거래일 수

    # 배당
    total_dividend_income: float
    avg_annual_dividend: float
    yield_on_cost: float

    # 변동성
    annual_volatility: float

    # 거래
    total_trades: int


def compute_metrics(
    daily_values: pd.Series,
    initial_capital: float,
    dividend_events: list,
    trades: list,
) -> BacktestMetrics:
    if daily_values.empty:
        return _empty_metrics()

    daily_values = daily_values.sort_index().dropna()
    returns = daily_values.pct_change().dropna()

    years = len(daily_values) / 252
    total_return = (daily_values.iloc[-1] / daily_values.iloc[0]) - 1
    cagr = (1 + total_return) ** (1 / max(years, 0.01)) - 1 if years > 0 else 0.0

    # 변동성
    annual_vol = float(returns.std() * np.sqrt(252))

    # 샤프비율
    excess = returns.mean() * 252 - RISK_FREE_RATE
    sharpe = excess / annual_vol if annual_vol > 0 else 0.0

    # 소르티노비율
    downside = returns[returns < 0].std() * np.sqrt(252)
    sortino = excess / downside if downside > 0 else 0.0

    # 최대 낙폭
    max_dd, max_dd_dur = compute_max_drawdown(daily_values)

    # 칼마비율
    calmar = cagr / abs(max_dd) if max_dd != 0 else 0.0

    # 배당 수익
    total_div = sum(e.total_amount for e in dividend_events)
    avg_annual_div = total_div / max(years, 1)
    yoc = total_div / initial_capital

    return BacktestMetrics(
        start_date=str(daily_values.index[0].date()),
        end_date=str(daily_values.index[-1].date()),
        years=round(years, 2),
        total_return=round(total_return, 4),
        cagr=round(cagr, 4),
        buy_hold_return=0.0,       # 엔진에서 채움
        sharpe_ratio=round(sharpe, 3),
        sortino_ratio=round(sortino, 3),
        calmar_ratio=round(calmar, 3),
        max_drawdown=round(max_dd, 4),
        max_drawdown_duration=max_dd_dur,
        total_dividend_income=round(total_div, 2),
        avg_annual_dividend=round(avg_annual_div, 2),
        yield_on_cost=round(yoc, 4),
        annual_volatility=round(annual_vol, 4),
        total_trades=len(trades),
    )


def compute_max_drawdown(values: pd.Series) -> tuple[float, int]:
    """최대 낙폭과 낙폭 지속 기간(거래일) 반환."""
    rolling_max = values.cummax()
    drawdown = (values - rolling_max) / rolling_max

    max_dd = float(drawdown.min())
    if max_dd == 0.0:
        return 0.0, 0

    # 낙폭 지속 기간 계산
    in_drawdown = drawdown < 0
    max_dur = 0
    cur_dur = 0
    for dd in in_drawdown:
        if dd:
            cur_dur += 1
            max_dur = max(max_dur, cur_dur)
        else:
            cur_dur = 0

    return max_dd, max_dur


def compute_drawdown_series(values: pd.Series) -> pd.Series:
    rolling_max = values.cummax()
    return (values - rolling_max) / rolling_max


def _empty_metrics() -> BacktestMetrics:
    return BacktestMetrics(
        start_date="", end_date="", years=0,
        total_return=0, cagr=0, buy_hold_return=0,
        sharpe_ratio=0, sortino_ratio=0, calmar_ratio=0,
        max_drawdown=0, max_drawdown_duration=0,
        total_dividend_income=0, avg_annual_dividend=0, yield_on_cost=0,
        annual_volatility=0, total_trades=0,
    )
