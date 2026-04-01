"""페이지 5: 배당 성장 시각화 + 지속가능성/함정 분석."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import pandas as pd
import streamlit as st


@st.cache_resource
def get_fetcher():
    from data.cache import DataCache
    from data.fetcher import YFinanceFetcher
    return YFinanceFetcher(DataCache())


st.title("🌱 배당 성장 & 지속가능성 분석")
st.markdown("종목의 배당 성장 이력과 지속가능성 점수를 분석합니다.")

fetcher = get_fetcher()

from dashboard.shared_state import portfolio_banner, symbol_selector_sidebar

portfolio_banner()

st.sidebar.header("⚙️ 설정")
symbols = symbol_selector_sidebar("growth")

if st.sidebar.button("🔍 분석 시작", type="primary") or symbols:
    tab1, tab2, tab3 = st.tabs(["📈 배당 성장 이력", "🏆 지속가능성 점수", "⚠️ 배당함정 탐지"])

    with tab1:
        st.subheader("배당 성장 추이")
        growth_data = {}

        with st.spinner("배당 데이터 분석 중..."):
            for sym in symbols:
                try:
                    divs = fetcher.get_dividends(sym)
                    if not divs.empty:
                        annual = divs.resample("YE").sum()
                        annual.index = annual.index.year
                        growth_data[sym] = annual
                except Exception:
                    pass

        if growth_data:
            from dashboard.components.charts import dividend_growth_line
            st.plotly_chart(
                dividend_growth_line(
                    {k: v for k, v in growth_data.items()},
                    title="연간 주당 배당금 추이"
                ),
                use_container_width=True
            )

            # CAGR 계산 테이블
            cagr_rows = []
            for sym, series in growth_data.items():
                if len(series) < 2:
                    continue
                vals = series.dropna()
                if vals.empty or vals.iloc[0] == 0:
                    continue

                # 5년, 10년 CAGR
                def calc_cagr(s, yrs):
                    if len(s) >= yrs and s.iloc[-yrs] > 0:
                        return (s.iloc[-1] / s.iloc[-yrs]) ** (1 / yrs) - 1
                    return None

                c5 = calc_cagr(vals, 5)
                c10 = calc_cagr(vals, 10)
                growth = (vals.iloc[-1] - vals.iloc[0]) / vals.iloc[0] if vals.iloc[0] > 0 else 0
                consecutive = 0
                for i in range(len(vals) - 1, 0, -1):
                    if vals.iloc[i] >= vals.iloc[i - 1] * 0.99:
                        consecutive += 1
                    else:
                        break

                cagr_rows.append({
                    "종목": sym,
                    "최근 배당 (연간)": f"${vals.iloc[-1]:.3f}",
                    "최저 배당 (연간)": f"${vals.min():.3f}",
                    "5년 CAGR": f"{c5:.1%}" if c5 is not None else "-",
                    "10년 CAGR": f"{c10:.1%}" if c10 is not None else "-",
                    "전체 성장률": f"{growth:.1%}",
                    "연속 증가 연수": f"{consecutive}년",
                })

            st.dataframe(pd.DataFrame(cagr_rows), use_container_width=True, hide_index=True)

    with tab2:
        st.subheader("배당 지속가능성 점수")

        from analysis.sustainability import compute_sustainability

        scores = []
        progress = st.progress(0)
        for i, sym in enumerate(symbols):
            try:
                score = compute_sustainability(sym, fetcher)
                scores.append(score)
            except Exception as e:
                pass
            progress.progress((i + 1) / len(symbols))
        progress.empty()

        if scores:
            # 점수 바차트
            import plotly.graph_objects as go

            score_df = pd.DataFrame([{
                "종목": s.symbol,
                "종합 점수": s.overall_score,
                "배당성향": s.payout_ratio_score,
                "FCF 커버리지": s.cf_coverage_score,
                "이익 안정성": s.earnings_stability,
                "배당 추세": s.dividend_trend_score,
                "등급": s.grade,
            } for s in scores]).sort_values("종합 점수", ascending=False)

            fig = go.Figure()
            components = ["배당성향", "FCF 커버리지", "이익 안정성", "배당 추세"]
            colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#9467bd"]

            for comp, color in zip(components, colors):
                fig.add_trace(go.Bar(
                    x=score_df["종목"], y=score_df[comp],
                    name=comp, marker_color=color,
                ))
            fig.update_layout(
                barmode="stack", title="배당 지속가능성 점수 분해",
                template="plotly_dark", height=400,
                yaxis=dict(range=[0, 100]),
            )
            st.plotly_chart(fig, use_container_width=True)

            # 등급 카드
            st.subheader("등급별 분류")
            for grade in ["A", "B", "C", "D", "F"]:
                grade_syms = [s.symbol for s in scores if s.grade == grade]
                if grade_syms:
                    color = {"A": "🟢", "B": "🔵", "C": "🟡", "D": "🟠", "F": "🔴"}[grade]
                    st.write(f"{color} **등급 {grade}**: {', '.join(grade_syms)}")

            # 상세 테이블
            st.dataframe(score_df, use_container_width=True, hide_index=True)

    with tab3:
        st.subheader("배당함정 탐지 분석")

        from analysis.yield_trap import detect_yield_trap

        traps = []
        progress2 = st.progress(0)
        for i, sym in enumerate(symbols):
            try:
                trap = detect_yield_trap(sym, fetcher)
                traps.append(trap)
            except Exception:
                pass
            progress2.progress((i + 1) / len(symbols))
        progress2.empty()

        if traps:
            # 위험 종목 먼저 표시
            high_risk = [t for t in traps if t.risk_level == "high"]
            med_risk = [t for t in traps if t.risk_level == "medium"]
            safe = [t for t in traps if t.risk_level == "low"]

            col1, col2, col3 = st.columns(3)
            with col1:
                st.error(f"🔴 고위험: {len(high_risk)}개 종목")
                for t in high_risk:
                    st.write(f"• **{t.symbol}** (점수: {t.trap_score})")
                    for w in t.warnings:
                        st.caption(f"  - {w}")
            with col2:
                st.warning(f"🟡 중위험: {len(med_risk)}개 종목")
                for t in med_risk:
                    st.write(f"• **{t.symbol}** (점수: {t.trap_score})")
                    for w in t.warnings:
                        st.caption(f"  - {w}")
            with col3:
                st.success(f"🟢 저위험: {len(safe)}개 종목")
                for t in safe:
                    st.write(f"• **{t.symbol}**")

            # 상세 테이블
            st.subheader("전체 배당함정 분석 결과")
            trap_rows = []
            for t in sorted(traps, key=lambda x: x.trap_score, reverse=True):
                m = t.metrics
                trap_rows.append({
                    "종목": t.symbol,
                    "위험도": {"high": "🔴 고위험", "medium": "🟡 중위험", "low": "🟢 저위험"}[t.risk_level],
                    "함정 점수": t.trap_score,
                    "배당수익률": f"{m.get('dividend_yield', 0):.2%}",
                    "배당성향": f"{m.get('payout_ratio', 0):.1%}" if m.get("payout_ratio") else "-",
                    "1년 주가변동": f"{m.get('price_drop_1yr', 0):.1%}" if "price_drop_1yr" in m else "-",
                    "FCF 적자": "⚠️" if m.get("fcf_negative") else "✅",
                    "경고 사항": " | ".join(t.warnings[:2]) if t.warnings else "없음",
                })
            st.dataframe(pd.DataFrame(trap_rows), use_container_width=True, hide_index=True)
