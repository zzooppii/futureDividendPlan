"""나스닥 배당주 유니버스 관리.

yfinance 전체 나스닥 스캔은 너무 오래 걸리므로
알려진 배당주 목록을 정적으로 관리한다.
"""

# ── 월배당 ETF / 리츠 ──────────────────────────────────────
MONTHLY_DIVIDEND_ETFS = [
    "JEPI", "JEPQ", "O", "MAIN", "STAG", "AGNC", "NLY",
    "QYLD", "RYLD", "XYLD", "NUSI", "DIVO", "PFFD",
    "SLVO", "CLM", "CRF", "UTF", "UTG", "GOF",
    "HNDL", "IGLD", "SVOL",
]

# ── 나스닥 대형 배당주 ─────────────────────────────────────
NASDAQ_LARGE_CAP_DIVIDEND = [
    "AAPL", "MSFT", "CSCO", "INTC", "TXN", "AVGO",
    "QCOM", "ADI", "PAYX", "ADP", "KLAC", "LRCX",
    "MCHP", "SNPS", "CDNS",
]

# ── 배당 귀족 / 챔피언 (25년+ 연속 인상) ──────────────────
DIVIDEND_ARISTOCRATS = [
    "JNJ", "KO", "PG", "MMM", "ABT", "ADP", "BDX",
    "CL", "CAT", "CVX", "XOM", "GPC", "HRL", "ITW",
    "LOW", "MCD", "MKC", "NDSN", "PEP", "ROST", "SWK",
    "SYY", "T", "VFC", "WMT", "GWW", "EMR", "FRT",
    "ALB", "AOS", "CINF", "CTAS", "ESS",
]

# ── 배당성장 우량주 ────────────────────────────────────────
DIVIDEND_GROWTH_STOCKS = [
    "MSFT", "AAPL", "V", "MA", "UNH", "HD", "MCD",
    "NKE", "SBUX", "TGT", "COST", "AMGN", "GILD",
    "BIIB", "INTU", "ADBE", "AMAT", "MU",
]

# ── 고배당 인컴 주식 ───────────────────────────────────────
HIGH_YIELD_INCOME = [
    "MO", "PM", "BTI", "VZ", "T", "CVX", "XOM",
    "OKE", "WMB", "EPD", "PSX", "VLO",
    "IBM", "ABBV", "BMY", "PFE", "MRK",
    "SPG", "VICI", "AMT", "CCI", "DLR",
    "ARCC", "HTGC", "GBDC", "FSCO",
]

# ── 커버드콜 ETF (옵션 유동성 높음) ───────────────────────
COVERED_CALL_STOCKS = [
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA",
    "TSLA", "SPY", "QQQ", "AMD", "INTC", "BAC",
    "GS", "JPM", "MS", "C",
]

# ── 실버 연금형 (안정적, 저변동성, 4~6% 수익률) ────────────
SILVER_PENSION_STOCKS = [
    "JNJ", "PG", "KO", "PEP", "WMT", "MCD", "ABT",
    "VZ", "T", "ED", "SO", "DUK", "AEP", "D",
    "NEE", "ETR", "FE", "PPL", "WEC", "CMS",
    "O", "NNN", "ADC", "EPRT",
]


def get_full_universe() -> list[str]:
    """중복 없는 전체 배당주 유니버스."""
    all_tickers = (
        MONTHLY_DIVIDEND_ETFS
        + NASDAQ_LARGE_CAP_DIVIDEND
        + DIVIDEND_ARISTOCRATS
        + DIVIDEND_GROWTH_STOCKS
        + HIGH_YIELD_INCOME
        + COVERED_CALL_STOCKS
        + SILVER_PENSION_STOCKS
    )
    return list(dict.fromkeys(all_tickers))  # 순서 보존 중복 제거


def get_small_universe() -> list[str]:
    """개발/테스트용 소규모 유니버스 (50종목)."""
    return (
        MONTHLY_DIVIDEND_ETFS[:8]
        + NASDAQ_LARGE_CAP_DIVIDEND[:8]
        + DIVIDEND_ARISTOCRATS[:10]
        + HIGH_YIELD_INCOME[:12]
        + SILVER_PENSION_STOCKS[:12]
    )[:50]


def get_monthly_payers() -> list[str]:
    return MONTHLY_DIVIDEND_ETFS


def get_strategy_universe(strategy_name: str) -> list[str]:
    mapping = {
        "max_monthly": MONTHLY_DIVIDEND_ETFS + HIGH_YIELD_INCOME,
        "silver_pension": SILVER_PENSION_STOCKS + DIVIDEND_ARISTOCRATS,
        "dividend_growth": DIVIDEND_GROWTH_STOCKS + DIVIDEND_ARISTOCRATS,
        "quality_core": DIVIDEND_ARISTOCRATS + NASDAQ_LARGE_CAP_DIVIDEND + DIVIDEND_GROWTH_STOCKS,
        "covered_call": COVERED_CALL_STOCKS + HIGH_YIELD_INCOME,
    }
    tickers = mapping.get(strategy_name, get_full_universe())
    return list(dict.fromkeys(tickers))
