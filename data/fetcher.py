"""yfinance 래퍼 - 캐시 연동 + 속도 제한."""
import time
import warnings
from typing import Any

import pandas as pd
import yfinance as yf
from tqdm import tqdm

from config import BACKTEST_START, RATE_LIMIT_SECONDS
from data.cache import DataCache

warnings.filterwarnings("ignore", category=FutureWarning)


def _normalize_yield(yld: float) -> float:
    """yfinance는 dividendYield를 0.0791(소수) 또는 7.91(퍼센트) 형태로 혼용해서 반환한다.
    - 1.0 초과: 퍼센트 형태 (7.91 → 0.0791)
    - 0.20 초과 1.0 이하: 잘못된 퍼센트 형태 (0.42 → 0.0042)
      실제 배당주 수익률이 20%를 넘는 경우는 없으므로 무조건 100으로 나눔
    """
    if yld > 0.20:
        return yld / 100
    return yld


class YFinanceFetcher:
    def __init__(self, cache: DataCache | None = None, rate_limit: float = RATE_LIMIT_SECONDS):
        self._cache = cache or DataCache()
        self._rate = rate_limit
        self._last_call = 0.0

    # ── 속도 제한 ──────────────────────────────────────────

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._rate:
            time.sleep(self._rate - elapsed)
        self._last_call = time.monotonic()

    # ── 가격 히스토리 ──────────────────────────────────────

    def get_price_history(self, symbol: str, start: str = BACKTEST_START, end: str = "2026-03-29") -> pd.DataFrame:
        cached = self._cache.get_price_history(symbol)
        if cached is not None and not cached.empty:
            return cached

        self._wait()
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start, end=end, auto_adjust=True)
            if df.empty:
                return pd.DataFrame()
            df = self._validate_price_history(df, symbol)
            self._cache.put_price_history(symbol, df)
            return df
        except Exception as e:
            print(f"[WARN] 가격 히스토리 가져오기 실패: {symbol} - {e}")
            return pd.DataFrame()

    def _validate_price_history(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        df = df[df["Close"] > 0].copy()
        # 인덱스를 timezone-naive로 변환
        if hasattr(df.index, "tz") and df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        return df

    def get_dividends(self, symbol: str) -> pd.Series:
        df = self.get_price_history(symbol)
        if df.empty or "Dividends" not in df.columns:
            return pd.Series(dtype=float)
        divs = df["Dividends"]
        return divs[divs > 0]

    # ── Ticker Info ────────────────────────────────────────

    def get_ticker_info(self, symbol: str) -> dict:
        cached = self._cache.get_ticker_info(symbol)
        if cached is not None:
            return cached

        self._wait()
        try:
            info = yf.Ticker(symbol).info
            self._cache.put_ticker_info(symbol, info)
            return info
        except Exception as e:
            print(f"[WARN] 티커 정보 가져오기 실패: {symbol} - {e}")
            return {}

    # ── 재무제표 ───────────────────────────────────────────

    def get_financials(self, symbol: str) -> dict[str, pd.DataFrame]:
        result = {}
        type_map = {
            "income": "financials",
            "balance": "balance_sheet",
            "cashflow": "cashflow",
        }
        for key, attr in type_map.items():
            cached = self._cache.get_financials(symbol, key)
            if cached is not None and not cached.empty:
                result[key] = cached
                continue

            self._wait()
            try:
                ticker = yf.Ticker(symbol)
                df = getattr(ticker, attr)
                if df is not None and not df.empty:
                    # 날짜 컬럼 정규화
                    if hasattr(df.columns, "tz") and df.columns.tz is not None:
                        df.columns = df.columns.tz_localize(None)
                    self._cache.put_financials(symbol, key, df)
                    result[key] = df
                else:
                    result[key] = pd.DataFrame()
            except Exception as e:
                print(f"[WARN] 재무제표 가져오기 실패: {symbol}/{key} - {e}")
                result[key] = pd.DataFrame()

        return result

    # ── 옵션 체인 ──────────────────────────────────────────

    def get_options_chain(self, symbol: str, expiration: str | None = None) -> dict[str, pd.DataFrame]:
        cached = self._cache.get_options(symbol)
        if cached is not None:
            return cached

        self._wait()
        try:
            ticker = yf.Ticker(symbol)
            expirations = ticker.options
            if not expirations:
                return {}
            exp = expiration or expirations[0]
            chain = ticker.option_chain(exp)
            result = {"calls": chain.calls, "puts": chain.puts, "expiration": exp}
            self._cache.put_options(symbol, {"calls": chain.calls, "puts": chain.puts})
            return result
        except Exception as e:
            print(f"[WARN] 옵션 체인 가져오기 실패: {symbol} - {e}")
            return {}

    # ── 배치 로딩 ──────────────────────────────────────────

    def bulk_fetch(self, symbols: list[str], data_types: list[str] | None = None, desc: str = "") -> None:
        data_types = data_types or ["price", "info"]
        for sym in tqdm(symbols, desc=desc or "데이터 로딩"):
            if "price" in data_types:
                self.get_price_history(sym)
            if "info" in data_types:
                self.get_ticker_info(sym)
            if "financials" in data_types:
                self.get_financials(sym)

    # ── 유틸 ───────────────────────────────────────────────

    def get_current_price(self, symbol: str) -> float | None:
        info = self.get_ticker_info(symbol)
        return info.get("currentPrice") or info.get("regularMarketPrice")

    def get_market_cap(self, symbol: str) -> float:
        info = self.get_ticker_info(symbol)
        return info.get("marketCap") or 0.0

    def get_annual_dividend(self, symbol: str) -> float:
        divs = self.get_dividends(symbol)
        if divs.empty:
            return 0.0
        recent = divs[divs.index >= divs.index[-1] - pd.DateOffset(years=1)]
        return float(recent.sum())

    def get_dividend_yield(self, symbol: str) -> float:
        info = self.get_ticker_info(symbol)
        yld = info.get("dividendYield") or info.get("trailingAnnualDividendYield")
        if yld:
            return _normalize_yield(float(yld))
        # 직접 계산
        price = self.get_current_price(symbol)
        if not price:
            return 0.0
        ann_div = self.get_annual_dividend(symbol)
        return ann_div / price if price > 0 else 0.0
