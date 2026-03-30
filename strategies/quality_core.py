"""전략 4: 퀄리티 배당 핵심 포트폴리오."""
import pandas as pd
import numpy as np

from strategies.base import ScreenResult, StrategyBase


class QualityCoreStrategy(StrategyBase):
    name = "quality_core"
    name_kr = "퀄리티 배당 코어"
    description = "ROE 15% 이상, 안정적 현금흐름, 10년+ 배당 이력"

    MIN_ROE = 0.15
    MIN_DIV_YEARS = 10
    MAX_PAYOUT = 0.75

    def get_criteria(self) -> dict[str, str]:
        return {
            "ROE": f"최소 {self.MIN_ROE:.0%}",
            "잉여현금흐름": "양(+)의 FCF",
            "배당 이력": f"최소 {self.MIN_DIV_YEARS}년 연속 배당",
            "배당성향": f"최대 {self.MAX_PAYOUT:.0%}",
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

        roe = self._safe_get(info, "returnOnEquity")
        if roe < self.MIN_ROE:
            return False

        fcf = info.get("freeCashflow") or 0.0
        if fcf <= 0:
            return False

        payout = self._safe_get(info, "payoutRatio")
        if payout > self.MAX_PAYOUT and payout > 0:
            return False

        divs = fetcher.get_dividends(symbol)
        if divs.empty:
            return False
        years = self._count_div_years(divs)
        return years >= self.MIN_DIV_YEARS

    def _count_div_years(self, divs: pd.Series) -> int:
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
        financials = fetcher.get_financials(symbol)

        roe = self._safe_get(info, "returnOnEquity")
        fcf = float(info.get("freeCashflow") or 0)
        payout = self._safe_get(info, "payoutRatio")
        dte = self._safe_get(info, "debtToEquity")
        years = self._count_div_years(divs)

        # ROE 점수
        roe_score = min(roe / 0.30, 1.0) * 25

        # FCF 커버리지
        rate = self._safe_get(info, "dividendRate")
        shares = self._safe_get(info, "sharesOutstanding")
        total_div = rate * shares
        if total_div > 0 and fcf > 0:
            coverage = fcf / total_div
            cf_score = min(coverage / 3.0, 1.0) * 25
        else:
            cf_score = 12.5

        # 배당 연수
        streak_score = min(years / 25, 1.0) * 20

        # 현금흐름 안정성 (재무제표에서 변동계수 계산)
        cf_stability = self._compute_cf_stability(financials.get("cashflow", pd.DataFrame()))
        stability_score = cf_stability * 15

        # 부채비율 (낮을수록 좋음)
        debt_score = max(0.0, 1.0 - dte / 200) * 15 if dte > 0 else 7.5

        total = roe_score + cf_score + streak_score + stability_score + debt_score

        return ScreenResult(
            symbol=symbol,
            score=round(total, 2),
            metrics={
                "roe": round(roe, 4),
                "free_cashflow": fcf,
                "payout_ratio": payout,
                "debt_to_equity": dte,
                "dividend_years": years,
            },
            pass_fail={
                "roe_ok": roe >= self.MIN_ROE,
                "fcf_positive": fcf > 0,
                "streak_ok": years >= self.MIN_DIV_YEARS,
            },
            name=self.name_kr,
        )

    def _compute_cf_stability(self, cashflow_df: pd.DataFrame) -> float:
        if cashflow_df.empty:
            return 0.5
        for key in ["Operating Cash Flow", "OperatingCashFlow", "Total Cash From Operating Activities"]:
            if key in cashflow_df.index:
                vals = cashflow_df.loc[key].dropna().values.astype(float)
                if len(vals) < 2:
                    return 0.5
                mean = np.mean(vals)
                if mean == 0:
                    return 0.0
                cv = np.std(vals) / abs(mean)
                return max(0.0, 1.0 - min(cv, 1.0))
        return 0.5
