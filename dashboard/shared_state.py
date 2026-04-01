"""페이지 간 포트폴리오 공유를 위한 session_state 유틸리티.

Page 0(내 투자 플래너)에서 추천된 포트폴리오를 저장하고,
다른 페이지에서 자동으로 불러올 수 있도록 한다.
"""
import streamlit as st

# ── session_state 키 상수 ────────────────────────────────────────
_SYMBOLS      = "shared_portfolio_symbols"
_WEIGHTS      = "shared_portfolio_weights"
_AMOUNT       = "shared_investment_amount"
_CURRENCY     = "shared_investment_currency"
_AVG_YIELD    = "shared_avg_yield"
_AVG_DIV_GR   = "shared_avg_div_growth"
_AVG_PRICE_GR = "shared_avg_price_growth"

# 세션에 포트폴리오가 없을 때 사용하는 기본 종목
DEFAULT_SYMBOLS = ["JEPI", "O", "JNJ", "PG", "KO", "MSFT", "VZ", "ABBV", "MAIN", "MCD"]


# ── 저장 / 불러오기 ──────────────────────────────────────────────

def save_portfolio(
    symbols: list[str],
    weights: dict[str, float],
    amount_usd: float,
    currency: str,
    avg_yield: float,
    avg_div_growth: float,
    avg_price_growth: float,
) -> None:
    """Page 0의 추천 결과를 session_state에 저장한다."""
    st.session_state[_SYMBOLS]      = symbols
    st.session_state[_WEIGHTS]      = weights
    st.session_state[_AMOUNT]       = amount_usd
    st.session_state[_CURRENCY]     = currency
    st.session_state[_AVG_YIELD]    = avg_yield
    st.session_state[_AVG_DIV_GR]   = avg_div_growth
    st.session_state[_AVG_PRICE_GR] = avg_price_growth


def has_portfolio() -> bool:
    return bool(st.session_state.get(_SYMBOLS))


def get_symbols() -> list[str]:
    return st.session_state.get(_SYMBOLS, DEFAULT_SYMBOLS)


def get_weights() -> dict[str, float]:
    return st.session_state.get(_WEIGHTS, {})


def get_amount_usd() -> float:
    return st.session_state.get(_AMOUNT, 100_000.0)


def get_currency() -> str:
    return st.session_state.get(_CURRENCY, "USD")


def get_avg_yield() -> float:
    return st.session_state.get(_AVG_YIELD, 0.05)


def get_avg_div_growth() -> float:
    return st.session_state.get(_AVG_DIV_GR, 0.05)


def get_avg_price_growth() -> float:
    return st.session_state.get(_AVG_PRICE_GR, 0.04)


# ── UI 컴포넌트 ──────────────────────────────────────────────────

def portfolio_banner() -> None:
    """포트폴리오가 로드된 경우 상단에 안내 배너를 표시한다."""
    if has_portfolio():
        syms = get_symbols()
        preview = ", ".join(syms[:6]) + ("..." if len(syms) > 6 else "")
        st.info(
            f"💼 **내 투자 플래너**에서 추천받은 **{len(syms)}개 종목** 포트폴리오가 자동으로 적용되었습니다.  \n"
            f"({preview})  \n"
            "아래 사이드바에서 종목을 수정할 수 있습니다.",
        )


def symbol_selector_sidebar(page_key: str, label: str = "분석할 종목") -> list[str]:
    """사이드바에 종목 선택 multiselect를 렌더링하고 선택된 종목 리스트를 반환한다.

    session_state의 포트폴리오를 기본값으로 사용, 사용자가 추가·제거 가능.
    page_key: 위젯 key 충돌 방지용 prefix (페이지마다 다른 값 사용)
    """
    from data.ticker_list import get_full_universe

    defaults = get_symbols()
    all_syms = list(dict.fromkeys(defaults + get_full_universe()))

    if has_portfolio():
        st.sidebar.caption("📌 내 투자 플래너 포트폴리오 적용 중")
    else:
        st.sidebar.caption("📋 기본 종목 (내 투자 플래너에서 설정 가능)")

    selected = st.sidebar.multiselect(
        label,
        options=all_syms,
        default=defaults,
        key=f"{page_key}_sym_sel",
    )
    return selected if selected else defaults
