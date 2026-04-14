import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pyomo.environ import *

# 커스텀 모듈 임포트
from optimization import solve_production_plan
from ai_engine import get_ai_consultant, analyze_risks

# 페이지 설정
st.set_page_config(page_title="AI S&OP Control Tower", layout="wide")
st.title("🚜 원예장비 AI 총괄생산계획 시스템")

# --- 1. 사이드바: 모든 기존 기능 유지 및 AI 보정 추가 ---
with st.sidebar:
    st.header("🎮 시스템 제어판")
    opt_mode = st.radio("알고리즘 선택", ["정수계획법(IP)", "선형계획법(LP)"])
    domain_type = NonNegativeIntegers if "IP" in opt_mode else NonNegativeReals

    st.subheader("🏭 공급망 전략")
    enable_sub = st.toggle("외주 하청(Outsourcing) 허용", value=True)

    st.subheader("🔮 AI 수요 시나리오")
    trend = st.selectbox("시장 상황", ["평시", "호황", "불황", "봄철 수요 폭증"])
    demand_raw = st.text_input("6개월 수요 예측", "1600, 3000, 3200, 3800, 2200, 2200")
    if st.button("🪄 AI 수요 보정"):
        res = get_ai_consultant(f"{demand_raw}를 {trend} 상황에 맞게 숫자 6개로 보정해줘.", "수요예측")
        st.info(f"AI 추천: {res}")

    st.subheader("💰 운영 비용 및 제약")
    v_c_reg = st.number_input("정규 임금 (인/월)", value=640)
    v_c_ot = st.number_input("초과 수당 (Hr)", value=6)
    v_c_sub = st.number_input("외주 비용 (개)", value=30)
    std_time = st.slider("표준 시간", 1.0, 10.0, 4.0)
    working_days = st.slider("가동 일수", 1, 30, 20)
    ot_limit = st.slider("초과근무 제한", 0, 30, 10)
    
    v_w_init = st.number_input("현재 인원", value=80)
    v_i_init = st.number_input("현재고", value=1000)
    v_i_final = st.number_input("목표재고", value=500)

# 데이터 전처리
demand = [float(d.strip()) for d in demand_raw.split(",")]

# --- 2. 탭 구성 ---
tab1, tab2, tab3 = st.tabs(["📊 운영 대시보드", "📉 리스크 분석", "💬 AI 전략 상담"])

if 'res' not in st.session_state: st.session_state['res'] = None

with tab1:
    if st.button("🚀 최적 생산계획 실행"):
        m, sol = solve_production_plan(demand, domain_type, v_c_reg, v_c_ot, 300, 500, 2, 5, 10, v_c_sub, std_time, working_days, ot_limit, v_w_init, v_i_init, v_i_final, enable_sub)
        if sol.solver.termination_condition == TerminationCondition.optimal:
            st.session_state['res'] = m
            st.session_state['utils'] = [(m.P[t]() * std_time / (8 * working_days * m.W[t]()) * 100) for t in range(1, 7)]
            st.toast("최적화 완료!")
        else: st.error("해를 찾을 수 없음")

    if st.session_state['res']:
        m = st.session_state['res']
        # KPI 카드 및 차트 시각화 로직 (기존 기능 그대로 유지)
        st.metric("총 운영 비용", f"{m.cost():,.0f}k")
        fig = go.Figure()
        fig.add_trace(go.Bar(x=list(range(1,7)), y=[m.P[t]() for t in range(1,7)], name="생산"))
        fig.add_trace(go.Scatter(x=list(range(1,7)), y=demand, name="수요", line=dict(color='red')))
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    if st.session_state['res']:
        st.subheader("🚩 AI 리스크 진단 보고서")
        risk_report = analyze_risks(st.session_state['utils'])
        st.warning(risk_report)
        st.line_chart(st.session_state['utils'])

with tab3:
    st.subheader("💬 AI 경영 컨설턴트")
    if st.button("📄 경영 요약 보고서 생성"):
        report = get_ai_consultant("현재 계획의 강점과 약점을 요약해줘.", f"총비용:{st.session_state['res'].cost()}")
        st.success(report)
    # 채팅 인터페이스 생략 (동일 로직 호출)
