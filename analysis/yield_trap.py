"""배당함정(Yield Trap) 탐지 모듈."""
from dataclasses import dataclass, field

import pandas as pd
import numpy as np


@dataclass
class YieldTrapWarning:
    symbol: str
    is_trap: bool
    risk_level: str               # "low" | "medium" | "high"
    warnings: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    trap_score: int = 0           # 레드플래그 누적 점수


def detect_yield_trap(symbol: str, fetcher) -> YieldTrapWarning:
    """배당함정 위험도를 평가한다."""
    info = fetcher.get_ticker_info(symbol)
    divs = fetcher.get_dividends(symbol)
    price_df = fetcher.get_price_history(symbol)
    financials = fetcher.get_financials(symbol)

    warnings = []
    trap_score = 0
    metrics = {}

    yield_val = info.get("dividendYield") or info.get("trailingAnnualDividendYield") or 0.0
    payout = info.get("payoutRatio") or 0.0
    metrics["dividend_yield"] = yield_val
    metrics["payout_ratio"] = payout

    # ── 레드플래그 1: 초고수익률 + 높은 배당성향 ───────────────
    if yield_val > 0.08 and payout > 0.80:
        warnings.append(f"초고배당(수익률 {yield_val:.1%}) + 높은 배당성향({payout:.1%}) - 지속 불가능 위험")
        trap_score += 3

    # ── 레드플래그 2: 주가 폭락으로 인한 수익률 상승 ─────────────
    if not price_df.empty:
        price_drop = _compute_price_drop(price_df)
        metrics["price_drop_1yr"] = price_drop
        if price_drop < -0.30:
            warnings.append(f"최근 1년 주가 {price_drop:.1%} 하락 - 수익률이 주가 하락으로 부풀려졌을 가능성")
            trap_score += 2

    # ── 레드플래그 3: 적자 or 이익 감소 중 배당 유지 ──────────────
    if not financials.get("income", pd.DataFrame()).empty:
        earnings_warning = _check_earnings_decline(financials["income"])
        if earnings_warning:
            warnings.append(earnings_warning)
            trap_score += 2

    # ── 레드플래그 4: FCF < 배당 지급액 ────────────────────────
    fcf = info.get("freeCashflow") or 0.0
    if fcf < 0:
        warnings.append(f"잉여현금흐름 마이너스(${fcf:,.0f}) - 차입으로 배당 지급 중")
        trap_score += 2
        metrics["fcf_negative"] = True
    elif fcf > 0:
        rate = info.get("dividendRate") or 0.0
        shares = info.get("sharesOutstanding") or 0.0
        total_div = rate * shares
        if total_div > 0 and fcf < total_div:
            warnings.append(f"FCF(${fcf:,.0f})이 배당지급(${total_div:,.0f})에 미달 - 재무 압박")
            trap_score += 1

    # ── 레드플래그 5: 높은 부채비율 + 고배당 ──────────────────────
    dte = info.get("debtToEquity") or 0.0
    metrics["debt_to_equity"] = dte
    if dte > 200 and yield_val > 0.06:
        warnings.append(f"높은 부채비율(D/E {dte:.0f}%) + 고배당(수익률 {yield_val:.1%}) - 금리 위험")
        trap_score += 1

    # ── 레드플래그 6: 최근 배당 삭감 이력 ────────────────────────
    if not divs.empty:
        cut_detected = _detect_dividend_cut(divs)
        if cut_detected:
            warnings.append("최근 3년 내 배당 삭감 이력 발견")
            trap_score += 2

    # ── 위험 등급 결정 ──────────────────────────────────────────
    if trap_score >= 5:
        risk_level = "high"
        is_trap = True
    elif trap_score >= 3:
        risk_level = "medium"
        is_trap = True
    else:
        risk_level = "low"
        is_trap = False

    return YieldTrapWarning(
        symbol=symbol,
        is_trap=is_trap,
        risk_level=risk_level,
        warnings=warnings,
        metrics=metrics,
        trap_score=trap_score,
    )


def _compute_price_drop(price_df: pd.DataFrame) -> float:
    if len(price_df) < 2:
        return 0.0
    now = price_df.index.max()
    year_ago = now - pd.DateOffset(years=1)
    past = price_df[price_df.index <= year_ago]
    if past.empty:
        return 0.0
    past_price = float(past["Close"].iloc[-1])
    current_price = float(price_df["Close"].iloc[-1])
    if past_price <= 0:
        return 0.0
    return (current_price - past_price) / past_price


def _check_earnings_decline(income_df: pd.DataFrame) -> str | None:
    for key in ["Net Income", "NetIncome", "Net Income Common Stockholders"]:
        if key in income_df.index:
            vals = income_df.loc[key].dropna().sort_index(ascending=False)
            if len(vals) < 2:
                return None
            nums = vals.values.astype(float)
            if nums[0] < 0:
                return f"최근 회계연도 순손실 발생 - 배당 지속가능성 의문"
            # 2년 연속 이익 감소
            if len(nums) >= 3 and nums[0] < nums[1] < nums[2]:
                pct = (nums[0] - nums[2]) / abs(nums[2])
                return f"2년 연속 이익 감소 ({pct:.1%}) - 배당 삭감 위험"
            return None
    return None


def _detect_dividend_cut(divs: pd.Series) -> bool:
    if divs.empty:
        return False
    # 연간 합계 계산
    annual = divs.resample("YE").sum()
    if len(annual) < 2:
        return False
    recent3 = annual.iloc[-3:] if len(annual) >= 3 else annual
    for i in range(1, len(recent3)):
        if recent3.iloc[i] < recent3.iloc[i - 1] * 0.85:  # 15% 이상 감소
            return True
    return False
