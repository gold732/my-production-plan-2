import streamlit as st
from pyomo.environ import TerminationCondition, NonNegativeIntegers, NonNegativeReals

from ai_consultant import get_ai_consultant, get_ai_analysis
from optimization_engine import solve_production_plan
from ui_components import (
    render_sidebar, render_supply_demand_tab, 
    render_risk_efficiency_tab, render_data_master_tab
)

st.set_page_config(page_title="AI S&OP Control Tower", layout="wide")
st.title("원예장비 제조업체 총괄생산계획 수립")

# 1. 기초 파라미터 이니셜라이징 (기존 로직 보존)
param_defaults = {
    'opt_mode': "정수계획법(IP)", 'enable_sub': True, 'std_time': 4.0, 'working_days': 20, 'ot_limit': 10,
    'max_util': 100.0, 'min_inv': 0.0, 'max_cost': 999999.0, 'v_c_reg': 640.0, 'v_c_ot': 6.0,
    'v_c_h': 300.0, 'v_c_l': 500.0, 'v_c_inv': 2.0, 'v_c_back': 5.0, 'v_c_mat': 10.0, 'v_c_sub': 30.0,
    'v_w_init': 80.0, 'v_i_init': 1000.0, 'v_i_final': 500.0, 'demand_raw': "1600, 3000, 3200, 3800, 2200, 2200"
}
for k, v in param_defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# 2. 보안 잠금 설정
initial_locked_keys = {'v_w_init', 'v_i_init', 'v_c_sub', 'v_c_inv', 'v_c_mat', 'v_c_back', 'std_time', 'opt_mode', 'enable_sub', 'v_i_final', 'max_util', 'min_inv', 'max_cost'}
for pk in initial_locked_keys:
    if f"lock_{pk}" not in st.session_state: st.session_state[f"lock_{pk}"] = True
if "lock_demand_raw" not in st.session_state: st.session_state["lock_demand_raw"] = True

for key in ['messages', 'success', 'utils', 'trigger_reoptimize', 'ai_analysis']:
    if key not in st.session_state: st.session_state[key] = [] if key == 'messages' else None

# ---------------------------------------------------------
# [핵심] 최적화 함수 정의 (사이드바 렌더링 전 호출 가능하도록 구성)
# ---------------------------------------------------------
def perform_optimization_flow():
    """알고리즘 기반 단계적 제약 완화 복구 (AI 의존 제거)"""
    st.session_state['success'] = False
    demand = [float(d.strip()) for d in st.session_state['demand_raw'].split(",") if d.strip()]
    
    # 가변 파라미터 임시 저장
    t_sub = st.session_state['enable_sub']
    t_util = st.session_state['max_util']
    t_ot = st.session_state['ot_limit']
    t_days = st.session_state['working_days']
    
    for attempt in range(5): # 최대 5단계 완화 시도
        cur_domain = NonNegativeIntegers if "IP" in st.session_state['opt_mode'] else NonNegativeReals
        m, sol = solve_production_plan(
            demand, cur_domain, st.session_state['v_c_reg'], st.session_state['v_c_ot'], 
            st.session_state['v_c_h'], st.session_state['v_c_l'], st.session_state['v_c_inv'], st.session_state['v_c_back'], 
            st.session_state['v_c_mat'], st.session_state['v_c_sub'], st.session_state['std_time'], 
            t_days, t_ot, st.session_state['v_w_init'], st.session_state['v_i_init'], st.session_state['v_i_final'], 
            t_sub, t_util, st.session_state['min_inv'], st.session_state['max_cost']
        )
        
        if sol.solver.termination_condition == TerminationCondition.optimal:
            # 성공 시 최종 파라미터를 세션에 업데이트 (위젯 렌더링 전이므로 안전)
            st.session_state['enable_sub'] = t_sub
            st.session_state['max_util'] = t_util
            st.session_state['ot_limit'] = t_ot
            st.session_state['working_days'] = t_days
            
            st.session_state['res'] = m
            st.session_state['success'] = True
            st.session_state['utils'] = [(m.P[t]()*st.session_state['std_time']/(8*t_days*m.W[t]())*100 if m.W[t]() > 0 else 0) for t in range(1, len(demand)+1)]
            
            # AI 분석 리포트 생성 (가성비 Flash-Lite 사용)
            ctx = f"비용:{m.cost():,.0f}, 가동률:{st.session_state['utils']}"
            st.session_state['ai_analysis'] = get_ai_analysis(ctx)
            if attempt > 0: st.toast(f"✅ {attempt}단계 완화로 해결!")
            return
        
        # [단계적 완화 알고리즘]
        if attempt == 0: t_sub = True # 1. 외주 허용
        elif attempt == 1: t_util = 100.0 # 2. 가동률 제한 해제
        elif attempt == 2: t_ot = 60.0 # 3. 연장근로 확대
        elif attempt == 3: t_days = 25 # 4. 가동일수 증가
        else: break

    st.error("❌ 알고리즘 완화 시도 후에도 최적해를 찾지 못했습니다.")

# ---------------------------------------------------------
# [핵심] 위젯 렌더링 전 데이터 업데이트 로직 배치 (에러 방지)
# ---------------------------------------------------------
if st.session_state.get('trigger_reoptimize'):
    st.session_state['trigger_reoptimize'] = False
    perform_optimization_flow()

# 사이드바 렌더링 (이미 세션값이 업데이트되어 위젯에 자동 반영됨)
demand, _, _, _, _ = render_sidebar()

# 탭 UI 배치 (기존 시각화 로직 100% 보존)
t1, t2, t3, t4 = st.tabs(["📊 공급망 운영", "📉 리스크/효율", "📋 데이터 마스터", "💬 AI 전략 상담방"])

with t1:
    if st.button("🚀 생산계획 수립 실행"):
        perform_optimization_flow()
        st.rerun() # 값 반영을 위해 1회 갱신
    if st.session_state.get('success'):
        render_supply_demand_tab(st.session_state['res'], st.session_state['utils'], demand)

with t2:
    if st.session_state.get('success'):
        render_risk_efficiency_tab(st.session_state['res'], st.session_state['utils'], demand)

with t3:
    if st.session_state.get('success'):
        render_data_master_tab(st.session_state['res'], st.session_state['utils'], demand)

with t4:
    # (기존 상담방 로직 보존)
    st.subheader("💬 AI 전략 상담방")
    if st.button("🧹 초기화"): st.session_state.messages = []; st.rerun()
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])
    if prompt := st.chat_input("조언을 구하세요"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            u_str = ", ".join([f"{v:.1f}%" for v in st.session_state['utils']]) if st.session_state['utils'] else "N/A"
            ctx = f"가동률:[{u_str}] | 비용:{st.session_state['res'].cost() if st.session_state['res'] else 'N/A'}"
            res = get_ai_consultant(prompt, ctx)
            st.markdown(res); st.session_state.messages.append({"role": "assistant", "content": res})
        if st.session_state.get('param_updated_by_ai'):
            st.session_state['param_updated_by_ai'] = False
            st.rerun()
