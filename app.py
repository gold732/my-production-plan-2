import streamlit as st
import pandas as pd
from pyomo.environ import NonNegativeIntegers, NonNegativeReals, TerminationCondition
import plotly.graph_objects as go
import plotly.express as px

# 모듈화된 비즈니스 로직 함수 로드
from ai_consultant import get_ai_consultant
from optimization_engine import solve_production_plan

# 1. 페이지 설정 및 디자인 
st.set_page_config(page_title="AI S&OP Control Tower", layout="wide")
st.title("원예장비 제조업체 총괄생산계획 수립")

# 3. 사이드바
with st.sidebar:
    st.header("🎮 시스템 제어판")
    opt_mode = st.radio("알고리즘 선택", ["정수계획법(IP)", "선형계획법(LP)"])
    domain_type = NonNegativeIntegers if "IP" in opt_mode else NonNegativeReals

    # [요청 사항] 외주 On/Off 토글 추가
    st.markdown("---")
    st.subheader("🏭 공급망 전략")
    enable_sub = st.toggle("외주 하청(Outsourcing) 허용", value=True)

    st.markdown("---")
    st.subheader("⏱️ 공정 효율 및 제약")
    std_time = st.slider("제품당 표준 작업 시간 (Hr)", 1.0, 10.0, 4.0)
    working_days = st.slider("월간 가동 일수", 1, 30, 20)
    ot_limit = st.slider("인당 월간 초과근무 제한 (Hr)", 0, 30, 10)

    st.markdown("---")
    st.subheader("💰 운영 비용 설정 (천원)")
    v_c_reg = st.number_input("정규 임금 (인/월)", value=640)
    v_c_ot  = st.number_input("초과 근무 수당 (Hr)", value=6)
    v_c_h   = st.number_input("신규 고용 비용 (인)", value=300)
    v_c_l   = st.number_input("해고 비용 (인)", value=500)
    v_c_inv = st.number_input("재고 유지비 (개/월)", value=2)
    v_c_back= st.number_input("부재고 비용 (개/월)", value=5)
    v_c_mat = st.number_input("재료비 (개당)", value=10)
    v_c_sub = st.number_input("외주 하청 비용 (개당)", value=30)

    st.markdown("---")
    st.subheader("📈 초기값 및 수요")
    demand_raw = st.text_input("6개월 수요 예측 (쉼표 구분)", "1600, 3000, 3200, 3800, 2200, 2200")
    demand = [float(d.strip()) for d in demand_raw.split(",")]
    v_w_init = st.number_input("현재 근로자 수", value=80)
    v_i_init = st.number_input("현재고 수준", value=1000)
    v_i_final = st.number_input("기말 목표 재고", value=500)

# 5. 세션 상태 관리
if 'messages' not in st.session_state: st.session_state.messages = []
if 'success' not in st.session_state: st.session_state['success'] = False
if 'utils' not in st.session_state: st.session_state['utils'] = []

tab1, tab2, tab3 = st.tabs(["📊 운영 대시보드", "📉 리스크/효율 분석", "💬 AI 전략 상담방"])

with tab1:
    if st.button("🚀 최적 생산계획 수립 실행"):
        st.session_state['success'] = False
        with st.spinner('최적화 수행 중...'):
            try:
                model, sol = solve_production_plan(demand, domain_type, v_c_reg, v_c_ot, v_c_h, v_c_l, v_c_inv, v_c_back, v_c_mat, v_c_sub, std_time, working_days, ot_limit, v_w_init, v_i_init, v_i_final, enable_sub)
                if sol.solver.termination_condition == TerminationCondition.optimal:
                    st.session_state['res'] = model
                    st.session_state['success'] = True
                    # 가동률 계산 및 전역 저장 (AI 연동용)
                    temp_utils = []
                    for t in range(1, len(demand) + 1):
                        denom = 8 * working_days * model.W[t]()
                        temp_utils.append((model.P[t]() * std_time / denom * 100) if denom > 0 else 0)
                    st.session_state['utils'] = temp_utils
                    st.toast("✅ 최적화 성공!")
                else:
                    st.error("❌ 최적해를 찾지 못했습니다.")
            except Exception as e:
                st.error(f"⚠️ 오류: {str(e)}")

    if st.session_state.get('success'):
        m = st.session_state['res']
        utils = st.session_state['utils']
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("총 운영 비용", f"{m.cost():,.0f}k")
        k2.metric("평균 가동률", f"{sum(utils)/len(utils):.1f}%")
        k3.metric("인력 변동 수", f"{sum(m.H[t]() + m.L[t]() for t in range(1,len(demand)+1)):.0f}명")
        k4.metric("기말 재고량", f"{m.I[len(demand)]():,.0f}ea")

        # 메인 차트
        st.subheader("📈 월별 생산/수요/재고 흐름")
        fig = go.Figure()
        fig.add_trace(go.Bar(x=list(range(1,len(demand)+1)), y=[m.P[t]() for t in range(1,len(demand)+1)], name="자체 생산", marker_color='royalblue'))
        fig.add_trace(go.Bar(x=list(range(1,len(demand)+1)), y=[m.C[t]() for t in range(1,len(demand)+1)], name="외주 하청", marker_color='lightslategray'))
        fig.add_trace(go.Scatter(x=list(range(1,len(demand)+1)), y=demand, name="예상 수요", line=dict(color='crimson', dash='dash')))
        fig.add_trace(go.Scatter(x=list(range(1,len(demand)+1)), y=[m.I[t]() for t in range(1,len(demand)+1)], name="재고 수준", yaxis="y2", line=dict(color='orange')))
        fig.update_layout(yaxis2=dict(overlaying='y', side='right'), barmode='stack', hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

        col_l, col_r = st.columns(2)
        with col_l:
            st.subheader("💰 비용 세부 구성")
            costs = {
                "노무비": sum(v_c_reg*m.W[t]() for t in range(1,len(demand)+1)), 
                "재고비": sum(v_c_inv*m.I[t]() for t in range(1,len(demand)+1)), 
                "재료비": sum(v_c_mat*m.P[t]() for t in range(1,len(demand)+1)), 
                "외주비": sum(v_c_sub*m.C[t]() for t in range(1,len(demand)+1)),
                "기타": m.cost() - sum((v_c_reg*m.W[t]() + v_c_inv*m.I[t]() + v_c_mat*m.P[t]() + v_c_sub*m.C[t]()) for t in range(1,len(demand)+1))
            }
            st.plotly_chart(px.pie(names=list(costs.keys()), values=list(costs.values()), hole=0.4), use_container_width=True)
        with col_r:
            st.subheader("👷 월별 인력 운영 현황")
            st.line_chart(pd.DataFrame({"인원": [m.W[t]() for t in range(1,len(demand)+1)]}))

with tab2:
    if st.session_state.get('success'):
        utils = st.session_state['utils']
        st.subheader("⚠️ 운영 리스크 분석 (가동률)")
        fig_risk = px.area(x=list(range(1,len(demand)+1)), y=utils, title="생산 가동률 추이 (%)", markers=True)
        fig_risk.add_hline(y=100, line_dash="dot", line_color="red")
        st.plotly_chart(fig_risk, use_container_width=True)

with tab3:
    st.subheader("💬 AI 전략 상담방")
    if st.button("🧹 대화 내용 초기화"):
        st.session_state.messages = []; st.rerun()
    
    st.markdown("---")
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])

    if prompt := st.chat_input("질문하세요."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        
        if st.session_state['success']:
            m = st.session_state['res']
            u_str = ", ".join([f"{i+1}월:{val:.1f}%" for i, val in enumerate(st.session_state['utils'])])
            ctx = f"총비용:{m.cost():,.0f}, 가동률:[{u_str}], 외주허용:{enable_sub}"
        else:
            ctx = "데이터 없음"

        with st.chat_message("assistant"):
            ai_res = get_ai_consultant(prompt, ctx)
            st.markdown(ai_res)
            st.session_state.messages.append({"role": "assistant", "content": ai_res})