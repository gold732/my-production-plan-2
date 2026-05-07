import streamlit as st
from pyomo.environ import TerminationCondition, NonNegativeIntegers, NonNegativeReals

from ai_consultant import get_ai_consultant, get_ai_analysis
from optimization_engine import solve_production_plan
# [🚨 수정]: 모든 함수 명칭을 ui_components.py와 100% 일치하도록 복구
from ui_components import (
    render_sidebar, 
    render_supply_demand_tab, 
    render_risk_efficiency_tab, 
    render_data_master_tab
)

st.set_page_config(page_title="AI S&OP Control Tower", layout="wide")
st.title("원예장비 제조업체 총괄생산계획 수립")

# 세션 상태 초기화 및 파라미터 락 설정 (유실 없이 보존)
param_keys = ['opt_mode', 'enable_sub', 'std_time', 'working_days', 'ot_limit', 'max_util', 'min_inv', 'max_cost',
              'v_c_reg', 'v_c_ot', 'v_c_h', 'v_c_l', 'v_c_inv', 'v_c_back', 'v_c_mat', 'v_c_sub',
              'v_w_init', 'v_i_init', 'v_i_final']

if 'pending_updates' not in st.session_state: st.session_state['pending_updates'] = {}
if st.session_state['pending_updates']:
    for pk, pval in st.session_state['pending_updates'].items(): st.session_state[pk] = pval
    st.session_state['pending_updates'] = {}; st.session_state['trigger_reoptimize'] = True

# 초기값 및 강제 잠금 초기화
initial_locked_keys = {'v_w_init', 'v_i_init', 'v_c_sub', 'v_c_inv', 'v_c_mat', 'v_c_back', 'std_time', 'opt_mode', 'enable_sub', 'v_i_final', 'max_util', 'min_inv', 'max_cost'}
for pk in param_keys:
    if f"lock_{pk}" not in st.session_state: st.session_state[f"lock_{pk}"] = (pk in initial_locked_keys)
if "lock_demand_raw" not in st.session_state: st.session_state["lock_demand_raw"] = True

# 세션 기본 상태
for key in ['messages', 'success', 'utils', 'trigger_reoptimize']:
    if key not in st.session_state: st.session_state[key] = [] if key == 'messages' else False

demand, enable_sub, std_time, working_days, ot_limit = render_sidebar()

def run_optimization():
    st.session_state['success'] = False
    try:
        cur_demand = [float(d.strip()) for d in st.session_state['demand_raw'].split(",")]
        cur_domain = NonNegativeIntegers if "IP" in st.session_state['opt_mode'] else NonNegativeReals
        m, sol = solve_production_plan(
            cur_demand, cur_domain, st.session_state['v_c_reg'], st.session_state['v_c_ot'], 
            st.session_state['v_c_h'], st.session_state['v_c_l'], st.session_state['v_c_inv'], st.session_state['v_c_back'], 
            st.session_state['v_c_mat'], st.session_state['v_c_sub'], st.session_state['std_time'], st.session_state['working_days'], 
            st.session_state['ot_limit'], st.session_state['v_w_init'], st.session_state['v_i_init'], st.session_state['v_i_final'], 
            st.session_state['enable_sub'], st.session_state['max_util'], st.session_state['min_inv'], st.session_state['max_cost']
        )
        if sol.solver.termination_condition == TerminationCondition.optimal:
            st.session_state['res'] = m; st.session_state['success'] = True
            st.session_state['utils'] = [(m.P[t]()*st.session_state['std_time']/(8*st.session_state['working_days']*m.W[t]())*100 if m.W[t]() > 0 else 0) for t in range(1, len(cur_demand)+1)]
            st.session_state['ai_analysis'] = get_ai_analysis(f"비용:{m.cost():,.0f}, 가동률:{st.session_state['utils']}")
            st.toast("✅ 수립 완료!")
        else: st.error("❌ 최적해 없음")
    except Exception as e: st.error(f"⚠️ 오류: {str(e)}")

if st.session_state.get('trigger_reoptimize'):
    st.session_state['trigger_reoptimize'] = False; run_optimization()

# 4단 탭 구조 배치
t1, t2, t3, t4 = st.tabs(["📊 공급망 운영", "📉 리스크/효율", "📋 데이터 마스터", "💬 AI 전략 상담방"])

with t1:
    if st.button("🚀 실행"): run_optimization()
    if st.session_state.get('success'):
        render_supply_demand_tab(st.session_state['res'], st.session_state['utils'], demand)

with t2:
    if st.session_state.get('success'):
        render_risk_efficiency_tab(st.session_state['res'], st.session_state['utils'], demand)

with t3:
    if st.session_state.get('success'):
        render_data_master_tab(st.session_state['res'], st.session_state['utils'], demand)

with t4:
    st.subheader("💬 AI 상담방")
    if st.button("🧹 초기화"): st.session_state.messages = []; st.rerun()
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])
    if prompt := st.chat_input("질문하세요"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            res = get_ai_consultant(prompt, "컨텍스트 요약...")
            st.markdown(res); st.session_state.messages.append({"role": "assistant", "content": res})
        if st.session_state.get('param_updated_by_ai'):
            st.session_state['param_updated_by_ai'] = False; st.rerun()
