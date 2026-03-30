"""재사용 가능한 Plotly 차트 컴포넌트."""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots


COLORS = {
    "primary": "#1f77b4",
    "success": "#2ca02c",
    "warning": "#ff7f0e",
    "danger": "#d62728",
    "purple": "#9467bd",
    "bg": "#0e1117",
    "card": "#1e2130",
}

STRATEGY_COLORS = {
    "월배당 최대화": "#ff7f0e",
    "실버 연금 배당": "#1f77b4",
    "장기 배당 성장": "#2ca02c",
    "퀄리티 배당 코어": "#9467bd",
    "커버드콜 배당": "#d62728",
}


def equity_curve_chart(
    results: dict,           # {전략명: BacktestResult}
    title: str = "포트폴리오 성과",
) -> go.Figure:
    fig = go.Figure()
    for name, res in results.items():
        if res.daily_values.empty:
            continue
        norm = res.daily_values / res.daily_values.iloc[0] * 100
        color = STRATEGY_COLORS.get(name, "#aaaaaa")
        fig.add_trace(go.Scatter(
            x=norm.index, y=norm.values,
            name=name, line=dict(color=color, width=2),
            hovertemplate=f"{name}: %{{y:.1f}}<br>%{{x|%Y-%m-%d}}<extra></extra>",
        ))
    fig.update_layout(
        title=title, xaxis_title="날짜", yaxis_title="수익률 (100 기준)",
        hovermode="x unified", template="plotly_dark",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=450,
    )
    return fig


def drawdown_chart(result, title: str = "낙폭(Drawdown)") -> go.Figure:
    fig = go.Figure()
    if not result.drawdown_series.empty:
        fig.add_trace(go.Scatter(
            x=result.drawdown_series.index,
            y=result.drawdown_series.values * 100,
            fill="tozeroy", fillcolor="rgba(214,39,40,0.3)",
            line=dict(color=COLORS["danger"], width=1),
            name="낙폭 (%)",
        ))
    fig.update_layout(
        title=title, xaxis_title="날짜", yaxis_title="낙폭 (%)",
        template="plotly_dark", height=300,
    )
    return fig


def dividend_bar_chart(divs_by_year: pd.Series, title: str = "연간 배당 수입") -> go.Figure:
    fig = go.Figure(go.Bar(
        x=divs_by_year.index.astype(str),
        y=divs_by_year.values,
        marker_color=COLORS["success"],
        text=[f"${v:,.0f}" for v in divs_by_year.values],
        textposition="outside",
    ))
    fig.update_layout(
        title=title, xaxis_title="연도", yaxis_title="배당 수입 ($)",
        template="plotly_dark", height=350,
    )
    return fig


def projection_chart(
    years: list[int],
    reinvest_values: list[float],
    no_reinvest_values: list[float],
    title: str = "투자 성장 시뮬레이션",
) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=years, y=reinvest_values, name="배당 재투자",
        line=dict(color=COLORS["success"], width=3),
        fill="tonexty" if no_reinvest_values else None,
    ))
    fig.add_trace(go.Scatter(
        x=years, y=no_reinvest_values, name="배당 수령",
        line=dict(color=COLORS["primary"], width=3),
    ))
    fig.update_layout(
        title=title, xaxis_title="투자 연도",
        yaxis_title="포트폴리오 가치 ($)",
        template="plotly_dark", height=400,
        hovermode="x unified",
    )
    return fig


def allocation_pie(symbols: list[str], weights: list[float], title: str = "포트폴리오 배분") -> go.Figure:
    fig = go.Figure(go.Pie(
        labels=symbols, values=weights,
        hole=0.4,
        textinfo="label+percent",
        hovertemplate="%{label}: %{percent}<extra></extra>",
    ))
    fig.update_layout(title=title, template="plotly_dark", height=400)
    return fig


def monthly_dividend_heatmap(dividend_calendar: pd.DataFrame) -> go.Figure:
    """dividend_calendar: index=종목, columns=월(1~12), values=예상 배당금."""
    fig = go.Figure(go.Heatmap(
        z=dividend_calendar.values,
        x=[f"{m}월" for m in range(1, 13)],
        y=dividend_calendar.index.tolist(),
        colorscale="Greens",
        hoverongaps=False,
        hovertemplate="%{y} %{x}: $%{z:.2f}<extra></extra>",
    ))
    fig.update_layout(
        title="월별 배당 수입 히트맵",
        xaxis_title="월", yaxis_title="종목",
        template="plotly_dark", height=max(300, len(dividend_calendar) * 30 + 100),
    )
    return fig


def radar_chart(strategies: list[str], categories: list[str], values: list[list[float]]) -> go.Figure:
    fig = go.Figure()
    cats_closed = categories + [categories[0]]
    for name, vals in zip(strategies, values):
        vals_closed = vals + [vals[0]]
        color = STRATEGY_COLORS.get(name, "#aaaaaa")
        fig.add_trace(go.Scatterpolar(
            r=vals_closed, theta=cats_closed,
            fill="toself", name=name,
            line=dict(color=color),
        ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        template="plotly_dark", height=450,
        title="전략별 특성 비교",
    )
    return fig


def dividend_growth_line(data: dict[str, pd.Series], title: str = "배당 성장 추이") -> go.Figure:
    """data: {symbol: annual_dividend_series}"""
    fig = go.Figure()
    for sym, series in data.items():
        if series.empty:
            continue
        fig.add_trace(go.Scatter(
            x=series.index.astype(str), y=series.values,
            name=sym, mode="lines+markers",
            hovertemplate=f"{sym}: $%{{y:.3f}}<extra></extra>",
        ))
    fig.update_layout(
        title=title, xaxis_title="연도", yaxis_title="주당 연간 배당 ($)",
        template="plotly_dark", height=400,
    )
    return fig


def covered_call_comparison(
    years: list, div_only: list, with_cc: list,
) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(x=years, y=div_only, name="배당만", marker_color=COLORS["primary"]))
    fig.add_trace(go.Bar(x=years, y=with_cc, name="배당+커버드콜", marker_color=COLORS["success"]))
    fig.update_layout(
        barmode="group", title="배당 vs 배당+커버드콜 수입 비교",
        xaxis_title="연도", yaxis_title="수입 ($)",
        template="plotly_dark", height=400,
    )
    return fig
