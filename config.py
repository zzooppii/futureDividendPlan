from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data" / "store"
CACHE_DB = DATA_DIR / "cache.sqlite"

DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── 캐시 TTL (초) ──────────────────────────────────────
CACHE_TTL_PRICE = 86400           # 1일 (가격 히스토리)
CACHE_TTL_INFO = 86400 * 7        # 1주 (.info 데이터)
CACHE_TTL_FINANCIALS = 86400 * 30 # 1개월 (재무제표)

# ── 백테스트 기간 ──────────────────────────────────────
BACKTEST_START = "2005-01-01"
BACKTEST_END = "2026-03-01"

# ── 스크리닝 기본 임계값 ────────────────────────────────
MIN_MARKET_CAP = 500_000_000      # $500M
MIN_AVG_VOLUME = 100_000
RISK_FREE_RATE = 0.04             # 4% (무위험 수익률)

# ── API 속도 제한 ───────────────────────────────────────
RATE_LIMIT_SECONDS = 0.3          # API 호출 간격

# ── 환율 (USD -> KRW 근사값, 실제는 동적으로 조회 가능) ──
USD_TO_KRW = 1350
