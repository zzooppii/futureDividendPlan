"""데이터 초기 로딩 스크립트.

사용법:
    python setup_data.py              # 소규모 유니버스 (테스트용)
    python setup_data.py --full       # 전체 유니버스
    python setup_data.py --refresh    # 캐시 무시하고 재로딩
"""
import argparse
import sys

from data.cache import DataCache
from data.fetcher import YFinanceFetcher
from data.ticker_list import get_full_universe, get_small_universe


def main():
    parser = argparse.ArgumentParser(description="배당 투자 데이터 초기 로딩")
    parser.add_argument("--full", action="store_true", help="전체 유니버스 (~400종목)")
    parser.add_argument("--refresh", action="store_true", help="캐시 무시하고 재로딩")
    args = parser.parse_args()

    universe = get_full_universe() if args.full else get_small_universe()
    print(f"유니버스 크기: {len(universe)}종목")

    if args.refresh:
        import os
        from config import DATA_DIR
        for f in DATA_DIR.glob("*_price.parquet"):
            os.remove(f)
        from config import CACHE_DB
        if CACHE_DB.exists():
            os.remove(CACHE_DB)
        print("캐시 초기화 완료")

    cache = DataCache()
    fetcher = YFinanceFetcher(cache)

    print("\n[1/3] 가격 히스토리 + 배당 데이터 로딩...")
    fetcher.bulk_fetch(universe, data_types=["price"], desc="가격 히스토리")

    print("\n[2/3] 티커 정보 로딩...")
    fetcher.bulk_fetch(universe, data_types=["info"], desc="티커 정보")

    print("\n[3/3] 재무제표 로딩 (선택적)...")
    # 재무제표는 핵심 종목만 (ETF 제외)
    stock_universe = [s for s in universe if len(s) <= 5][:50]
    fetcher.bulk_fetch(stock_universe, data_types=["financials"], desc="재무제표")

    print("\n=== 로딩 완료 ===")
    stats = cache.stats()
    for k, v in stats.items():
        print(f"  {k}: {v}건 캐시됨")


if __name__ == "__main__":
    main()
