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

# 초기 세션 상태 설정 보존
param_defaults = {
    'opt_mode': "정수계획법(IP)", 'enable_sub': True, 'std_time': 4.0, 'working_days': 20, 'ot_limit': 10,
    'max_util': 100.0, 'min_inv': 0.0, 'max_cost': 999999.0, 'v_c_reg': 640.0, 'v_c_ot': 6.0,
    'v_c_h': 300.0, 'v_c_l': 500.0, 'v_c_inv': 2.0, 'v_c_back': 5.0, 'v_c_mat': 10.0, 'v_c_sub': 30.0,
    'v_w_init': 80.0, 'v_i_init': 1000.0, 'v_i_final': 500.0, 'demand_raw': "1600, 3000, 3200, 3800, 2200, 2200"
}
for k, v in param_defaults.items():
    if k not in st.session_state: st.session_state[k] = v

if st.session_state.get('pending_updates'):
    for pk, pval in st.session_state['pending_updates'].items(): st.session_state[pk] = pval
    st.session_state['pending_updates'] = {}; st.session_state['trigger_reoptimize'] = True

initial_locked_keys = {'v_w_init', 'v_i_init', 'v_c_sub', 'v_c_inv', 'v_c_mat', 'v_c_back', 'std_time', 'opt_mode', 'enable_sub', 'v_i_final', 'max_util', 'min_inv', 'max_cost'}
for pk in initial_locked_keys:
    if f"lock_{pk}" not in st.session_state: st.session_state[f"lock_{pk}"] = True
if "lock_demand_raw" not in st.session_state: st.session_state["lock_demand_raw"] = True

for key in ['messages', 'success', 'utils', 'trigger_reoptimize', 'ai_analysis', 'skip_analysis']:
    if key not in st.session_state: st.session_state[key] = [] if key == 'messages' else (False if key == 'skip_analysis' else None)

demand, enable_sub, std_time, working_days, ot_limit = render_sidebar()

def run_optimization():
    st.session_state['success'] = False
    try:
        cur_domain = NonNegativeIntegers if "IP" in st.session_state['opt_mode'] else NonNegativeReals
        m, sol = solve_production_plan(
            demand, cur_domain, st.session_state['v_c_reg'], st.session_state['v_c_ot'], 
            st.session_state['v_c_h'], st.session_state['v_c_l'], st.session_state['v_c_inv'], st.session_state['v_c_back'], 
            st.session_state['v_c_mat'], st.session_state['v_c_sub'], st.session_state['std_time'], st.session_state['working_days'], 
            st.session_state['ot_limit'], st.session_state['v_w_init'], st.session_state['v_i_init'], st.session_state['v_i_final'], 
            st.session_state['enable_sub'], st.session_state['max_util'], st.session_state['min_inv'], st.session_state['max_cost']
        )
        if sol.solver.termination_condition == TerminationCondition.optimal:
            st.session_state['res'] = m; st.session_state['success'] = True
            st.session_state['utils'] = [(m.P[t]()*st.session_state['std_time']/(8*st.session_state['working_days']*m.W[t]())*100 if m.W[t]() > 0 else 0) for t in range(1, len(demand)+1)]
            
            # [RPD 절감 핵심] AI가 이미 상담을 진행했다면 추가 리포트 분석(get_ai_analysis) 스킵
            if not st.session_state.get('skip_analysis'):
                ctx_summary = f"비용:{m.cost():,.0f}, 가동률:{st.session_state['utils']}"
                st.session_state['ai_analysis'] = get_ai_analysis(ctx_summary)
            else:
                st.session_state['skip_analysis'] = False
            st.toast("✅ 최적화 완료")
        else: 
            st.error("❌ 최적해 없음")
            st.session_state['skip_analysis'] = True
            recovery_ctx = f"상태:Infeasible | 가동률제한:{st.session_state['max_util']}%"
            recovery_msg = get_ai_consultant("최적화 실패 복구 요청", recovery_ctx)
            st.session_state.messages.append({"role": "assistant", "content": f"🚨 [자동 복구] {recovery_msg}"})
            # 파라미터가 바뀌었으면 즉시 새로고침하여 AI가 원샷으로 고친 값 반영
            if st.session_state.get('param_updated_by_ai'):
                st.session_state['param_updated_by_ai'] = False; st.rerun()
            
    except Exception as e: st.error(f"⚠️ 시스템 오류: {str(e)}")

if st.session_state.get('trigger_reoptimize'):
    st.session_state['trigger_reoptimize'] = False; run_optimization()

# 4단 탭 UI (원본 100% 보존)
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
    if prompt := st.chat_input("조언을 구하세요"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            u_str = ", ".join([f"{v:.1f}%" for v in st.session_state['utils']]) if st.session_state['utils'] else "N/A"
            ctx = f"가동률:[{u_str}] | 비용:{st.session_state['res'].cost() if st.session_state['res'] else 'N/A'}"
            res = get_ai_consultant(prompt, ctx)
            st.markdown(res); st.session_state.messages.append({"role": "assistant", "content": res})
        if st.session_state.get('param_updated_by_ai'):
            st.session_state['param_updated_by_ai'] = False; st.rerun()
