import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pyomo.environ import *

# 사용자 정의 모듈 임포트
from optimization import solve_production_plan
from ai_engine import get_ai_consultant, get_risk_analysis

# 1. 페이지 설정
st.set_page_config(page_title="AI S&OP Control Tower", layout="wide")
st.title("🚜 원예장비 AI 총괄생산계획 시스템")

# 2. 세션 상태 초기화
if 'messages' not in st.session_state: 
    st.session_state.messages = []
if 'res' not in st.session_state: 
    st.session_state.res = None
if 'utils' not in st.session_state:
    st.session_state.utils = []

# --- 3. 사이드바 영역 (모든 조절 파라미터 복구) ---
with st.sidebar:
    st.header("🎮 시스템 제어판")
    opt_mode = st.radio("알고리즘 선택", ["정수계획법(IP)", "선형계획법(LP)"])
    domain_type = NonNegativeIntegers if "IP" in opt_mode else NonNegativeReals
    
    st.markdown("---")
    st.subheader("🏭 공급망 전략")
    enable_sub = st.toggle("외주 하청(Outsourcing) 허용", value=True)

    st.markdown("---")
    st.subheader("🔮 AI 수요 시나리오")
    trend = st.selectbox("시장 트렌드 선택", ["평시", "호황(원예 붐)", "불황", "봄철 수요 폭증"])
    demand_raw = st.text_input("6개월 수요 예측 (쉼표 구분)", "1600, 3000, 3200, 3800, 2200, 2200")
    
    if st.button("🪄 AI에게 수요 보정 요청"):
        ai_suggestion = get_ai_consultant(f"현재 수요 {demand_raw}를 {trend} 상황에 맞춰 숫자 6개로만 보정해줘.", "수요 예측")
        st.success(f"AI 추천: {ai_suggestion}")

    st.markdown("---")
    st.subheader("⏱️ 공정 효율 및 제약")
    std_time = st.slider("제품당 표준 작업 시간 (Hr)", 1.0, 10.0, 4.0)
    working_days = st.slider("월간 가동 일수", 1, 30, 20)
    ot_limit = st.slider("인당 월간 초과근무 제한 (Hr)", 0, 30, 10)

    st.markdown("---")
    st.subheader("💰 운영 비용 설정 (천원)")
    # 모든 비용 파라미터 입력창 복구
    v_c_reg = st.number_input("정규 임금 (인/월)", value=640)
    v_c_ot  = st.number_input("초과 근무 수당 (Hr)", value=6)
    v_c_h   = st.number_input("신규 고용 비용 (인)", value=300)
    v_c_l   = st.number_input("해고 비용 (인)", value=500)
    v_c_inv = st.number_input("재고 유지비 (개/월)", value=2)
    v_c_back= st.number_input("부재고 비용 (개/월)", value=5)
    v_c_mat = st.number_input("재료비 (개당)", value=10)
    v_c_sub = st.number_input("외주 하청 비용 (개당)", value=30)

    st.markdown("---")
    st.subheader("📈 초기값 설정")
    v_w_init = st.number_input("현재 근로자 수", value=80)
    v_i_init = st.number_input("현재고 수준", value=1000)
    v_i_final = st.number_input("기말 목표 재고", value=500)

# 데이터 변환
demand = [float(d.strip()) for d in demand_raw.split(",")]

# --- 4. 메인 콘텐츠 영역 (탭 구성) ---
tab1, tab2, tab3 = st.tabs(["📊 운영 대시보드", "📉 리스크 분석", "💬 AI 전략 상담방"])

with tab1:
    if st.button("🚀 최적 생산계획 수립 실행"):
        with st.spinner('최적화 계산 중...'):
            m, sol = solve_production_plan(demand, domain_type, v_c_reg, v_c_ot, v_c_h, v_c_l, v_c_inv, v_c_back, v_c_mat, v_c_sub, std_time, working_days, ot_limit, v_w_init, v_i_init, v_i_final, enable_sub)
            
            if m and sol.solver.termination_condition == TerminationCondition.optimal:
                st.session_state.res = m
                st.session_state.utils = [(m.P[t]() * std_time / (8 * working_days * m.W[t]()) * 100) if m.W[t]() > 0 else 0 for t in range(1, 7)]
                st.toast("✅ 최적화 성공!")
            else:
                st.error("❌ 최적해를 찾지 못했습니다. 제약 조건을 조정해 보세요.")

    if st.session_state.res:
        m = st.session_state.res
        
        # KPI 지표
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("총 운영 비용", f"{m.cost():,.0f}k")
        k2.metric("평균 가동률", f"{sum(st.session_state.utils)/6:.1f}%")
        k3.metric("인력 변동 수", f"{sum(m.H[t]() + m.L[t]() for t in range(1,7)):.0f}명")
        k4.metric("기말 재고량", f"{m.I[6]():,.0f}ea")

        # 메인 차트
        fig = go.Figure()
        fig.add_trace(go.Bar(x=list(range(1,7)), y=[m.P[t]() for t in range(1,7)], name="자체 생산", marker_color='royalblue'))
        fig.add_trace(go.Bar(x=list(range(1,7)), y=[m.C[t]() for t in range(1,7)], name="외주 하청", marker_color='lightslategray'))
        fig.add_trace(go.Scatter(x=list(range(1,7)), y=demand, name="예상 수요", line=dict(color='crimson', dash='dash')))
        fig.add_trace(go.Scatter(x=list(range(1,7)), y=[m.I[t]() for t in range(1,7)], name="재고 수준", yaxis="y2", line=dict(color='orange')))
        
        fig.update_layout(yaxis2=dict(overlaying='y', side='right'), barmode='stack', title="월별 통합 생산 및 재고 흐름")
        st.plotly_chart(fig, use_container_width=True)

        # 하단 그래프 2종 (복구)
        col_l, col_r = st.columns(2)
        with col_l:
            st.subheader("💰 비용 세부 구성")
            costs_breakdown = {
                "노무비": sum(v_c_reg * m.W[t]() for t in range(1, 7)),
                "재료비": sum(v_c_mat * m.P[t]() for t in range(1, 7)),
                "외주비": sum(v_c_sub * m.C[t]() for t in range(1, 7)),
                "기타/재고": m.cost() - sum((v_c_reg * m.W[t]() + v_c_mat * m.P[t]() + v_c_sub * m.C[t]()) for t in range(1, 7))
            }
            st.plotly_chart(px.pie(names=list(costs_breakdown.keys()), values=list(costs_breakdown.values()), hole=0.4), use_container_width=True)
            
        with col_r:
            st.subheader("👷 월별 인력 운영 현황")
            st.line_chart(pd.DataFrame({"인원": [m.W[t]() for t in range(1, 7)]}, index=range(1,7)))

with tab2:
    if st.session_state.res:
        st.warning(get_risk_analysis(st.session_state.utils, enable_sub))
        st.line_chart(pd.DataFrame({"가동률": st.session_state.utils}, index=range(1,7)))

with tab3:
    st.subheader("💬 AI 전략 상담방")
    if st.button("📄 핵심 요약 보고서 생성"):
        if st.session_state.res:
            st.success(get_ai_consultant("계획 성과 요약해.", f"비용:{st.session_state.res.cost():,.0f}"))

    st.markdown("---")
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])

    if prompt := st.chat_input("질문하세요."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        
        ctx = f"비용:{st.session_state.res.cost():,.0f}, 가동률:{st.session_state.utils}" if st.session_state.res else "데이터 없음"
        with st.chat_message("assistant"):
            res = get_ai_consultant(prompt, ctx)
            st.markdown(res)
            st.session_state.messages.append({"role": "assistant", "content": res})
