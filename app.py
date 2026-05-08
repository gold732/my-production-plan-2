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

# 1. 기초 파라미터 초기화
param_defaults = {
    'opt_mode': "정수계획법(IP)", 'enable_sub': True, 'std_time': 4.0, 'working_days': 20, 'ot_limit': 10,
    'max_util': 100.0, 'min_inv': 0.0, 'max_cost': 999999.0, 'v_c_reg': 640.0, 'v_c_ot': 6.0,
    'v_c_h': 300.0, 'v_c_l': 500.0, 'v_c_inv': 2.0, 'v_c_back': 5.0, 'v_c_mat': 10.0, 'v_c_sub': 30.0,
    'v_w_init': 80.0, 'v_i_init': 1000.0, 'v_i_final': 500.0, 'demand_raw': "1600, 3000, 3200, 3800, 2200, 2200"
}
for k, v in param_defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# 2. 보안 잠금(Lock) 설정
initial_locked_keys = {
    'v_w_init', 'v_i_init', 'v_c_sub', 'v_c_inv', 'v_c_mat', 'v_c_back', 
    'std_time', 'opt_mode', 'enable_sub', 'v_i_final', 'max_util', 'min_inv', 'max_cost'
}
for pk in initial_locked_keys:
    if f"lock_{pk}" not in st.session_state: st.session_state[f"lock_{pk}"] = True
if "lock_demand_raw" not in st.session_state: st.session_state["lock_demand_raw"] = True

for key in ['messages', 'success', 'utils', 'ai_analysis']:
    if key not in st.session_state: st.session_state[key] = [] if key == 'messages' else None

# 3. 사이드바 및 실행 엔진
demand, enable_sub, std_time, working_days, ot_limit = render_sidebar()

def run_optimization():
    """임금/제약 동적 탐색 루프가 포함된 강화된 실행 엔진"""
    st.session_state['success'] = False
    
    # [Step 1] 사용자 지정 원본 조건으로 시도
    def try_solve(p_overrides={}):
        p = {
            "v_c_reg": st.session_state['v_c_reg'], "v_c_sub": st.session_state['v_c_sub'],
            "max_util": st.session_state['max_util'], "max_cost": st.session_state['max_cost'],
            "min_inv": st.session_state['min_inv'], "enable_sub": st.session_state['enable_sub'],
            "ot_limit": st.session_state['ot_limit']
        }
        p.update(p_overrides)
        
        cur_domain = NonNegativeIntegers if "IP" in st.session_state['opt_mode'] else NonNegativeReals
        return solve_production_plan(
            demand, cur_domain, p['v_c_reg'], st.session_state['v_c_ot'], 
            st.session_state['v_c_h'], st.session_state['v_c_l'], st.session_state['v_c_inv'], st.session_state['v_c_back'], 
            st.session_state['v_c_mat'], p['v_c_sub'], st.session_state['std_time'], st.session_state['working_days'], 
            p['ot_limit'], st.session_state['v_w_init'], st.session_state['v_i_init'], st.session_state['v_i_final'], 
            p['enable_sub'], p['max_util'], p['min_inv'], p['max_cost']
        )

    # 기본 실행
    m, sol = try_solve()
    
    if sol.solver.termination_condition == TerminationCondition.optimal:
        finalize_optimization(m, "✅ 사용자 지정 조건 수립 완료")
        return

    # [Step 2] 실패 시: 동적 임금/비용 탐색 (Sensitivity Search)
    st.info("🤖 현재 조건에서 해가 없습니다. 시스템이 가능한 파라미터 범위를 탐색합니다...")
    
    # 임금을 90%부터 10%씩 줄여보며 해를 찾음
    for ratio in [0.9, 0.7, 0.5, 0.3, 0.1, 0.01]:
        test_wage = round(st.session_state['v_c_reg'] * ratio, 2)
        m, sol = try_solve({"v_c_reg": test_wage})
        if sol.solver.termination_condition == TerminationCondition.optimal:
            st.session_state['v_c_reg'] = test_wage
            finalize_optimization(m, f"🚨 [자동 보정] 정규 임금을 기존 대비 {int(ratio*100)}% 수준({test_wage})으로 조정하여 해를 찾았습니다.")
            return

    # [Step 3] 그래도 실패 시: 제약 완화 시퀀스
    relaxations = [
        {"max_util": 100.0, "name": "가동률 제한 해제 (100%)"},
        {"max_cost": 99999999.0, "name": "예산 제약 해제"},
        {"enable_sub": True, "min_inv": 0.0, "name": "외주 허용 및 최소 재고 해제"}
    ]
    
    for relax in relaxations:
        m, sol = try_solve(relax)
        if sol.solver.termination_condition == TerminationCondition.optimal:
            msg = f"🚨 [제약 완화] '{relax['name']}' 적용으로 해를 찾았습니다."
            for k, v in relax.items(): 
                if k != "name": st.session_state[k] = v
            finalize_optimization(m, msg)
            return

    st.error("❌ 모든 탐색 시도 실패: 수요가 너무 높거나 기초 자산이 부족하여 물리적으로 해를 산출할 수 없습니다.")

def finalize_optimization(m, success_msg):
    """성공 시 공통 처리 로직"""
    st.session_state['res'] = m
    st.session_state['success'] = True
    st.session_state['utils'] = [(m.P[t]()*st.session_state['std_time']/(8*st.session_state['working_days']*m.W[t]())*100 if m.W[t]() > 0 else 0) for t in range(1, len(demand)+1)]
    
    ctx_summary = f"비용:{m.cost():,.0f}, 가동률:{st.session_state['utils']}, 부재고:{sum(m.S[t]() for t in range(1,len(demand)+1))}"
    st.session_state['ai_analysis'] = get_ai_analysis(ctx_summary)
    st.success(success_msg)
    st.toast("생산계획 최적화 완료")

# UI 탭 배치
t1, t2, t3, t4 = st.tabs(["📊 공급망 운영", "📉 리스크/효율", "📋 데이터 마스터", "💬 AI 전략 상담방"])

with t1:
    if st.button("🚀 생산계획 수립 실행"): run_optimization()
    if st.session_state.get('success'): render_supply_demand_tab(st.session_state['res'], st.session_state['utils'], demand)

with t2:
    if st.session_state.get('success'): render_risk_efficiency_tab(st.session_state['res'], st.session_state['utils'], demand)

with t3:
    if st.session_state.get('success'): render_data_master_tab(st.session_state['res'], st.session_state['utils'], demand)

with t4:
    st.subheader("💬 AI 전략 상담방")
    if st.button("🧹 초기화"): st.session_state.messages = []; st.rerun()
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])
    if prompt := st.chat_input("의사결정에 필요한 조언을 구하세요"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            u_str = ", ".join([f"{v:.1f}%" for v in st.session_state.get('utils', [])])
            cost_val = st.session_state['res'].cost() if st.session_state['res'] else "N/A"
            res = get_ai_consultant(prompt, f"현황 - 가동률:[{u_str}], 비용:{cost_val}")
            st.markdown(res); st.session_state.messages.append({"role": "assistant", "content": res})
