"""배당 지속가능성 점수 계산."""
from dataclasses import dataclass, field

import pandas as pd
import numpy as np


@dataclass
class SustainabilityScore:
    symbol: str
    overall_score: float          # 0~100점
    payout_ratio_score: float     # 배당성향 점수 (0~25)
    cf_coverage_score: float      # FCF 커버리지 점수 (0~25)
    earnings_stability: float     # 이익 안정성 점수 (0~25)
    dividend_trend_score: float   # 배당 추세 점수 (0~25)
    details: dict = field(default_factory=dict)
    grade: str = ""               # A/B/C/D/F

    def __post_init__(self):
        if not self.grade:
            s = self.overall_score
            if s >= 80:
                self.grade = "A"
            elif s >= 65:
                self.grade = "B"
            elif s >= 50:
                self.grade = "C"
            elif s >= 35:
                self.grade = "D"
            else:
                self.grade = "F"


def compute_sustainability(symbol: str, fetcher) -> SustainabilityScore:
    """배당 지속가능성 점수를 계산한다."""
    info = fetcher.get_ticker_info(symbol)
    financials = fetcher.get_financials(symbol)
    divs = fetcher.get_dividends(symbol)

    # ── 1. 배당성향 점수 (0~25) ─────────────────────────────
    payout = info.get("payoutRatio") or 0.0
    if payout <= 0.4:
        pr_score = 25.0
    elif payout <= 0.6:
        pr_score = 20.0
    elif payout <= 0.8:
        pr_score = 10.0
    else:
        pr_score = 0.0

    # ── 2. FCF 커버리지 점수 (0~25) ──────────────────────────
    cf_score = _compute_cf_coverage_score(info, financials.get("cashflow", pd.DataFrame()))

    # ── 3. 이익 안정성 (0~25) ────────────────────────────────
    stability_score = _compute_earnings_stability(financials.get("income", pd.DataFrame()))

    # ── 4. 배당 추세 (0~25) ──────────────────────────────────
    trend_score, cagr = _compute_dividend_trend(divs)

    overall = pr_score + cf_score + stability_score + trend_score

    return SustainabilityScore(
        symbol=symbol,
        overall_score=round(overall, 1),
        payout_ratio_score=pr_score,
        cf_coverage_score=cf_score,
        earnings_stability=stability_score,
        dividend_trend_score=trend_score,
        details={
            "payout_ratio": round(payout, 3),
            "dividend_cagr_5yr": round(cagr, 4),
            "free_cashflow": info.get("freeCashflow"),
        },
    )


def _compute_cf_coverage_score(info: dict, cashflow_df: pd.DataFrame) -> float:
    fcf = info.get("freeCashflow") or 0.0
    if fcf <= 0:
        return 0.0

    # 재무제표에서 배당 지급액 추출
    div_paid = 0.0
    if not cashflow_df.empty:
        for key in ["CommonStockDividendPaid", "DividendsPaid", "Cash Dividends Paid"]:
            if key in cashflow_df.index:
                vals = cashflow_df.loc[key].dropna()
                if not vals.empty:
                    div_paid = abs(float(vals.iloc[0]))
                    break

    if div_paid <= 0:
        # info에서 dividendRate * sharesOutstanding 추정
        rate = info.get("dividendRate") or 0.0
        shares = info.get("sharesOutstanding") or 0.0
        div_paid = rate * shares

    if div_paid <= 0:
        return 15.0  # 데이터 없으면 중간값

    coverage = fcf / div_paid
    if coverage >= 2.0:
        return 25.0
    elif coverage >= 1.5:
        return 20.0
    elif coverage >= 1.0:
        return 10.0
    else:
        return 0.0


def _compute_earnings_stability(income_df: pd.DataFrame) -> float:
    if income_df.empty:
        return 12.5  # 중간값

    eps_keys = ["Basic EPS", "Diluted EPS", "EPS", "Net Income"]
    series = None
    for key in eps_keys:
        if key in income_df.index:
            series = income_df.loc[key].dropna()
            if len(series) >= 2:
                break

    if series is None or len(series) < 2:
        return 12.5

    vals = series.values.astype(float)
    mean = np.mean(vals)
    if mean == 0:
        return 0.0

    cv = np.std(vals) / abs(mean)  # 변동계수 (낮을수록 안정)
    # CV 0 -> 25점, CV 1 -> 0점
    score = max(0.0, 25.0 * (1 - min(cv, 1.0)))
    return round(score, 1)


def _compute_dividend_trend(divs: pd.Series) -> tuple[float, float]:
    """(trend_score, 5년 CAGR)"""
    if divs.empty:
        return 0.0, 0.0

    now = divs.index.max()
    year_ago5 = now - pd.DateOffset(years=5)
    year_ago1 = now - pd.DateOffset(years=1)

    recent = divs[divs.index >= year_ago1].sum()
    past5 = divs[(divs.index >= year_ago5) & (divs.index < year_ago5 + pd.DateOffset(years=1))].sum()

    if past5 <= 0:
        # 5년 전 데이터 없으면 최근 추세만 확인
        return 15.0, 0.0

    cagr = (recent / past5) ** (1 / 5) - 1

    if cagr >= 0.08:
        score = 25.0
    elif cagr >= 0.04:
        score = 20.0
    elif cagr >= 0.0:
        score = 12.0
    else:
        score = 0.0

    return score, cagr
