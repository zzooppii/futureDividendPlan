"""대시보드 진입점.

실행:
    streamlit run run_dashboard.py
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st

st.set_page_config(
    page_title="배당 투자 리서치 시스템",
    page_icon="💹",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("💹 나스닥 배당 투자 리서치 시스템")

col1, col2, col3 = st.columns(3)
with col1:
    st.info("💰 **내 투자 플래너**\n\n투자금액을 입력하면 맞춤형 전략과 시뮬레이션을 제공합니다.")
with col2:
    st.success("📊 **5가지 전략**\n\n월배당·실버연금·배당성장·퀄리티코어·커버드콜")
with col3:
    st.warning("⚠️ **데이터 출처**\n\nyfinance (무료) 기반. 투자 결정 전 전문가 상담 권장.")

st.divider()
st.markdown("""
### 🚀 시작하기
왼쪽 사이드바에서 페이지를 선택하거나, 아래 순서대로 진행하세요:

1. **💰 내 투자 플래너** → 투자금액 입력, 맞춤 전략 추천 + 시뮬레이션
2. **📈 배당 수입 예측** → 종목별 미래 현금흐름 예측
3. **🥧 포트폴리오 배분** → 종목/섹터 분석
4. **📅 배당 캘린더** → 월별 배당 스케줄 확인
5. **⚔️ 전략 비교** → 5개 전략 백테스트 비교
6. **🌱 성장 분석** → 지속가능성 점수 & 배당함정 탐지
7. **📞 커버드콜** → 커버드콜 수입 시뮬레이터

```bash
# 데이터 미리 로딩 (최초 실행 시 권장):
python setup_data.py

# 대시보드 실행:
streamlit run run_dashboard.py
```
""")
