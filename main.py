import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pyomo.environ import *
from optimization import solve_production_plan
from ai_engine import get_ai_consultant, get_risk_analysis

# 페이지 설정
st.set_page_config(page_title="AI S&OP Control Tower", layout="wide")
st.title("🚜 원예장비 AI 총괄생산계획 시스템")

# 세션 상태 초기화
if 'messages' not in st.session_state: 
    st.session_state.messages = []
if 'res' not in st.session_state: 
    st.session_state.res = None
if 'utils' not in st.session_state:
    st.session_state.utils = []

# --- 사이드바 영역 ---
with st.sidebar:
    st.header("🎮 시스템 제어판")
    opt_mode = st.radio("알고리즘 선택", ["정수계획법(IP)", "선형계획법(LP)"])
    domain_type = NonNegativeIntegers if "IP" in opt_mode else NonNegativeReals
    enable_sub = st.toggle("외주 하청 허용", value=True)

    st.markdown("---")
    st.subheader("🔮 AI 수요 보정")
    trend = st.selectbox("상황", ["평시", "호황", "불황", "봄철 폭증"])
    demand_raw = st.text_input("수요 예측 (쉼표 구분)", "1600, 3000, 3200, 3800, 2200, 2200")
    if st.button("🪄 AI 수요 보정"):
        suggestion = get_ai_consultant(f"{demand_raw}를 {trend}에 맞게 숫자 6개로만 보정해.", "수요예측")
        st.success(suggestion)

    st.markdown("---")
    st.subheader("💰 운영 비용 및 제약")
    std_time = st.slider("표준 시간", 1.0, 10.0, 4.59)
    working_days = st.slider("가동 일수", 1, 30, 15)
    ot_limit = st.slider("초과근무 제한", 0, 30, 10)
    
    v_c_reg = st.number_input("정규 임금 (인/월)", value=640)
    v_c_ot, v_c_h, v_c_l, v_c_inv, v_c_sub, v_c_mat, v_c_back = 6, 300, 500, 2, 30, 10, 5
    v_w_init = st.number_input("현재 인원", value=80)
    v_i_init, v_i_final = 1000, 500

# 데이터 리스트 변환
demand = [float(d.strip()) for d in demand_raw.split(",")]

# --- 메인 탭 영역 ---
tab1, tab2, tab3 = st.tabs(["📊 운영 대시보드", "📉 리스크 분석", "💬 AI 전략 상담방"])

with tab1:
    if st.button("🚀 최적 생산계획 수립 실행"):
        with st.spinner('계산 중...'):
            m, sol = solve_production_plan(demand, domain_type, v_c_reg, v_c_ot, v_c_h, v_c_l, v_c_inv, v_c_back, v_c_mat, v_c_sub, std_time, working_days, ot_limit, v_w_init, v_i_init, v_i_final, enable_sub)
            if m and sol.solver.termination_condition == TerminationCondition.optimal:
                st.session_state.res = m
                st.session_state.utils = [(m.P[t]() * std_time / (8 * working_days * m.W[t]()) * 100) for t in range(1, 7)]
                st.toast("✅ 최적화 성공!")
            else: 
                st.error("❌ 최적해를 찾지 못했습니다.")

    if st.session_state.res:
        m = st.session_state.res
        # 1. KPI 지표
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("총 운영 비용", f"{m.cost():,.0f}k")
        c2.metric("평균 가동률", f"{sum(st.session_state.utils)/6:.1f}%")
        c3.metric("인력 변동", f"{sum(m.H[t]() + m.L[t]() for t in range(1,7)):.0f}명")
        c4.metric("기말 재고", f"{m.I[6]():,.0f}ea")

        # 2. 메인 생산 흐름 차트
        fig = go.Figure()
        fig.add_trace(go.Bar(x=list(range(1,7)), y=[m.P[t]() for t in range(1,7)], name="자체생산", marker_color='royalblue'))
        fig.add_trace(go.Bar(x=list(range(1,7)), y=[m.C[t]() for t in range(1,7)], name="외주하청", marker_color='gray'))
        fig.add_trace(go.Scatter(x=list(range(1,7)), y=demand, name="수요", line=dict(color='red', dash='dash')))
        fig.add_trace(go.Scatter(x=list(range(1,7)), y=[m.I[t]() for t in range(1,7)], name="재고", yaxis="y2", line=dict(color='orange')))
        fig.update_layout(yaxis2=dict(overlaying='y', side='right'), barmode='stack', title="월별 통합 생산 흐름")
        st.plotly_chart(fig, use_container_width=True)

        # 3. 하단 상세 분석 (기존 복구 그래프 2종)
        col_l, col_r = st.columns(2)
        with col_l:
            st.subheader("💰 비용 세부 구성")
            c_vals = {
                "노무비": sum(v_c_reg*m.W[t]() for t in range(1,7)), 
                "재료비": sum(v_c_mat*m.P[t]() for t in range(1,7)), 
                "외주비": sum(v_c_sub*m.C[t]() for t in range(1,7)), 
                "기타/재고": m.cost() - sum((v_c_reg*m.W[t]() + v_c_mat*m.P[t]() + v_c_sub*m.C[t]()) for t in range(1,7))
            }
            st.plotly_chart(px.pie(names=list(c_vals.keys()), values=list(c_vals.values()), hole=0.4), use_container_width=True)
        
        with col_r:
            st.subheader("👷 월별 인력 운영 현황")
            worker_df = pd.DataFrame({"월": list(range(1,7)), "인원": [m.W[t]() for t in range(1,7)]})
            st.line_chart(worker_df.set_index("월"))

with tab2:
    if st.session_state.res:
        st.subheader("🚩 AI 생산 리스크 진단")
        st.warning(get_risk_analysis(st.session_state.utils, enable_sub))
        st.line_chart(st.session_state.utils)

with tab3:
    st.subheader("💬 AI 전략 상담방")
    if st.button("🧹 대화 초기화"):
        st.session_state.messages = []
        st.rerun()
    
    if st.button("📄 핵심 요약 보고서 생성"):
        if st.session_state.res:
            report = get_ai_consultant("계획 핵심 성과 요약해.", f"비용:{st.session_state.res.cost():,.0f}")
            st.success(report)

    st.markdown("---")
    # 채팅 인터페이스 구현부
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("계획에 대해 질문하세요."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        ctx = f"비용:{st.session_state.res.cost():,.0f}, 외주:{enable_sub}" if st.session_state.res else "데이터 없음"
        with st.chat_message("assistant"):
            res = get_ai_consultant(prompt, ctx)
            st.markdown(res)
            st.session_state.messages.append({"role": "assistant", "content": res})
