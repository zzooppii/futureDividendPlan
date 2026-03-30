"""전략 3: 장기 배당 성장 전략."""
import pandas as pd
import numpy as np

from strategies.base import ScreenResult, StrategyBase


class DividendGrowthStrategy(StrategyBase):
    name = "dividend_growth"
    name_kr = "장기 배당 성장"
    description = "연 8% 이상 배당 성장률, 낮은 배당성향, 강한 매출 성장"

    MIN_DIV_CAGR = 0.08
    MAX_PAYOUT = 0.60
    MIN_STREAK = 5              # 최소 5년 연속 배당 증가

    def get_criteria(self) -> dict[str, str]:
        return {
            "배당 성장률": f"5년 CAGR {self.MIN_DIV_CAGR:.0%} 이상",
            "배당성향": f"최대 {self.MAX_PAYOUT:.0%}",
            "매출 성장": "양(+)의 매출 성장",
            "연속 증가": f"최소 {self.MIN_STREAK}년 연속 배당 증가",
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
        payout = self._safe_get(info, "payoutRatio")
        if payout > self.MAX_PAYOUT and payout > 0:
            return False

        divs = fetcher.get_dividends(symbol)
        if divs.empty:
            return False

        cagr = self._compute_div_cagr(divs, years=5)
        if cagr < self.MIN_DIV_CAGR:
            return False

        streak = self._compute_increase_streak(divs)
        return streak >= self.MIN_STREAK

    def _compute_div_cagr(self, divs: pd.Series, years: int = 5) -> float:
        if divs.empty:
            return 0.0
        now = divs.index.max()
        recent = divs[divs.index >= now - pd.DateOffset(years=1)].sum()
        past_start = now - pd.DateOffset(years=years)
        past_end = now - pd.DateOffset(years=years - 1)
        past = divs[(divs.index >= past_start) & (divs.index < past_end)].sum()
        if past <= 0:
            return 0.0
        return (recent / past) ** (1 / years) - 1

    def _compute_increase_streak(self, divs: pd.Series) -> int:
        if divs.empty:
            return 0
        annual = divs.resample("YE").sum().dropna()
        if len(annual) < 2:
            return 0
        streak = 0
        vals = annual.values[::-1]  # 최신부터
        for i in range(len(vals) - 1):
            if vals[i] >= vals[i + 1] * 0.99:  # 1% 이내 감소는 허용
                streak += 1
            else:
                break
        return streak

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

        cagr = self._compute_div_cagr(divs, years=5)
        payout = self._safe_get(info, "payoutRatio")
        rev_growth = self._safe_get(info, "revenueGrowth")
        earn_growth = self._safe_get(info, "earningsGrowth", "earningsQuarterlyGrowth")
        streak = self._compute_increase_streak(divs)

        # CAGR 점수 (8% = 기준, 15% = 만점)
        cagr_score = min(cagr / 0.15, 1.0) * 35

        # 배당성향 여유 (낮을수록 좋음)
        payout_score = max(0.0, (0.60 - payout) / 0.60) * 20 if payout > 0 else 10.0

        # 매출 성장
        rev_score = min(max(rev_growth / 0.20, 0.0), 1.0) * 20

        # 이익 성장
        earn_score = min(max(earn_growth / 0.20, 0.0), 1.0) * 15

        # 연속 증가 연수
        streak_score = min(streak / 15, 1.0) * 10

        total = cagr_score + payout_score + rev_score + earn_score + streak_score

        return ScreenResult(
            symbol=symbol,
            score=round(total, 2),
            metrics={
                "div_cagr_5yr": round(cagr, 4),
                "payout_ratio": payout,
                "revenue_growth": rev_growth,
                "earnings_growth": earn_growth,
                "increase_streak": streak,
            },
            pass_fail={
                "cagr_ok": cagr >= self.MIN_DIV_CAGR,
                "payout_ok": payout <= self.MAX_PAYOUT,
                "streak_ok": streak >= self.MIN_STREAK,
            },
            name=self.name_kr,
        )
