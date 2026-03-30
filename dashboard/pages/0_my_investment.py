"""페이지 0: 내 투자금액 기반 맞춤 전략 추천 + 시뮬레이션."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# ── 전략 추천 로직 ───────────────────────────────────────────────
def recommend_strategies(amount_usd: float, goal: str, horizon: int, risk: str) -> list[dict]:
    """투자 프로필에 따라 전략 조합과 비중을 추천한다."""
    strategies = {
        # price_growth: 주가 자체 성장률 (배당과 별개)
        # 커버드콜/고배당 ETF는 옵션으로 상승분을 팔기 때문에 주가 성장이 거의 없음
        "월배당 최대화": {"yield": 0.065, "growth": 0.02, "price_growth": 0.015, "volatility": "중",  "risk_score": 3},
        "실버 연금 배당": {"yield": 0.050, "growth": 0.03, "price_growth": 0.030, "volatility": "저",  "risk_score": 1},
        "장기 배당 성장": {"yield": 0.025, "growth": 0.10, "price_growth": 0.080, "volatility": "중",  "risk_score": 2},
        "퀄리티 배당 코어":{"yield": 0.035, "growth": 0.07, "price_growth": 0.065, "volatility": "저중","risk_score": 2},
        "커버드콜 배당":  {"yield": 0.090, "growth": 0.01, "price_growth": 0.010, "volatility": "중고","risk_score": 4},
    }

    risk_map = {"매우 보수적": 1, "보수적": 2, "중립": 3, "적극적": 4, "매우 적극적": 5}
    risk_score = risk_map.get(risk, 3)

    # 금액별 기본 전략 조합
    if amount_usd < 10_000:
        base = {"월배당 최대화": 0.60, "실버 연금 배당": 0.40}
    elif amount_usd < 50_000:
        base = {"월배당 최대화": 0.40, "실버 연금 배당": 0.35, "퀄리티 배당 코어": 0.25}
    elif amount_usd < 100_000:
        base = {"월배당 최대화": 0.30, "실버 연금 배당": 0.25,
                "장기 배당 성장": 0.25, "퀄리티 배당 코어": 0.20}
    else:
        base = {"월배당 최대화": 0.20, "실버 연금 배당": 0.20,
                "장기 배당 성장": 0.20, "퀄리티 배당 코어": 0.20, "커버드콜 배당": 0.20}

    # 목표 조정
    if goal == "월수입 극대화":
        for k in base:
            if k == "월배당 최대화":
                base[k] *= 1.5
            elif k == "커버드콜 배당":
                base[k] *= 1.3
    elif goal == "안정적 노후 대비":
        for k in base:
            if k == "실버 연금 배당":
                base[k] *= 1.5
    elif goal == "배당 성장 + 자산 증식":
        for k in base:
            if k in ("장기 배당 성장", "퀄리티 배당 코어"):
                base[k] *= 1.5

    # ── 위험 성향 조정 ──────────────────────────────────────────
    # 보수적 → 안정형 전략 비중 UP, 고위험 전략 비중 DOWN
    # 적극적 → 성장형/고배당 전략 비중 UP, 안정형 비중 DOWN
    safe_strategies = {"실버 연금 배당", "퀄리티 배당 코어"}
    risky_strategies = {"커버드콜 배당", "장기 배당 성장"}

    if risk_score == 1:   # 매우 보수적
        for k in base:
            if k in safe_strategies:   base[k] *= 1.6
            elif k in risky_strategies: base[k] *= 0.4
            elif k == "월배당 최대화":  base[k] *= 0.7
    elif risk_score == 2:  # 보수적
        for k in base:
            if k in safe_strategies:   base[k] *= 1.3
            elif k in risky_strategies: base[k] *= 0.7
    elif risk_score == 4:  # 적극적
        for k in base:
            if k in risky_strategies:  base[k] *= 1.4
            elif k in safe_strategies:  base[k] *= 0.75
    elif risk_score == 5:  # 매우 적극적
        for k in base:
            if k in risky_strategies:  base[k] *= 1.8
            elif k in safe_strategies:  base[k] *= 0.5
            elif k == "월배당 최대화":  base[k] *= 1.2
    # risk_score == 3 (중립): 조정 없음

    # 정규화
    total = sum(base.values())
    base = {k: v / total for k, v in base.items()}

    result = []
    for name, weight in base.items():
        info = strategies[name]
        result.append({
            "전략": name,
            "비중": weight,
            "예상 배당수익률": info["yield"],
            "배당 성장률": info["growth"],
            "주가 성장률": info["price_growth"],
            "변동성": info["volatility"],
            "투자금": amount_usd * weight,
        })

    return sorted(result, key=lambda x: x["비중"], reverse=True)


def simulate_growth(amount_usd: float, recommendations: list[dict], years: int) -> tuple:
    """배당 재투자 vs 배당 수령 시뮬레이션.

    전략별로 주가 성장률이 다름:
    - 고배당(커버드콜 ETF): 주가 성장 거의 없음 → 총수익 = 배당 수입 위주
    - 배당 성장(성장주): 주가 성장 높음 → 총수익 = 주가 상승 + 배당
    """
    avg_yield = sum(r["비중"] * r["예상 배당수익률"] for r in recommendations)
    avg_div_growth = sum(r["비중"] * r["배당 성장률"] for r in recommendations)
    # ★ 전략별 주가 성장률을 가중평균 (고정 4% 아님)
    avg_price_growth = sum(r["비중"] * r["주가 성장률"] for r in recommendations)

    reinvest_values = [amount_usd]
    no_reinvest_values = [amount_usd]
    annual_dividends_reinvest = []
    annual_dividends_no_reinvest = []
    current_yield = avg_yield

    for y in range(1, years + 1):
        # 재투자: 배당을 다시 원금에 합산
        div_reinvest = reinvest_values[-1] * current_yield
        annual_dividends_reinvest.append(div_reinvest)
        reinvest_values.append(reinvest_values[-1] * (1 + avg_price_growth) + div_reinvest)

        # 미재투자: 배당은 수령, 원금만 주가 성장
        div_no_reinvest = no_reinvest_values[-1] * current_yield
        annual_dividends_no_reinvest.append(div_no_reinvest)
        no_reinvest_values.append(no_reinvest_values[-1] * (1 + avg_price_growth))

        # 배당 성장률 반영
        # 주가도 오르기 때문에 수익률은 div_growth - price_growth 만큼만 변함
        # yield(t) = yield(0) × (1+div_growth)^t / (1+price_growth)^t
        price_growth_adj = 1 + avg_price_growth if avg_price_growth > 0 else 1.0
        current_yield = min(current_yield * (1 + avg_div_growth) / price_growth_adj, 0.15)

    return (
        list(range(years + 1)),
        reinvest_values,
        no_reinvest_values,
        annual_dividends_reinvest,
        annual_dividends_no_reinvest,
        avg_yield,
        avg_price_growth,
    )


def past_investment_simulation(amount_usd: float, years_ago: int, avg_yield: float,
                               avg_growth: float, avg_price_growth: float) -> dict:
    """X년 전에 투자했다면 현재 어떻게 됐을지 계산."""
    total_div = 0.0
    portfolio = amount_usd
    current_yield = avg_yield

    for y in range(years_ago):
        annual_div = portfolio * current_yield
        total_div += annual_div
        portfolio = portfolio * (1 + avg_price_growth) + annual_div
        current_yield = min(current_yield * (1 + avg_growth), 0.20)

    return {
        "initial": amount_usd,
        "current_value": portfolio,
        "total_dividends": total_div,
        "total_return": (portfolio - amount_usd + total_div) / amount_usd,
        "years": years_ago,
    }


# ── 메인 UI ──────────────────────────────────────────────────────
st.title("💰 나의 배당 투자 플래너")
st.markdown("투자 가능한 금액과 목표를 입력하면 최적의 배당 전략과 미래 수익을 시뮬레이션합니다.")

st.divider()

# ── 입력 섹션 ─────────────────────────────────────────────────────
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📝 투자 정보 입력")

    currency = st.selectbox("💱 통화", ["USD ($)", "KRW (₩)"])
    is_krw = currency == "KRW (₩)"

    if is_krw:
        amount_krw = st.number_input("투자 금액 (만원)", 100, 100_000, 3_000, 100)
        amount_usd = amount_krw * 10_000 / 1350
        st.caption(f"≈ ${amount_usd:,.0f}")
    else:
        amount_usd = st.number_input("투자 금액 ($)", 1_000, 10_000_000, 50_000, 1_000)

    goal = st.selectbox("🎯 투자 목표", [
        "월수입 극대화", "안정적 노후 대비", "배당 성장 + 자산 증식", "종합 균형"
    ])
    horizon = st.slider("📅 투자 기간 (년)", 1, 30, 10)
    risk = st.select_slider(
        "⚖️ 위험 성향",
        options=["매우 보수적", "보수적", "중립", "적극적", "매우 적극적"],
        value="중립",
    )

    simulate_btn = st.button("🚀 전략 추천 & 시뮬레이션 시작", type="primary", use_container_width=True)

with col2:
    st.subheader("💡 금액별 추천 전략 가이드")
    guide_data = {
        "투자 규모": ["$10,000 미만", "$10,000~$50,000", "$50,000~$100,000", "$100,000 이상"],
        "추천 전략 구성": [
            "월배당 ETF 중심 (JEPI, O 등)",
            "월배당 40% + 실버연금 35% + 퀄리티 25%",
            "4개 전략 균등 분산",
            "5개 전략 + 커버드콜 포함",
        ],
        "예상 배당수익률": ["5.5~7%", "4.5~6%", "4~5.5%", "4.5~6%"],
    }
    st.dataframe(pd.DataFrame(guide_data), use_container_width=True, hide_index=True)

    st.info(
        "📌 **투자 팁**: 월배당 ETF(JEPI, JEPQ)는 높은 수익률과 월단위 현금흐름을 제공하지만, "
        "실버연금 전략은 대형 우량주 중심으로 안정성이 높습니다. "
        "투자 기간이 길수록 배당 성장 전략의 복리 효과가 커집니다."
    )

# ── 시뮬레이션 결과 ────────────────────────────────────────────────
if simulate_btn or True:  # 기본으로 보여주기
    st.divider()

    recommendations = recommend_strategies(amount_usd, goal, horizon, risk)
    years_list, reinvest_vals, no_reinvest_vals, divs_reinvest, divs_no_reinvest, avg_yield, avg_price_growth = simulate_growth(
        amount_usd, recommendations, horizon
    )

    # ── 요약 지표 카드 ────────────────────────────────────────────
    st.subheader("📊 투자 요약")
    monthly_income = amount_usd * avg_yield / 12

    disp_symbol = "₩" if is_krw else "$"
    multiplier = 1350 if is_krw else 1

    def fmt(v): return f"{disp_symbol}{v*multiplier:,.0f}"

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("💵 투자 금액", fmt(amount_usd))
        st.metric("📅 예상 월 배당 수입", fmt(monthly_income), f"연 {avg_yield:.1%} 수익률")
    with col2:
        st.metric(f"🏆 {horizon}년 후 예상 가치 (배당 재투자)",
                  fmt(reinvest_vals[-1]),
                  f"+{(reinvest_vals[-1]/amount_usd - 1):.1%}")
        st.metric(f"📦 {horizon}년 후 예상 가치 (배당 수령)",
                  fmt(no_reinvest_vals[-1]),
                  f"+{(no_reinvest_vals[-1]/amount_usd - 1):.1%}")
    with col3:
        st.metric(f"💰 {horizon}년 누적 배당 수입 (재투자 시)", fmt(sum(divs_reinvest)))
        st.metric(f"💸 {horizon}년 누적 배당 수입 (수령 시)", fmt(sum(divs_no_reinvest)))

    # 전략별 수익 구조 설명
    total_return_reinvest = reinvest_vals[-1] / amount_usd - 1
    price_only_return = (1 + avg_price_growth) ** horizon - 1
    div_contribution = total_return_reinvest - price_only_return
    st.caption(
        f"📌 이 포트폴리오의 {horizon}년 총수익 {total_return_reinvest:.1%} 중 "
        f"주가 성장 기여 {price_only_return:.1%} / 배당 기여 {div_contribution:.1%} "
        f"(가중평균 주가 성장률 {avg_price_growth:.1%} 적용)"
    )

    # ── 전략 추천 테이블 ──────────────────────────────────────────
    risk_label = {
        "매우 보수적": "🛡️ 매우 보수적 — 안정형 전략(실버연금·퀄리티) 비중을 크게 높이고, 고위험 전략(커버드콜·성장) 비중을 줄였습니다.",
        "보수적":     "🛡️ 보수적 — 안정형 전략 비중을 높이고, 고위험 전략 비중을 낮췄습니다.",
        "중립":       "⚖️ 중립 — 투자 목표 기반 비중을 그대로 적용했습니다.",
        "적극적":     "🚀 적극적 — 성장·커버드콜 전략 비중을 높이고, 안정형 비중을 낮췄습니다.",
        "매우 적극적":"🚀 매우 적극적 — 고수익 전략(배당성장·커버드콜) 비중을 최대화했습니다.",
    }
    st.info(risk_label.get(risk, ""))
    st.subheader("🎯 추천 포트폴리오 구성")
    rec_df_rows = []
    for r in recommendations:
        inv = r["투자금"] * multiplier
        annual_div = r["투자금"] * r["예상 배당수익률"] * multiplier
        monthly_div = annual_div / 12
        rec_df_rows.append({
            "전략": r["전략"],
            "비중": f"{r['비중']:.0%}",
            "투자금액": f"{disp_symbol}{inv:,.0f}" if not is_krw else f"₩{inv:,.0f}",
            "예상 배당수익률": f"{r['예상 배당수익률']:.1%}",
            "배당 성장률": f"{r['배당 성장률']:.1%}",
            "예상 월 배당": f"{disp_symbol}{monthly_div:,.0f}" if not is_krw else f"₩{monthly_div:,.0f}",
            "변동성": r["변동성"],
        })
    st.dataframe(pd.DataFrame(rec_df_rows), use_container_width=True, hide_index=True)

    # ── 배분 파이차트 + 성장 시뮬레이션 ──────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        from dashboard.components.charts import allocation_pie
        names = [r["전략"] for r in recommendations]
        weights = [r["비중"] for r in recommendations]
        st.plotly_chart(allocation_pie(names, weights, "전략 배분"), use_container_width=True)

    with col2:
        from dashboard.components.charts import projection_chart
        # 통화 변환 적용
        rv = [v * multiplier for v in reinvest_vals]
        nrv = [v * multiplier for v in no_reinvest_vals]
        fig = projection_chart(years_list, rv, nrv,
                               title=f"{horizon}년 투자 성장 시뮬레이션 ({disp_symbol})")
        # 초기 투자금 기준선
        fig.add_hline(y=amount_usd * multiplier, line_dash="dash",
                      line_color="gray", annotation_text="초기 투자금")
        st.plotly_chart(fig, use_container_width=True)

    # ── 연도별 배당 수입 예측 ────────────────────────────────────
    st.subheader("📆 연도별 배당 수입 예측")
    annual_data = []
    for y in range(1, horizon + 1):
        div_r = divs_reinvest[y - 1] * multiplier
        div_nr = divs_no_reinvest[y - 1] * multiplier
        annual_data.append({
            "연도": f"투자 {y}년차",
            "배당 재투자 시 월배당": f"{disp_symbol}{div_r/12:,.0f}" if not is_krw else f"₩{div_r/12:,.0f}",
            "배당 수령 시 월배당": f"{disp_symbol}{div_nr/12:,.0f}" if not is_krw else f"₩{div_nr/12:,.0f}",
            "누적 수령 배당": f"{disp_symbol}{sum(divs_no_reinvest[:y])*multiplier:,.0f}",
        })

    st.dataframe(pd.DataFrame(annual_data), use_container_width=True, hide_index=True)

    # ── 과거 투자 시뮬레이션 ─────────────────────────────────────
    st.subheader("⏰ 만약 과거에 투자했다면?")
    years_ago = st.slider("몇 년 전 투자를 시뮬레이션할까요?", 1, 20, 10, key="past_sim")

    avg_growth = sum(r["비중"] * r["배당 성장률"] for r in recommendations)
    past_result = past_investment_simulation(amount_usd, years_ago, avg_yield, avg_growth, avg_price_growth)

    col1, col2, col3 = st.columns(3)
    with col1:
        init_val = past_result["initial"] * multiplier
        st.metric("초기 투자금",
                  f"{disp_symbol}{init_val:,.0f}" if not is_krw else f"₩{init_val:,.0f}")
    with col2:
        curr_val = past_result["current_value"] * multiplier
        gain = past_result["current_value"] / past_result["initial"] - 1
        st.metric("현재 추정 가치",
                  f"{disp_symbol}{curr_val:,.0f}" if not is_krw else f"₩{curr_val:,.0f}",
                  f"+{gain:.1%}")
    with col3:
        total_d = past_result["total_dividends"] * multiplier
        st.metric(f"{years_ago}년간 수령한 배당",
                  f"{disp_symbol}{total_d:,.0f}" if not is_krw else f"₩{total_d:,.0f}")

    st.caption(
        f"⚠️ 위 시뮬레이션은 평균 배당수익률 {avg_yield:.1%}, 주가 성장률 4% 가정 기반의 추정치입니다. "
        "실제 성과와 다를 수 있으며 투자 손실이 발생할 수 있습니다."
    )

    # ── 투자 목표 반영 설명 ───────────────────────────────────────
    st.subheader("🎯 투자 목표 반영 결과")
    goal_explain = {
        "월수입 극대화": {
            "icon": "💵",
            "desc": "월배당 ETF와 커버드콜 비중을 높였습니다. 매달 최대한 많은 현금을 수령하는 데 최적화되어 있습니다.",
            "강점": "높은 월 현금흐름, 즉각적인 배당 수입",
            "주의": "장기 자산 성장보다 현재 수입에 집중 → 원금 성장은 다소 낮을 수 있음",
            "추천이유": "JEPI·JEPQ 같은 월배당 ETF는 연 6~8% 수준의 배당을 매월 지급합니다.",
        },
        "안정적 노후 대비": {
            "icon": "🏦",
            "desc": "실버 연금 배당 비중을 높였습니다. 저변동성 대형 우량주 중심으로 안정적인 현금흐름을 만듭니다.",
            "강점": "낮은 변동성, 10년+ 연속 배당 기업, 경기침체에도 배당 유지 확률 높음",
            "주의": "수익률은 4~5%대로 상대적으로 낮지만 자산 보전에 강점",
            "추천이유": "JNJ·PG·KO 같은 배당귀족주는 25년 이상 배당을 늘려온 검증된 기업입니다.",
        },
        "배당 성장 + 자산 증식": {
            "icon": "📈",
            "desc": "배당 성장과 퀄리티 코어 비중을 높였습니다. 현재 수익률은 낮아도 복리 효과로 장기 총수익이 극대화됩니다.",
            "강점": f"배당 성장률 연 7~10%, {horizon}년 후 배당 수입이 지금의 {(1.08**horizon):.1f}배 예상",
            "주의": "초기 배당수익률(2~3%)이 낮아 단기 현금흐름은 적음",
            "추천이유": "MSFT·AAPL·V 같은 기업은 수익률은 낮지만 매년 10%씩 배당을 올려왔습니다.",
        },
        "종합 균형": {
            "icon": "⚖️",
            "desc": "수입·성장·안정성을 균형 있게 배분했습니다. 특정 위험에 편중되지 않는 분산 포트폴리오입니다.",
            "강점": "배당수입 + 자산성장 + 리스크 분산 동시 달성",
            "주의": "어느 한 목표에 집중된 포트폴리오보다 최고 성과는 낮을 수 있음",
            "추천이유": "단일 전략 집중 시 특정 시장 상황에서 타격을 받을 수 있어 분산이 유리합니다.",
        },
    }

    exp = goal_explain.get(goal, {})
    if exp:
        st.markdown(f"### {exp['icon']} {goal}")
        st.markdown(exp["desc"])
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.success(f"**강점:** {exp['강점']}")
        with col_g2:
            st.warning(f"**주의:** {exp['주의']}")
        st.info(f"💡 {exp['추천이유']}")

    st.divider()

    # ── 종목별 투자금액 상세 테이블 ──────────────────────────────
    st.subheader("📋 종목별 투자 계획 (상세)")

    STOCK_INFO = {
        "JEPI":  {"name": "JPMorgan Equity Premium Income ETF", "yield": 0.072, "freq": "월배당", "desc": "S&P500 + 커버드콜, 안정적 고배당 ETF"},
        "JEPQ":  {"name": "JPMorgan Nasdaq Equity Premium ETF",  "yield": 0.095, "freq": "월배당", "desc": "나스닥100 + 커버드콜, 기술주 고배당 ETF"},
        "O":     {"name": "Realty Income Corp",                  "yield": 0.055, "freq": "월배당", "desc": "월배당 리츠 대표주, 30년+ 연속 배당"},
        "MAIN":  {"name": "Main Street Capital",                 "yield": 0.060, "freq": "월배당", "desc": "BDC 업체, 월배당 + 특별배당"},
        "STAG":  {"name": "STAG Industrial",                     "yield": 0.040, "freq": "월배당", "desc": "산업용 부동산 리츠, 월배당"},
        "JNJ":   {"name": "Johnson & Johnson",                   "yield": 0.033, "freq": "분기배당", "desc": "헬스케어 대장주, 62년 연속 배당 증가"},
        "KO":    {"name": "Coca-Cola",                           "yield": 0.030, "freq": "분기배당", "desc": "소비재 대장주, 62년 연속 배당 증가"},
        "PG":    {"name": "Procter & Gamble",                    "yield": 0.025, "freq": "분기배당", "desc": "생활용품 대장주, 67년 연속 배당 증가"},
        "VZ":    {"name": "Verizon Communications",              "yield": 0.065, "freq": "분기배당", "desc": "통신 대형주, 안정적 고배당"},
        "PEP":   {"name": "PepsiCo",                             "yield": 0.032, "freq": "분기배당", "desc": "음식료 대장주, 51년 연속 배당 증가"},
        "MSFT":  {"name": "Microsoft",                           "yield": 0.008, "freq": "분기배당", "desc": "빅테크 대장, 연 10%+ 배당 성장"},
        "AAPL":  {"name": "Apple",                               "yield": 0.005, "freq": "분기배당", "desc": "빅테크 대장, 연 5%+ 배당 성장"},
        "V":     {"name": "Visa",                                "yield": 0.008, "freq": "분기배당", "desc": "결제 네트워크 독점, 연 15%+ 배당 성장"},
        "MA":    {"name": "Mastercard",                          "yield": 0.006, "freq": "분기배당", "desc": "결제 네트워크 독점, 연 15%+ 배당 성장"},
        "HD":    {"name": "Home Depot",                          "yield": 0.025, "freq": "분기배당", "desc": "홈인테리어 1위, 연 10%+ 배당 성장"},
        "MMM":   {"name": "3M Company",                          "yield": 0.060, "freq": "분기배당", "desc": "산업재 대장주, 65년 연속 배당 증가"},
        "ABT":   {"name": "Abbott Laboratories",                 "yield": 0.020, "freq": "분기배당", "desc": "의료기기 대장, 52년 연속 배당 증가"},
        "QYLD":  {"name": "Global X NASDAQ 100 Covered Call ETF","yield": 0.120, "freq": "월배당", "desc": "나스닥 커버드콜 ETF, 초고배당"},
    }

    stock_recs = {
        "월배당 최대화":   ["JEPI", "JEPQ", "O", "MAIN", "STAG"],
        "실버 연금 배당":  ["JNJ", "KO", "PG", "VZ", "PEP"],
        "장기 배당 성장":  ["MSFT", "AAPL", "V", "MA", "HD"],
        "퀄리티 배당 코어":["JNJ", "PG", "KO", "MMM", "ABT"],
        "커버드콜 배당":   ["AAPL", "MSFT", "QYLD", "JEPI", "JEPQ"],
    }

    detail_rows = []
    for rec in recommendations:
        strat_name = rec["전략"]
        strat_invest = rec["투자금"]  # USD
        stocks = stock_recs.get(strat_name, [])
        n_stocks = len(stocks)
        per_stock_usd = strat_invest / n_stocks if n_stocks else 0

        for sym in stocks:
            info = STOCK_INFO.get(sym, {"name": sym, "yield": rec["예상 배당수익률"] / n_stocks,
                                        "freq": "-", "desc": "-"})
            invest_amt = per_stock_usd * multiplier
            annual_div = per_stock_usd * info["yield"] * multiplier
            monthly_div = annual_div / 12

            detail_rows.append({
                "전략":        strat_name,
                "종목":        sym,
                "종목명":      info["name"],
                "배당 주기":   info["freq"],
                "투자금액":    f"{disp_symbol}{invest_amt:,.0f}",
                "예상 연배당": f"{disp_symbol}{annual_div:,.0f}",
                "예상 월배당": f"{disp_symbol}{monthly_div:,.0f}",
                "배당수익률":  f"{info['yield']:.1%}",
                "종목 설명":   info["desc"],
            })

    detail_df = pd.DataFrame(detail_rows)
    st.dataframe(detail_df, use_container_width=True, hide_index=True)

    # ── 전략별 합산 요약 ─────────────────────────────────────────
    st.subheader("💼 전략별 투자 합산")
    summary_rows = []
    for rec in recommendations:
        strat_name = rec["전략"]
        stocks = stock_recs.get(strat_name, [])
        n = len(stocks)
        total_annual = sum(
            (rec["투자금"] / n) * STOCK_INFO.get(s, {"yield": rec["예상 배당수익률"]})["yield"]
            for s in stocks
        ) * multiplier
        summary_rows.append({
            "전략":         strat_name,
            "비중":         f"{rec['비중']:.0%}",
            "투자금액":     f"{disp_symbol}{rec['투자금']*multiplier:,.0f}",
            "종목 수":      f"{n}개",
            "예상 연배당":  f"{disp_symbol}{total_annual:,.0f}",
            "예상 월배당":  f"{disp_symbol}{total_annual/12:,.0f}",
            "배당수익률":   f"{rec['예상 배당수익률']:.1%}",
            "변동성":       rec["변동성"],
        })
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

    total_annual_div = sum(
        (rec["투자금"] / len(stock_recs.get(rec["전략"], ["x"])))
        * STOCK_INFO.get(s, {"yield": rec["예상 배당수익률"]})["yield"]
        for rec in recommendations
        for s in stock_recs.get(rec["전략"], [])
    ) * multiplier
    st.success(
        f"📌 **전체 포트폴리오 예상 연배당: {disp_symbol}{total_annual_div:,.0f}"
        f" | 월 {disp_symbol}{total_annual_div/12:,.0f}**"
    )
