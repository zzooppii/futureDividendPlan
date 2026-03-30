"""전략 5: 커버드콜 배당 전략."""
import math

import numpy as np
import pandas as pd
from scipy.stats import norm

from strategies.base import ScreenResult, StrategyBase


class CoveredCallStrategy(StrategyBase):
    name = "covered_call"
    name_kr = "커버드콜 배당"
    description = "고배당 + 높은 옵션 유동성, 커버드콜 프리미엄 수입 시뮬레이션"

    MIN_YIELD = 0.02
    MIN_VOLUME = 500_000
    DTE = 30                   # 30일 만기 옵션

    def get_criteria(self) -> dict[str, str]:
        return {
            "배당수익률": f"최소 {self.MIN_YIELD:.0%}",
            "거래량": f"일평균 최소 {self.MIN_VOLUME:,}주",
            "옵션 유동성": "옵션 체인 존재",
        }

    def screen(self, universe: list[str], fetcher) -> list[str]:
        passed = []
        for sym in universe:
            try:
                if self._passes(sym, fetcher):
                    passed.append(sym)
            except Exception:
                continue
        return passed

    def _passes(self, symbol: str, fetcher) -> bool:
        info = fetcher.get_ticker_info(symbol)
        yld = self._safe_get(info, "dividendYield", "trailingAnnualDividendYield")
        if yld < self.MIN_YIELD:
            return False
        vol = self._safe_get(info, "averageVolume", "averageDailyVolume10Day")
        if vol < self.MIN_VOLUME:
            return False
        return True

    def score(self, symbols: list[str], fetcher) -> list[ScreenResult]:
        results = []
        for sym in symbols:
            try:
                results.append(self._score_one(sym, fetcher))
            except Exception:
                continue
        return sorted(results, key=lambda x: x.score, reverse=True)

    def _score_one(self, symbol: str, fetcher) -> ScreenResult:
        info = fetcher.get_ticker_info(symbol)
        price_df = fetcher.get_price_history(symbol)

        yld = self._safe_get(info, "dividendYield", "trailingAnnualDividendYield")
        vol = self._safe_get(info, "averageVolume", "averageDailyVolume10Day")
        price = self._safe_get(info, "currentPrice", "regularMarketPrice")

        # 내재변동성 (현재 옵션 체인에서 가져오거나 히스토리컬 추정)
        iv = self._estimate_iv(symbol, fetcher, price_df)

        # 월간 커버드콜 프리미엄 추정
        premium_pct = self._estimate_call_premium_pct(price, iv) if price > 0 else 0.0

        # 합산 수익률 (배당 + 커버드콜)
        combined_yield = yld + premium_pct * 12

        # 점수 계산
        yield_score = min(yld / 0.06, 1.0) * 25
        iv_score = min(iv / 0.40, 1.0) * 25
        liq_score = min(vol / 5_000_000, 1.0) * 20
        combined_score = min(combined_yield / 0.20, 1.0) * 20
        hv_iv_ratio = self._compute_hv(price_df) / iv if iv > 0 else 0.5
        ratio_score = min(hv_iv_ratio, 1.0) * 10

        total = yield_score + iv_score + liq_score + combined_score + ratio_score

        return ScreenResult(
            symbol=symbol,
            score=round(total, 2),
            metrics={
                "dividend_yield": round(yld, 4),
                "implied_vol_est": round(iv, 4),
                "monthly_premium_pct": round(premium_pct, 4),
                "combined_annual_yield": round(combined_yield, 4),
                "avg_volume": vol,
            },
            pass_fail={"yield_ok": True, "volume_ok": True},
            name=self.name_kr,
        )

    def _estimate_iv(self, symbol: str, fetcher, price_df: pd.DataFrame) -> float:
        """현재 옵션 체인에서 IV를 가져오거나, 없으면 히스토리컬 변동성으로 추정."""
        try:
            chain = fetcher.get_options_chain(symbol)
            if chain and "calls" in chain and not chain["calls"].empty:
                calls = chain["calls"]
                price = fetcher.get_current_price(symbol) or 0.0
                if price > 0:
                    atm = calls.iloc[(calls["strike"] - price).abs().argsort()[:1]]
                    iv = float(atm["impliedVolatility"].iloc[0])
                    if 0 < iv < 3.0:
                        return iv
        except Exception:
            pass
        return self._compute_hv(price_df) * 1.1  # HV에 10% 프리미엄

    def _compute_hv(self, price_df: pd.DataFrame, window: int = 30) -> float:
        if price_df.empty or len(price_df) < window + 1:
            return 0.25
        returns = price_df["Close"].pct_change().dropna()
        hv = float(returns.iloc[-window:].std() * math.sqrt(252))
        return max(hv, 0.10)

    def _estimate_call_premium_pct(self, price: float, iv: float) -> float:
        """ATM 30일 콜옵션 프리미엄을 Black-Scholes로 계산."""
        if price <= 0 or iv <= 0:
            return 0.0
        return black_scholes_call(S=price, K=price, T=self.DTE / 365, r=0.04, sigma=iv) / price


def black_scholes_call(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Black-Scholes ATM 콜옵션 가격."""
    if T <= 0 or sigma <= 0:
        return max(S - K, 0.0)
    d1 = (math.log(S / K) + (r + sigma ** 2 / 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
