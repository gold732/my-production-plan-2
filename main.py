import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pyomo.environ import *

# 파일 분리 모듈 임포트
from optimization import solve_production_plan
from ai_engine import get_ai_response, get_risk_analysis

st.set_page_config(page_title="S&OP AI Control Tower", layout="wide")

# [세션 상태 관리]
if 'res' not in st.session_state: st.session_state.res = None
if 'messages' not in st.session_state: st.session_state.messages = []

# --- 사이드바 (모든 입력 유지) ---
with st.sidebar:
    st.header("⚙️ 생산 제약 설정")
    opt_mode = st.radio("알고리즘", ["IP", "LP"])
    domain = NonNegativeIntegers if opt_mode == "IP" else NonNegativeReals
    enable_sub = st.toggle("외주 허용", value=True)
    
    st.markdown("---")
    demand_raw = st.text_input("수요 예측 (6개월)", "1600, 3000, 3200, 3800, 2200, 2200")
    demand = [float(d.strip()) for d in demand_raw.split(",")]
    
    # AI 수요 보정 버튼 (ai_engine 활용)
    if st.button("🪄 AI 수요 최적화 제안"):
        suggestion = get_ai_response(f"수요 {demand_raw}를 시장 호황에 맞춰 보정해줘.", "데이터 분석")
        st.success(suggestion)

    # 나머지 비용 설정 (기존과 동일)
    v_c_reg = st.number_input("정규 임금", value=640)
    # ... (기존 비용 입력 코드들) ...

# --- 메인 화면 (탭 구성) ---
tab1, tab2, tab3 = st.tabs(["📊 대시보드", "📉 리스크 분석", "💬 AI 상담"])

with tab1:
    if st.button("🚀 최적 생산계획 수립"):
        m, sol = solve_production_plan(demand, domain, v_c_reg, 6, 300, 500, 2, 5, 10, 30, 4.0, 20, 10, 80, 1000, 500, enable_sub)
        st.session_state.res = m
        st.session_state.utils = [(m.P[t]() * 4.0 / (8 * 20 * m.W[t]()) * 100) for t in range(1, 7)]
        st.toast("최적화 완료!")

    if st.session_state.res:
        m = st.session_state.res
        st.metric("총 비용", f"{m.cost():,.0f}k")
        # Plotly 차트 시각화 (기존 코드 그대로 적용)

with tab2:
    if st.session_state.res:
        st.subheader("🚩 AI 리스크 진단")
        st.warning(get_risk_analysis(st.session_state.utils))
        st.line_chart(st.session_state.utils)

with tab3:
    st.subheader("💬 AI 경영 컨설턴트")
    # 채팅 인터페이스 (get_ai_response 활용)
