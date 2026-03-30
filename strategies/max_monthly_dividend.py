"""전략 1: 월배당 최대화 전략."""
import pandas as pd

from strategies.base import ScreenResult, StrategyBase


class MaxMonthlyDividendStrategy(StrategyBase):
    name = "max_monthly"
    name_kr = "월배당 최대화"
    description = "월배당 ETF/주식 중심, 최고 현금 흐름 최적화"

    MIN_YIELD = 0.03          # 최소 수익률 3%
    MIN_MARKET_CAP = 5e8      # $500M
    MIN_VOLUME = 200_000

    def get_criteria(self) -> dict[str, str]:
        return {
            "월배당": "최근 3년 연평균 12회 이상 배당 지급",
            "배당수익률": f"최소 {self.MIN_YIELD:.0%}",
            "시가총액": f"최소 ${self.MIN_MARKET_CAP/1e6:.0f}M",
            "거래량": f"일평균 최소 {self.MIN_VOLUME:,}주",
        }

    def screen(self, universe: list[str], fetcher) -> list[str]:
        passed = []
        for sym in universe:
            try:
                if not self._passes(sym, fetcher):
                    continue
                passed.append(sym)
            except Exception:
                continue
        return passed

    def _passes(self, symbol: str, fetcher) -> bool:
        info = fetcher.get_ticker_info(symbol)
        cap = self._safe_get(info, "marketCap")
        if cap < self.MIN_MARKET_CAP:
            return False
        vol = self._safe_get(info, "averageVolume", "averageDailyVolume10Day")
        if vol < self.MIN_VOLUME:
            return False

        divs = fetcher.get_dividends(symbol)
        if divs.empty:
            return False

        yld = self._safe_get(info, "dividendYield", "trailingAnnualDividendYield")
        if yld < self.MIN_YIELD:
            return False

        return self._is_monthly_payer(divs)

    def _is_monthly_payer(self, divs: pd.Series) -> bool:
        if divs.empty:
            return False
        recent = divs[divs.index >= divs.index[-1] - pd.DateOffset(years=3)]
        if recent.empty:
            return False
        annual_counts = recent.groupby(recent.index.year).count()
        median_count = annual_counts.median()
        return median_count >= 11

    def score(self, symbols: list[str], fetcher) -> list[ScreenResult]:
        results = []
        for sym in symbols:
            try:
                result = self._score_one(sym, fetcher)
                results.append(result)
            except Exception:
                continue
        return sorted(results, key=lambda x: x.score, reverse=True)

    def _score_one(self, symbol: str, fetcher) -> ScreenResult:
        info = fetcher.get_ticker_info(symbol)
        divs = fetcher.get_dividends(symbol)

        yld = self._safe_get(info, "dividendYield", "trailingAnnualDividendYield")
        cap = self._safe_get(info, "marketCap")
        vol = self._safe_get(info, "averageVolume", "averageDailyVolume10Day")

        # 배당 일관성 (변동계수 낮을수록 좋음)
        consistency_score = self._compute_consistency(divs)

        # 점수 계산 (가중치 합 = 100)
        yield_score = min(yld / 0.15, 1.0) * 40          # 수익률 40%
        cons_score = consistency_score * 25               # 일관성 25%
        liq_score = min(vol / 1_000_000, 1.0) * 15       # 유동성 15%
        cap_score = min(cap / 50e9, 1.0) * 10             # 시총 10%
        # 3년 수익률 10%
        ret_score = self._compute_return_score(fetcher.get_price_history(symbol)) * 10

        total = yield_score + cons_score + liq_score + cap_score + ret_score

        return ScreenResult(
            symbol=symbol,
            score=round(total, 2),
            metrics={
                "dividend_yield": round(yld, 4),
                "market_cap": cap,
                "avg_volume": vol,
                "is_monthly": True,
            },
            pass_fail={"monthly_payer": True, "yield_ok": True},
            name=self.name_kr,
        )

    def _compute_consistency(self, divs: pd.Series) -> float:
        if divs.empty:
            return 0.0
        monthly = divs.resample("ME").sum()
        nonzero = monthly[monthly > 0]
        if len(nonzero) < 2:
            return 0.0
        cv = nonzero.std() / nonzero.mean()
        return max(0.0, 1.0 - min(cv, 1.0))

    def _compute_return_score(self, price_df: pd.DataFrame) -> float:
        if price_df.empty or len(price_df) < 252:
            return 0.5
        close = price_df["Close"]
        ret_3yr = (close.iloc[-1] / close.iloc[max(-756, -len(close))]) - 1
        return min(max(ret_3yr / 0.3 + 0.5, 0.0), 1.0)
