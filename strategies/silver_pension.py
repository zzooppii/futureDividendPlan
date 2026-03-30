"""전략 2: 실버 연금 배당 전략."""
import pandas as pd
import numpy as np

from strategies.base import ScreenResult, StrategyBase


class SilverPensionStrategy(StrategyBase):
    name = "silver_pension"
    name_kr = "실버 연금 배당"
    description = "안정적 4~6% 수익률, 저변동성, 대형주 중심"

    MIN_YIELD = 0.04
    MAX_YIELD = 0.07
    MIN_MARKET_CAP = 10e9     # $10B
    MAX_BETA = 1.0
    MAX_PAYOUT = 0.80
    MIN_DIV_YEARS = 10

    def get_criteria(self) -> dict[str, str]:
        return {
            "배당수익률": f"{self.MIN_YIELD:.0%}~{self.MAX_YIELD:.0%}",
            "시가총액": f"최소 ${self.MIN_MARKET_CAP/1e9:.0f}B",
            "베타": f"최대 {self.MAX_BETA}",
            "배당성향": f"최대 {self.MAX_PAYOUT:.0%}",
            "배당 연수": f"최소 {self.MIN_DIV_YEARS}년 연속 배당",
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
        cap = self._safe_get(info, "marketCap")
        if cap < self.MIN_MARKET_CAP:
            return False

        yld = self._safe_get(info, "dividendYield", "trailingAnnualDividendYield")
        if not (self.MIN_YIELD <= yld <= self.MAX_YIELD):
            return False

        beta = self._safe_get(info, "beta")
        if 0 < beta > self.MAX_BETA:
            return False

        payout = self._safe_get(info, "payoutRatio")
        if payout > self.MAX_PAYOUT:
            return False

        divs = fetcher.get_dividends(symbol)
        if divs.empty:
            return False
        years = self._count_dividend_years(divs)
        return years >= self.MIN_DIV_YEARS

    def _count_dividend_years(self, divs: pd.Series) -> int:
        if divs.empty:
            return 0
        annual = divs.resample("YE").sum()
        count = 0
        for yr_sum in reversed(annual.values):
            if yr_sum > 0:
                count += 1
            else:
                break
        return count

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
        divs = fetcher.get_dividends(symbol)
        price_df = fetcher.get_price_history(symbol)

        yld = self._safe_get(info, "dividendYield", "trailingAnnualDividendYield")
        beta = self._safe_get(info, "beta")
        payout = self._safe_get(info, "payoutRatio")
        cap = self._safe_get(info, "marketCap")
        years = self._count_dividend_years(divs)

        # 수익률이 5% 스윗스팟에 가까울수록 높은 점수
        yield_proximity = max(0.0, 1.0 - abs(yld - 0.05) / 0.02)
        yield_score = yield_proximity * 25

        # 배당 연수
        streak_score = min(years / 20, 1.0) * 25

        # 저변동성
        vol_score = (max(0.0, 1.0 - beta) if beta > 0 else 0.5) * 20

        # 배당성향 여유
        payout_score = max(0.0, (0.80 - payout) / 0.80) * 15 if payout > 0 else 7.5

        # 시총
        cap_score = min(cap / 100e9, 1.0) * 15

        total = yield_score + streak_score + vol_score + payout_score + cap_score

        return ScreenResult(
            symbol=symbol,
            score=round(total, 2),
            metrics={
                "dividend_yield": round(yld, 4),
                "beta": beta,
                "payout_ratio": payout,
                "market_cap": cap,
                "dividend_years": years,
            },
            pass_fail={
                "yield_range": self.MIN_YIELD <= yld <= self.MAX_YIELD,
                "low_beta": beta <= self.MAX_BETA,
                "streak": years >= self.MIN_DIV_YEARS,
            },
            name=self.name_kr,
        )
