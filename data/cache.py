"""SQLite + Parquet 기반 캐시 레이어.

가격 히스토리: parquet 파일 (심볼별)
.info / 재무제표: SQLite JSON blob
"""
import json
import sqlite3
import time
from pathlib import Path

import pandas as pd

from config import CACHE_DB, CACHE_TTL_FINANCIALS, CACHE_TTL_INFO, CACHE_TTL_PRICE, DATA_DIR

_TTL_MAP = {
    "price": CACHE_TTL_PRICE,
    "info": CACHE_TTL_INFO,
    "income": CACHE_TTL_FINANCIALS,
    "balance": CACHE_TTL_FINANCIALS,
    "cashflow": CACHE_TTL_FINANCIALS,
    "options": 3600,  # 1시간
}

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS cache_meta (
    symbol      TEXT NOT NULL,
    data_type   TEXT NOT NULL,
    fetched_at  REAL NOT NULL,
    file_path   TEXT,
    json_data   TEXT,
    PRIMARY KEY (symbol, data_type)
)
"""


class DataCache:
    def __init__(self, db_path: Path = CACHE_DB):
        self._db = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(_CREATE_TABLE)

    # ── 내부 헬퍼 ────────────────────────────────────────

    def _is_fresh(self, symbol: str, data_type: str) -> bool:
        ttl = _TTL_MAP.get(data_type, CACHE_TTL_INFO)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT fetched_at FROM cache_meta WHERE symbol=? AND data_type=?",
                (symbol, data_type),
            ).fetchone()
        if row is None:
            return False
        return (time.time() - row["fetched_at"]) < ttl

    def _set_meta(
        self,
        symbol: str,
        data_type: str,
        file_path: str | None = None,
        json_data: str | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cache_meta (symbol, data_type, fetched_at, file_path, json_data)
                VALUES (?, ?, ?, ?, ?)
                """,
                (symbol, data_type, time.time(), file_path, json_data),
            )

    def _get_meta(self, symbol: str, data_type: str) -> sqlite3.Row | None:
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM cache_meta WHERE symbol=? AND data_type=?",
                (symbol, data_type),
            ).fetchone()

    # ── 가격 히스토리 (parquet) ────────────────────────────

    def _price_path(self, symbol: str) -> Path:
        return DATA_DIR / f"{symbol.replace('/', '_')}_price.parquet"

    def get_price_history(self, symbol: str) -> pd.DataFrame | None:
        if not self._is_fresh(symbol, "price"):
            return None
        path = self._price_path(symbol)
        if not path.exists():
            return None
        try:
            return pd.read_parquet(path)
        except Exception:
            return None

    def put_price_history(self, symbol: str, df: pd.DataFrame) -> None:
        path = self._price_path(symbol)
        df.to_parquet(path)
        self._set_meta(symbol, "price", file_path=str(path))

    # ── Ticker Info (JSON blob) ────────────────────────────

    def get_ticker_info(self, symbol: str) -> dict | None:
        if not self._is_fresh(symbol, "info"):
            return None
        row = self._get_meta(symbol, "info")
        if row is None or row["json_data"] is None:
            return None
        try:
            return json.loads(row["json_data"])
        except Exception:
            return None

    def put_ticker_info(self, symbol: str, info: dict) -> None:
        self._set_meta(symbol, "info", json_data=json.dumps(info, default=str))

    # ── 재무제표 (JSON blob) ────────────────────────────────

    def get_financials(self, symbol: str, stmt_type: str) -> pd.DataFrame | None:
        key = stmt_type  # "income" | "balance" | "cashflow"
        if not self._is_fresh(symbol, key):
            return None
        row = self._get_meta(symbol, key)
        if row is None or row["json_data"] is None:
            return None
        try:
            return pd.read_json(row["json_data"])
        except Exception:
            return None

    def put_financials(self, symbol: str, stmt_type: str, df: pd.DataFrame) -> None:
        self._set_meta(symbol, stmt_type, json_data=df.to_json())

    # ── 옵션 체인 (JSON blob) ──────────────────────────────

    def get_options(self, symbol: str) -> dict | None:
        if not self._is_fresh(symbol, "options"):
            return None
        row = self._get_meta(symbol, "options")
        if row is None or row["json_data"] is None:
            return None
        try:
            data = json.loads(row["json_data"])
            return {k: pd.read_json(v) for k, v in data.items()}
        except Exception:
            return None

    def put_options(self, symbol: str, chains: dict) -> None:
        serialized = {k: v.to_json() for k, v in chains.items()}
        self._set_meta(symbol, "options", json_data=json.dumps(serialized))

    # ── 캐시 통계 ──────────────────────────────────────────

    def stats(self) -> dict:
        with self._connect() as conn:
            rows = conn.execute("SELECT data_type, COUNT(*) as cnt FROM cache_meta GROUP BY data_type").fetchall()
        return {r["data_type"]: r["cnt"] for r in rows}
