"""전략 무관 백테스팅 엔진."""
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from backtest.metrics import BacktestMetrics, compute_metrics
from backtest.portfolio import Portfolio
from config import BACKTEST_END, BACKTEST_START


@dataclass
class BacktestConfig:
    start_date: str = BACKTEST_START
    end_date: str = BACKTEST_END
    initial_capital: float = 100_000.0
    rebalance_frequency: str = "quarterly"   # "monthly" | "quarterly" | "annual"
    reinvest_dividends: bool = True
    max_positions: int = 20


@dataclass
class BacktestResult:
    daily_values: pd.Series
    drawdown_series: pd.Series
    dividend_income_series: pd.Series      # 일별 배당 수입
    trades_df: pd.DataFrame
    dividends_df: pd.DataFrame
    metrics: BacktestMetrics
    strategy_name: str
    config: BacktestConfig
    disclaimer: str = ""


class BacktestEngine:
    DISCLAIMER = (
        "⚠️ 주의: 2021년 이전 백테스트는 가격·배당 기반 지표만 사용하며 "
        "ROE/FCF 등 펀더멘털은 포함되지 않습니다. "
        "또한 생존 편향이 존재하므로 실제 성과와 차이가 있을 수 있습니다."
    )

    def __init__(self, config: BacktestConfig, fetcher):
        self.config = config
        self.fetcher = fetcher

    def run(self, strategy, universe: list[str]) -> BacktestResult:
        cfg = self.config
        portfolio = Portfolio(cfg.initial_capital)

        # 가격 데이터 미리 로딩
        price_data: dict[str, pd.DataFrame] = {}
        for sym in universe:
            df = self.fetcher.get_price_history(sym, start=cfg.start_date, end=cfg.end_date)
            if not df.empty:
                price_data[sym] = df

        if not price_data:
            return self._empty_result(strategy.name_kr, cfg)

        # 공통 거래일 인덱스
        all_dates = sorted(
            set.union(*[set(df.index) for df in price_data.values()])
        )
        all_dates = [d for d in all_dates if cfg.start_date <= str(d.date()) <= cfg.end_date]

        # 리밸런싱 날짜 계산
        rebalance_dates = self._compute_rebalance_dates(all_dates, cfg.rebalance_frequency)

        daily_values = {}
        div_income_by_day = {}
        current_holdings: list[str] = []

        for i, dt in enumerate(all_dates):
            dt_str = str(dt.date())
            prices = {sym: float(df.loc[dt, "Close"]) for sym, df in price_data.items() if dt in df.index}
            prices = {k: v for k, v in prices.items() if v > 0}

            # 배당 수령
            day_div = 0.0
            for sym, df in price_data.items():
                if dt not in df.index:
                    continue
                div_amt = float(df.loc[dt, "Dividends"]) if "Dividends" in df.columns else 0.0
                if div_amt > 0:
                    received = portfolio.receive_dividend(sym, div_amt, dt.date(), cfg.reinvest_dividends)
                    day_div += received

            if day_div > 0:
                div_income_by_day[dt] = day_div

            # 리밸런싱
            if dt in rebalance_dates or i == 0:
                current_holdings = self._select_holdings(
                    strategy, universe, prices, dt_str, cfg.max_positions
                )
                if current_holdings and prices:
                    portfolio.rebalance_to_equal_weight(current_holdings, prices, dt.date())

            total_val = portfolio.get_value(prices)
            daily_values[dt] = total_val

        # 결과 정리
        values_series = pd.Series(daily_values).sort_index()
        div_series = pd.Series(div_income_by_day).sort_index() if div_income_by_day else pd.Series(dtype=float)

        from backtest.metrics import compute_drawdown_series
        drawdown = compute_drawdown_series(values_series)

        metrics = compute_metrics(
            daily_values=values_series,
            initial_capital=cfg.initial_capital,
            dividend_events=portfolio.dividend_events,
            trades=portfolio.trades,
        )

        trades_df = pd.DataFrame([
            {"date": t.date, "symbol": t.symbol, "action": t.action,
             "shares": t.shares, "price": t.price, "amount": t.amount}
            for t in portfolio.trades
        ])

        divs_df = pd.DataFrame([
            {"date": e.date, "symbol": e.symbol, "shares": e.shares,
             "per_share": e.amount_per_share, "total": e.total_amount}
            for e in portfolio.dividend_events
        ])

        return BacktestResult(
            daily_values=values_series,
            drawdown_series=drawdown,
            dividend_income_series=div_series,
            trades_df=trades_df,
            dividends_df=divs_df,
            metrics=metrics,
            strategy_name=strategy.name_kr,
            config=cfg,
            disclaimer=self.DISCLAIMER,
        )

    def _select_holdings(
        self, strategy, universe: list[str], prices: dict[str, float], dt_str: str, top_n: int
    ) -> list[str]:
        """리밸런싱 시점의 보유 종목 선정 (기존 가격 데이터 기반 간략 스크리닝)."""
        # 현재 가격 데이터가 있는 종목만
        available = [s for s in universe if s in prices]
        if not available:
            return []

        # 간략 히스토리컬 스크리닝: 배당수익률 기준 필터링
        scored = []
        for sym in available:
            yld = self._compute_historical_yield(sym, dt_str)
            if yld > 0:
                scored.append((sym, yld))

        if not scored:
            scored = [(sym, 1.0) for sym in available[:top_n]]

        scored.sort(key=lambda x: x[1], reverse=True)
        return [s[0] for s in scored[:top_n]]

    def _compute_historical_yield(self, symbol: str, as_of: str) -> float:
        """해당 날짜까지의 데이터만 사용하여 배당수익률 계산."""
        try:
            price_df = self.fetcher.get_price_history(symbol)
            if price_df.empty:
                return 0.0
            hist = price_df[price_df.index.astype(str) <= as_of]
            if hist.empty or "Dividends" not in hist.columns:
                return 0.0
            # 최근 12개월 배당 합계
            cutoff = hist.index[-1]
            year_ago = cutoff - pd.DateOffset(years=1)
            ann_div = float(hist.loc[hist.index >= year_ago, "Dividends"].sum())
            price = float(hist["Close"].iloc[-1])
            return ann_div / price if price > 0 else 0.0
        except Exception:
            return 0.0

    def _compute_rebalance_dates(self, all_dates: list, frequency: str) -> set:
        if frequency == "monthly":
            # 매월 첫 거래일
            result = {}
            for dt in all_dates:
                key = (dt.year, dt.month)
                if key not in result:
                    result[key] = dt
            return set(result.values())
        elif frequency == "quarterly":
            result = {}
            for dt in all_dates:
                quarter = (dt.month - 1) // 3
                key = (dt.year, quarter)
                if key not in result:
                    result[key] = dt
            return set(result.values())
        else:  # annual
            result = {}
            for dt in all_dates:
                if dt.year not in result:
                    result[dt.year] = dt
            return set(result.values())

    def _empty_result(self, strategy_name: str, cfg: BacktestConfig) -> BacktestResult:
        from backtest.metrics import _empty_metrics
        return BacktestResult(
            daily_values=pd.Series(dtype=float),
            drawdown_series=pd.Series(dtype=float),
            dividend_income_series=pd.Series(dtype=float),
            trades_df=pd.DataFrame(),
            dividends_df=pd.DataFrame(),
            metrics=_empty_metrics(),
            strategy_name=strategy_name,
            config=cfg,
            disclaimer=self.DISCLAIMER,
        )
