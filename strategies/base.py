"""전략 추상 기반 클래스."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ScreenResult:
    symbol: str
    score: float                   # 0~100 종합 점수
    metrics: dict = field(default_factory=dict)
    pass_fail: dict = field(default_factory=dict)
    name: str = ""


class StrategyBase(ABC):
    name: str = ""
    description: str = ""
    name_kr: str = ""

    @abstractmethod
    def screen(self, universe: list[str], fetcher) -> list[str]:
        """유니버스에서 기준을 통과하는 종목 목록 반환."""

    @abstractmethod
    def score(self, symbols: list[str], fetcher) -> list[ScreenResult]:
        """통과 종목을 점수 순으로 정렬하여 반환."""

    @abstractmethod
    def get_criteria(self) -> dict[str, str]:
        """스크리닝 기준 설명 반환."""

    def select_portfolio(self, universe: list[str], fetcher, top_n: int = 20) -> list[ScreenResult]:
        """screen -> score -> 상위 N개 반환."""
        passed = self.screen(universe, fetcher)
        if not passed:
            return []
        ranked = self.score(passed, fetcher)
        return ranked[:top_n]

    def _safe_get(self, info: dict, *keys, default=0.0):
        for k in keys:
            v = info.get(k)
            if v is not None:
                try:
                    return float(v)
                except (TypeError, ValueError):
                    pass
        return default
