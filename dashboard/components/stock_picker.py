"""종목 브라우징 + 선택 컴포넌트.

카테고리별 탭으로 종목을 탐색하고, 배당수익률·베타·배당성향 등을
비교한 뒤 시뮬레이션에 사용할 종목을 선택한다.
"""
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import streamlit as st

from data.ticker_list import (
    MONTHLY_DIVIDEND_ETFS,
    NASDAQ_LARGE_CAP_DIVIDEND,
    DIVIDEND_ARISTOCRATS,
    DIVIDEND_GROWTH_STOCKS,
    HIGH_YIELD_INCOME,
    COVERED_CALL_STOCKS,
    SILVER_PENSION_STOCKS,
)

# ── 카테고리 정의 (탭 라벨 → 티커 리스트, 추천 정렬 기준) ─────────────
# sort_by: "yield" | "safety" | "size" | "balanced"
CATEGORIES: dict[str, dict] = {
    "📅 월배당 ETF":   {"tickers": MONTHLY_DIVIDEND_ETFS,       "sort": "yield"},
    "🏢 나스닥 대형주": {"tickers": NASDAQ_LARGE_CAP_DIVIDEND,   "sort": "balanced"},
    "👑 배당 귀족":     {"tickers": DIVIDEND_ARISTOCRATS,        "sort": "safety"},
    "📈 배당 성장":     {"tickers": DIVIDEND_GROWTH_STOCKS,      "sort": "safety"},
    "💰 고배당 인컴":   {"tickers": HIGH_YIELD_INCOME,           "sort": "yield"},
    "📞 커버드콜":      {"tickers": COVERED_CALL_STOCKS,         "sort": "size"},
    "🏦 실버 연금":     {"tickers": SILVER_PENSION_STOCKS,       "sort": "safety"},
}

# ── 전략 프리셋 ───────────────────────────────────────────────────
PRESETS: dict[str, list[str]] = {
    "직접 선택":              [],
    "월배당 최대화 (8종목)":   ["JEPI", "JEPQ", "O", "MAIN", "STAG", "QYLD", "AGNC", "NLY"],
    "실버 연금형 (8종목)":     ["JNJ", "KO", "PG", "PEP", "WMT", "VZ", "ABT", "MCD"],
    "배당 성장 (8종목)":       ["MSFT", "AAPL", "V", "MA", "HD", "UNH", "NKE", "COST"],
    "고배당 인컴 (8종목)":     ["MO", "PM", "ABBV", "VZ", "IBM", "ARCC", "BMY", "T"],
}

# 카테고리별 추천 기준 설명
SORT_DESC: dict[str, str] = {
    "yield":    "높은 배당수익률 순",
    "safety":   "배당 안정성 (낮은 배당성향 + 대형주) 순",
    "size":     "시총/유동성 (대형주) 순",
    "balanced": "종합 점수 (수익률 + 안정성 + 규모) 순",
}


def _normalize_yield(yld: float) -> float:
    return yld / 100 if yld > 0.20 else yld


@st.cache_data(ttl=86400 * 30, show_spinner=False)  # 번역 결과 30일 캐시
def _translate_to_korean(text: str) -> str:
    """영문 기업 소개를 한국어로 번역 (Google 번역, 무료)."""
    try:
        from deep_translator import GoogleTranslator
        # 2000자 초과 시 분할 번역
        chunk_size = 1500
        if len(text) <= chunk_size:
            return GoogleTranslator(source="en", target="ko").translate(text)
        # 문장 단위로 분할
        parts = []
        current = ""
        for sentence in text.replace(". ", ".|").split("|"):
            if len(current) + len(sentence) < chunk_size:
                current += sentence + " "
            else:
                if current:
                    parts.append(GoogleTranslator(source="en", target="ko").translate(current.strip()))
                current = sentence + " "
        if current.strip():
            parts.append(GoogleTranslator(source="en", target="ko").translate(current.strip()))
        return " ".join(parts)
    except Exception:
        return "번역을 불러올 수 없습니다. 영문 원본 탭을 참고하세요."


def _compute_rec_score(yld: float, payout: float, size_b: float, style: str) -> float:
    """0~100점 추천 점수 계산. style에 따라 각 항목 가중치가 달라진다."""
    # 수익률 점수 (0~100): 10% = 100점 상한
    yield_pt = min(yld * 1000, 100)

    # 안정성 점수 (0~100): 배당성향 낮을수록 높음
    if payout <= 0:
        safety_pt = 50
    elif payout <= 0.50:
        safety_pt = 100
    elif payout <= 0.70:
        safety_pt = 75
    elif payout <= 0.90:
        safety_pt = 40
    elif payout <= 1.0:
        safety_pt = 15
    else:
        safety_pt = 0  # 100% 초과 → 위험

    # 규모 점수 (0~100): 로그 스케일
    size_pt = min(math.log10(size_b + 1) * 30, 100) if size_b > 0 else 20

    weights = {
        "yield":    (0.70, 0.20, 0.10),
        "safety":   (0.20, 0.60, 0.20),
        "size":     (0.15, 0.25, 0.60),
        "balanced": (0.40, 0.35, 0.25),
    }
    yw, sw, mw = weights.get(style, weights["balanced"])
    return round(yield_pt * yw + safety_pt * sw + size_pt * mw, 1)


def _score_to_stars(score: float) -> str:
    if score >= 80: return "⭐⭐⭐⭐⭐"
    if score >= 65: return "⭐⭐⭐⭐"
    if score >= 50: return "⭐⭐⭐"
    if score >= 35: return "⭐⭐"
    return "⭐"


@st.cache_data(ttl=3600, show_spinner="종목 정보 로딩 중...")
def _load_category_data(_fetcher, category_name: str, tickers: tuple, sort_style: str) -> pd.DataFrame:
    rows = []
    for sym in tickers:
        try:
            info = _fetcher.get_ticker_info(sym)
            yld = info.get("dividendYield") or info.get("trailingAnnualDividendYield") or 0.0
            yld = _normalize_yield(float(yld))

            payout = float(info.get("payoutRatio") or 0.0)
            if payout > 2.0:
                payout = payout / 100

            quote_type = info.get("quoteType", "")
            is_etf = quote_type in ("ETF", "MUTUALFUND") or info.get("fundFamily") is not None
            sector = info.get("sector") or ("ETF" if is_etf else "-")

            market_size = info.get("marketCap") or info.get("totalAssets") or 0
            size_b = round(market_size / 1e9, 1)
            size_label = "AUM" if (not info.get("marketCap") and info.get("totalAssets")) else "시총"

            beta_raw = info.get("beta") or info.get("beta3Year")
            beta = round(float(beta_raw), 2) if beta_raw else None

            score = _compute_rec_score(yld, payout, size_b, sort_style)

            rows.append({
                "_score":       score,
                "추천":         _score_to_stars(score),
                "종목":         sym,
                "종목명":       (info.get("shortName") or info.get("longName") or sym)[:28],
                "배당수익률":   yld,
                "섹터":         sector,
                "베타 ℹ️":      beta,
                "배당성향":     payout,
                f"규모({size_label})": size_b,
            })
        except Exception:
            rows.append({
                "_score": 0, "추천": "⭐",
                "종목": sym, "종목명": sym, "배당수익률": 0.0,
                "섹터": "-", "베타 ℹ️": None, "배당성향": 0.0, "규모(시총)": 0.0,
            })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("_score", ascending=False).reset_index(drop=True)
        df = df.drop(columns=["_score"])
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def _load_stock_detail(_fetcher, symbol: str) -> dict:
    """종목 상세 정보 로드."""
    try:
        info = _fetcher.get_ticker_info(symbol)
        yld = info.get("dividendYield") or info.get("trailingAnnualDividendYield") or 0.0
        yld = _normalize_yield(float(yld))
        payout = float(info.get("payoutRatio") or 0.0)
        if payout > 2.0:
            payout = payout / 100
        return {
            "name":          info.get("longName") or info.get("shortName") or symbol,
            "sector":        info.get("sector") or info.get("category") or "-",
            "industry":      info.get("industry") or "-",
            "description":   info.get("longBusinessSummary") or "",
            "price":         info.get("currentPrice") or info.get("regularMarketPrice") or 0,
            "yield":         yld,
            "div_rate":      info.get("dividendRate") or info.get("trailingAnnualDividendRate") or 0,
            "payout":        payout,
            "beta":          info.get("beta"),
            "pe":            info.get("trailingPE"),
            "roe":           info.get("returnOnEquity"),
            "debt_equity":   info.get("debtToEquity"),
            "52w_high":      info.get("fiftyTwoWeekHigh"),
            "52w_low":       info.get("fiftyTwoWeekLow"),
            "market_cap":    info.get("marketCap") or info.get("totalAssets") or 0,
            "ex_div_date":   info.get("exDividendDate"),
            "5yr_avg_yield": info.get("fiveYearAvgDividendYield"),
        }
    except Exception:
        return {"name": symbol, "description": "정보를 불러올 수 없습니다."}


def _render_stock_detail(fetcher, symbol: str) -> None:
    """선택된 종목의 상세 정보 패널을 렌더링한다."""
    d = _load_stock_detail(fetcher, symbol)

    st.markdown(f"### 🔍 {symbol} — {d['name']}")
    if d.get("sector") and d["sector"] != "-":
        st.caption(f"섹터: {d['sector']}  |  업종: {d.get('industry', '-')}")

    # ── 핵심 지표 카드 ─────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    price = d.get("price") or 0
    with c1:
        st.metric("현재 주가", f"${price:,.2f}" if price else "-")
    with c2:
        yld = d.get("yield") or 0
        st.metric("배당수익률", f"{yld:.2%}" if yld else "-")
    with c3:
        div_rate = d.get("div_rate") or 0
        st.metric("연간 배당금(주당)", f"${div_rate:.2f}" if div_rate else "-")
    with c4:
        payout = d.get("payout") or 0
        payout_label = f"{payout:.1%}" if payout else "-"
        if payout > 1.0:
            payout_label = f"⚠️ {payout_label}"
        st.metric("배당성향", payout_label)

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        beta = d.get("beta")
        st.metric("베타", f"{beta:.2f}" if beta else "-",
                  help="1.0=시장 동일 변동성")
    with c6:
        cap = d.get("market_cap") or 0
        st.metric("시총/AUM", f"${cap/1e9:.1f}B" if cap else "-")
    with c7:
        high = d.get("52w_high")
        low  = d.get("52w_low")
        if high and low:
            st.metric("52주 범위", f"${low:.1f} ~ ${high:.1f}")
        else:
            st.metric("52주 범위", "-")
    with c8:
        avg5 = d.get("5yr_avg_yield")
        st.metric("5년 평균 수익률", f"{avg5:.2%}" if avg5 else "-")

    # ── 재무 지표 ──────────────────────────────────────────────
    fa, fb, fc = st.columns(3)
    with fa:
        pe = d.get("pe")
        st.metric("PER (주가수익비율)", f"{pe:.1f}배" if pe else "-",
                  help="낮을수록 저평가. 업종 평균 대비 비교 필요")
    with fb:
        roe = d.get("roe")
        st.metric("ROE (자기자본수익률)", f"{roe*100:.1f}%" if roe else "-",
                  help="15% 이상이면 우수한 수익성")
    with fc:
        de = d.get("debt_equity")
        st.metric("부채비율 (D/E)", f"{de:.1f}%" if de else "-",
                  help="낮을수록 재무 건전. 200% 초과 시 주의")

    # ── 기업 소개 ──────────────────────────────────────────────
    desc = d.get("description", "")
    if desc:
        short_desc = desc[:1000] + ("..." if len(desc) > 1000 else "")
        with st.expander("📄 기업/펀드 소개", expanded=True):
            tab_ko, tab_en = st.tabs(["🇰🇷 한국어", "🇺🇸 영문 원본"])
            with tab_ko:
                ko_text = _translate_to_korean(short_desc)
                st.write(ko_text)
            with tab_en:
                st.write(short_desc)

    # ── 간단 평가 ──────────────────────────────────────────────
    pros, cons = [], []
    yld = d.get("yield") or 0
    payout = d.get("payout") or 0
    beta = d.get("beta") or 1.0
    cap = (d.get("market_cap") or 0) / 1e9

    if yld >= 0.05:  pros.append(f"높은 배당수익률 ({yld:.1%})")
    elif yld > 0:    pros.append(f"배당 지급 ({yld:.1%})")
    if payout > 0 and payout <= 0.6:  pros.append("안정적 배당성향 (60% 이하)")
    if beta and beta < 0.8:           pros.append(f"낮은 변동성 (β={beta:.2f})")
    if cap >= 100:                    pros.append(f"초대형주 (시총 ${cap:.0f}B)")
    elif cap >= 10:                   pros.append(f"대형주 (시총 ${cap:.0f}B)")

    if payout > 1.0:   cons.append(f"⚠️ 배당성향 100% 초과 ({payout:.0%}) — 배당 삭감 위험")
    elif payout > 0.85: cons.append(f"높은 배당성향 ({payout:.0%}) — 여유 없음")
    if beta and beta > 1.3: cons.append(f"높은 변동성 (β={beta:.2f})")
    if yld < 0.01:     cons.append("배당수익률 1% 미만 — 현금흐름 적음")

    if pros or cons:
        pa, pb = st.columns(2)
        with pa:
            if pros:
                st.success("**장점**\n" + "\n".join(f"• {p}" for p in pros))
        with pb:
            if cons:
                st.error("**단점 / 주의**\n" + "\n".join(f"• {c}" for c in cons))


def _format_display_df(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["배당수익률"] = d["배당수익률"].map(lambda x: f"{x:.2%}")

    def fmt_payout(x):
        if x <= 0: return "-"
        label = f"{x:.1%}"
        return f"⚠️ {label}" if x > 1.0 else label
    d["배당성향"] = d["배당성향"].map(fmt_payout)

    for col in d.columns:
        if col.startswith("규모"):
            d[col] = d[col].map(lambda x: f"${x:.1f}B" if x and x > 0 else "-")

    beta_col = "베타 ℹ️"
    if beta_col in d.columns:
        d[beta_col] = d[beta_col].map(lambda x: f"{x:.2f}" if x is not None else "-")

    return d


def stock_picker(fetcher) -> list[str]:
    """종목 브라우저 UI를 렌더링하고 선택된 티커 리스트를 반환한다."""
    if "selected_tickers" not in st.session_state:
        st.session_state["selected_tickers"] = ["JEPI", "O", "JNJ", "PG", "KO"]

    # ── 전략 프리셋 ──────────────────────────────────────────────
    with st.expander("⚡ 전략 프리셋으로 빠르게 선택", expanded=False):
        pc1, pc2 = st.columns([3, 1])
        with pc1:
            preset = st.selectbox(
                "프리셋", options=list(PRESETS.keys()),
                key="preset_selector", label_visibility="collapsed",
            )
        with pc2:
            if st.button("적용", key="btn_preset", use_container_width=True):
                if PRESETS[preset]:
                    st.session_state["selected_tickers"] = list(PRESETS[preset])
                    st.rerun()

    # ── 카테고리 탭 ─────────────────────────────────────────────
    st.markdown("#### 📋 카테고리별 종목 탐색")
    st.caption("종목을 선택 후 **추가 ➕** 버튼을 눌러 시뮬레이션에 포함하세요.")

    tabs = st.tabs(list(CATEGORIES.keys()))

    for tab, (cat_name, cat_cfg) in zip(tabs, CATEGORIES.items()):
        cat_tickers = cat_cfg["tickers"]
        sort_style  = cat_cfg["sort"]

        with tab:
            df = _load_category_data(fetcher, cat_name, tuple(cat_tickers), sort_style)

            if df.empty:
                st.warning("데이터를 불러올 수 없습니다.")
                continue

            # 정렬 기준 안내
            st.caption(f"📊 추천 순서 기준: **{SORT_DESC[sort_style]}**")

            # 종목 정보 테이블
            st.dataframe(
                _format_display_df(df),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "추천":       st.column_config.TextColumn("추천", width="small"),
                    "배당수익률": st.column_config.TextColumn("배당수익률", width="small"),
                    "베타 ℹ️":    st.column_config.TextColumn(
                        "베타 ℹ️", width="small",
                        help="시장 대비 변동성\n• 1.0 = 시장과 동일\n• 0.5 = 절반 변동\n• 1.5 = 50% 더 변동\nETF는 미제공('-') 경우 있음",
                    ),
                    "배당성향":   st.column_config.TextColumn(
                        "배당성향", width="small",
                        help="순이익 대비 배당 비율\n• 60% 이하: 안정\n• 80% 초과: 주의\n• ⚠️ 100% 초과: 자본 잠식 위험",
                    ),
                },
            )

            high_payout = df[df["배당성향"] > 1.0]["종목"].tolist()
            if high_payout:
                st.warning(
                    f"⚠️ **배당성향 100% 초과**: {', '.join(high_payout)} — "
                    "순이익보다 더 많이 배당 지급 중. 배당 삭감 위험이 있습니다."
                )

            # ── 종목 상세 보기 ──────────────────────────────────
            detail_options = ["선택하세요..."] + [
                f"{row['종목']} — {row['종목명']}" for _, row in df.iterrows()
            ]
            sym_map = {f"{row['종목']} — {row['종목명']}": row["종목"] for _, row in df.iterrows()}

            selected_detail = st.selectbox(
                "🔍 종목 상세 보기",
                options=detail_options,
                key=f"detail_{cat_name}",
            )
            if selected_detail != "선택하세요...":
                sym = sym_map[selected_detail]
                with st.container(border=True):
                    _render_stock_detail(fetcher, sym)

            st.divider()

            # ── 종목 선택 → 시뮬레이션 추가 ────────────────────
            options: list[str] = []
            label_to_sym: dict[str, str] = {}
            for _, row in df.iterrows():
                label = f"{row['추천']} {row['종목']} ({row['배당수익률']:.2%}) — {row['종목명']}"
                options.append(label)
                label_to_sym[label] = row["종목"]

            mc1, mc2 = st.columns([4, 1])
            with mc1:
                picked_labels = st.multiselect(
                    "종목 선택", options=options,
                    key=f"ms_{cat_name}",
                    placeholder="종목을 선택하세요...",
                    label_visibility="collapsed",
                )
            with mc2:
                if st.button("추가 ➕", key=f"btn_{cat_name}", use_container_width=True):
                    new_syms = [label_to_sym[lbl] for lbl in picked_labels]
                    merged = list(dict.fromkeys(
                        st.session_state["selected_tickers"] + new_syms
                    ))
                    st.session_state["selected_tickers"] = merged
                    st.rerun()

    # ── 수동 입력 폴백 ───────────────────────────────────────────
    with st.expander("✏️ 직접 입력 (고급 사용자)", expanded=False):
        fc1, fc2 = st.columns([4, 1])
        with fc1:
            manual_input = st.text_input(
                "종목 코드", placeholder="NVDA,AMD,GOOGL",
                key="manual_sym", label_visibility="collapsed",
            )
        with fc2:
            if st.button("추가", key="btn_manual", use_container_width=True):
                new_syms = [s.strip().upper() for s in manual_input.split(",") if s.strip()]
                if new_syms:
                    merged = list(dict.fromkeys(
                        st.session_state["selected_tickers"] + new_syms
                    ))
                    st.session_state["selected_tickers"] = merged
                    st.rerun()

    # ── 사이드바: 선택 종목 관리 ─────────────────────────────────
    st.sidebar.divider()
    n = len(st.session_state["selected_tickers"])
    st.sidebar.subheader(f"📌 선택된 종목 ({n}개)")

    if st.session_state["selected_tickers"]:
        kept = st.sidebar.multiselect(
            "종목 관리 (X로 제거)",
            options=st.session_state["selected_tickers"],
            default=st.session_state["selected_tickers"],
            key="sidebar_sel",
            label_visibility="collapsed",
        )
        if set(kept) != set(st.session_state["selected_tickers"]):
            st.session_state["selected_tickers"] = kept
            st.rerun()
        if st.sidebar.button("🗑️ 전체 초기화", use_container_width=True, key="btn_clear_all"):
            st.session_state["selected_tickers"] = []
            st.rerun()
    else:
        st.sidebar.info("위에서 종목을 선택하세요.")

    return list(st.session_state["selected_tickers"])
