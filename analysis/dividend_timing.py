"""배당락일 타이밍 분석 모듈."""
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class TimingAnalysis:
    symbol: str
    avg_pre_exdiv_return: float    # 배당락 5일 전 평균 수익률
    avg_exdiv_drop: float          # 배당락일 평균 주가 하락
    avg_drop_vs_dividend: float    # 하락폭 / 배당금 비율
    recovery_days: float           # 평균 회복 소요일
    optimal_buy_days_before: int   # 최적 매수 타이밍 (배당락 N일 전)
    sample_size: int


def analyze_dividend_timing(symbol: str, fetcher) -> TimingAnalysis | None:
    """배당락일 전후 주가 패턴을 분석한다."""
    divs = fetcher.get_dividends(symbol)
    price_df = fetcher.get_price_history(symbol)

    if divs.empty or price_df.empty or len(divs) < 4:
        return None

    pre_returns = []
    drops = []
    drop_ratios = []
    recovery_list = []

    for ex_date, div_amount in divs.items():
        if div_amount <= 0:
            continue

        # 배당락일을 가격 데이터에서 찾기
        idx_pos = price_df.index.searchsorted(ex_date)
        if idx_pos < 6 or idx_pos >= len(price_df) - 30:
            continue

        # T-1 종가 (배당락 하루 전)
        pre_close = float(price_df["Close"].iloc[idx_pos - 1])
        # T 시가 (배당락일 시초가)
        ex_open = float(price_df["Open"].iloc[idx_pos])
        # T-5 ~ T-1 기간 수익률
        t5_close = float(price_df["Close"].iloc[idx_pos - 6])
        if t5_close <= 0 or pre_close <= 0:
            continue

        pre_ret = (pre_close - t5_close) / t5_close
        drop = pre_close - ex_open
        drop_ratio = drop / div_amount if div_amount > 0 else 0.0

        pre_returns.append(pre_ret)
        drops.append(drop)
        drop_ratios.append(drop_ratio)

        # 회복 소요일 계산 (최대 30일)
        recovery = _compute_recovery_days(price_df, idx_pos, pre_close)
        recovery_list.append(recovery)

    if not pre_returns:
        return None

    avg_pre = float(np.mean(pre_returns))
    avg_drop = float(np.mean(drops))
    avg_ratio = float(np.mean(drop_ratios))
    avg_recovery = float(np.mean([r for r in recovery_list if r is not None]))

    # 최적 매수 타이밍: pre_return이 양수이면 배당락 전 매수 유리
    # 실제 윈도우별 수익률을 계산하여 최적값 탐색
    optimal = _find_optimal_buy_window(divs, price_df)

    return TimingAnalysis(
        symbol=symbol,
        avg_pre_exdiv_return=round(avg_pre, 4),
        avg_exdiv_drop=round(avg_drop, 4),
        avg_drop_vs_dividend=round(avg_ratio, 3),
        recovery_days=round(avg_recovery, 1),
        optimal_buy_days_before=optimal,
        sample_size=len(pre_returns),
    )


def _compute_recovery_days(price_df: pd.DataFrame, ex_idx: int, target_price: float) -> int | None:
    """배당락일 이후 주가가 target_price를 회복하는 데 걸리는 일수."""
    max_window = min(30, len(price_df) - ex_idx - 1)
    for i in range(1, max_window + 1):
        if float(price_df["Close"].iloc[ex_idx + i]) >= target_price:
            return i
    return max_window  # 30일 내 미회복


def _find_optimal_buy_window(divs: pd.Series, price_df: pd.DataFrame) -> int:
    """배당락 N일 전 매수 후 배당락 당일 매도 시 수익률이 가장 좋은 N을 반환."""
    window_returns = {n: [] for n in range(1, 11)}

    for ex_date, div_amount in divs.items():
        if div_amount <= 0:
            continue
        idx = price_df.index.searchsorted(ex_date)
        if idx < 12 or idx >= len(price_df):
            continue
        ex_close = float(price_df["Close"].iloc[idx])

        for n in range(1, 11):
            if idx - n < 0:
                continue
            buy_price = float(price_df["Close"].iloc[idx - n])
            if buy_price <= 0:
                continue
            ret = (ex_close + div_amount - buy_price) / buy_price
            window_returns[n].append(ret)

    best_n = 5
    best_ret = -999.0
    for n, rets in window_returns.items():
        if rets:
            avg = float(np.mean(rets))
            if avg > best_ret:
                best_ret = avg
                best_n = n
    return best_n
