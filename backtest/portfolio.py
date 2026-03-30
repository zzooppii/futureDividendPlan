"""포트폴리오 상태 추적."""
from dataclasses import dataclass, field
from datetime import date


@dataclass
class Trade:
    date: date
    symbol: str
    action: str        # "buy" | "sell"
    shares: float
    price: float
    amount: float


@dataclass
class DividendEvent:
    date: date
    symbol: str
    shares: float
    amount_per_share: float
    total_amount: float


class Portfolio:
    def __init__(self, initial_capital: float):
        self.cash = initial_capital
        self.initial_capital = initial_capital
        self.positions: dict[str, float] = {}   # symbol -> shares
        self.trades: list[Trade] = []
        self.dividend_events: list[DividendEvent] = []
        self.daily_snapshots: list[dict] = []

    def buy(self, symbol: str, shares: float, price: float, trade_date: date) -> None:
        cost = shares * price
        if cost > self.cash:
            shares = self.cash / price
            cost = shares * price
        if shares <= 0:
            return
        self.cash -= cost
        self.positions[symbol] = self.positions.get(symbol, 0.0) + shares
        self.trades.append(Trade(trade_date, symbol, "buy", shares, price, cost))

    def sell(self, symbol: str, shares: float, price: float, trade_date: date) -> None:
        held = self.positions.get(symbol, 0.0)
        shares = min(shares, held)
        if shares <= 0:
            return
        proceeds = shares * price
        self.cash += proceeds
        self.positions[symbol] = held - shares
        if self.positions[symbol] < 1e-6:
            del self.positions[symbol]
        self.trades.append(Trade(trade_date, symbol, "sell", shares, price, proceeds))

    def receive_dividend(
        self, symbol: str, amount_per_share: float, trade_date: date, reinvest: bool = True
    ) -> float:
        shares = self.positions.get(symbol, 0.0)
        if shares <= 0 or amount_per_share <= 0:
            return 0.0
        total = shares * amount_per_share
        self.cash += total
        self.dividend_events.append(
            DividendEvent(trade_date, symbol, shares, amount_per_share, total)
        )
        return total

    def get_value(self, prices: dict[str, float]) -> float:
        equity = sum(
            shares * prices.get(sym, 0.0)
            for sym, shares in self.positions.items()
        )
        return self.cash + equity

    def rebalance_to_equal_weight(
        self, symbols: list[str], prices: dict[str, float], trade_date: date
    ) -> None:
        if not symbols:
            return
        total = self.get_value(prices)
        target_per = total / len(symbols)

        # 먼저 제거할 종목 매도
        for sym in list(self.positions.keys()):
            if sym not in symbols:
                price = prices.get(sym)
                if price and price > 0:
                    self.sell(sym, self.positions[sym], price, trade_date)

        # 목표 비중으로 조정
        for sym in symbols:
            price = prices.get(sym)
            if not price or price <= 0:
                continue
            current_val = self.positions.get(sym, 0.0) * price
            diff = target_per - current_val
            if abs(diff) < 10:
                continue
            if diff > 0:
                shares_to_buy = diff / price
                self.buy(sym, shares_to_buy, price, trade_date)
            else:
                shares_to_sell = abs(diff) / price
                self.sell(sym, shares_to_sell, price, trade_date)

    def snapshot(self, dt: date, prices: dict[str, float]) -> dict:
        snap = {
            "date": dt,
            "total_value": self.get_value(prices),
            "cash": self.cash,
            "positions": dict(self.positions),
        }
        self.daily_snapshots.append(snap)
        return snap

    @property
    def total_dividends_received(self) -> float:
        return sum(e.total_amount for e in self.dividend_events)
