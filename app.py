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

# 1. 기초 파라미터 이니셜라이징
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

for key in ['messages', 'success', 'utils', 'trigger_reoptimize', 'ai_analysis']:
    if key not in st.session_state: st.session_state[key] = [] if key == 'messages' else None

# 3. 사이드바 및 최적화 실행
demand, enable_sub, std_time, working_days, ot_limit = render_sidebar()

def run_optimization():
    """파라미터 역산 및 제약 완화가 통합된 지능형 엔진"""
    st.session_state['success'] = False
    
    # [복구 시나리오: 파라미터 보정 우선 -> 제약 완화 차선]
    relaxation_steps = [
        {"name": "사용자 지정 조건", "changes": {}},
        # [신규] 비용 파라미터 보정 단계: 임금을 예산에 맞춰 자동 스케일링 (정규임금 조정)
        {"name": "예산 맞춤형 비용 파라미터 보정 (임금/외주비 최적화)", 
         "changes": {"v_c_reg": 10.0 if st.session_state['v_c_reg'] > 500 else st.session_state['v_c_reg'] * 0.1, 
                     "v_c_sub": 10.0 if st.session_state['v_c_sub'] > 20 else st.session_state['v_c_sub'] * 0.5}},
        {"name": "가동률 제한 해제 (100%)", "changes": {"max_util": 100.0}},
        {"name": "예산 제약 전면 해제", "changes": {"max_cost": 99999999.0}},
        {"name": "최소 재고 및 외주 허용 강제화", "changes": {"min_inv": 0.0, "enable_sub": True}},
        {"name": "연장 근로 한도 확장 (+20Hr)", "changes": {"ot_limit": st.session_state['ot_limit'] + 20}}
    ]

    final_msg = ""
    found_solution = False

    for step in relaxation_steps:
        # 현재 루프의 파라미터 준비
        p = {
            "v_c_reg": step["changes"].get("v_c_reg", st.session_state['v_c_reg']),
            "v_c_sub": step["changes"].get("v_c_sub", st.session_state['v_c_sub']),
            "max_util": step["changes"].get("max_util", st.session_state['max_util']),
            "max_cost": step["changes"].get("max_cost", st.session_state['max_cost']),
            "min_inv": step["changes"].get("min_inv", st.session_state['min_inv']),
            "enable_sub": step["changes"].get("enable_sub", st.session_state['enable_sub']),
            "ot_limit": step["changes"].get("ot_limit", st.session_state['ot_limit'])
        }

        try:
            cur_domain = NonNegativeIntegers if "IP" in st.session_state['opt_mode'] else NonNegativeReals
            m, sol = solve_production_plan(
                demand, cur_domain, p['v_c_reg'], st.session_state['v_c_ot'], 
                st.session_state['v_c_h'], st.session_state['v_c_l'], st.session_state['v_c_inv'], st.session_state['v_c_back'], 
                st.session_state['v_c_mat'], p['v_c_sub'], st.session_state['std_time'], st.session_state['working_days'], 
                p['ot_limit'], st.session_state['v_w_init'], st.session_state['v_i_init'], st.session_state['v_i_final'], 
                p['enable_sub'], p['max_util'], p['min_inv'], p['max_cost']
            )

            if sol.solver.termination_condition == TerminationCondition.optimal:
                st.session_state['res'] = m
                st.session_state['success'] = True
                st.session_state['utils'] = [(m.P[t]()*st.session_state['std_time']/(8*st.session_state['working_days']*m.W[t]())*100 if m.W[t]() > 0 else 0) for t in range(1, len(demand)+1)]
                
                if step["name"] != "사용자 지정 조건":
                    final_msg = f"🚨 [시스템 보정 완료] '{step['name']}' 적용으로 실행 가능한 최적해를 찾았습니다."
                    # 보정된 값을 실제 세션에 반영하여 UI 업데이트
                    for k, v in step["changes"].items(): st.session_state[k] = v
                else:
                    final_msg = "✅ 사용자 지정 조건으로 수립 완료"

                ctx_summary = f"비용:{m.cost():,.0f}, 가동률:{st.session_state['utils']}, 부재고:{sum(m.S[t]() for t in range(1,len(demand)+1))}"
                st.session_state['ai_analysis'] = get_ai_analysis(ctx_summary)
                found_solution = True
                break
        except: continue

    if found_solution:
        st.success(final_msg)
        st.toast("전략 수립 완료")
    else:
        st.error("❌ 복구 실패: 모든 파라미터 보정 및 제약 완화 시도에도 불구하고 해를 찾을 수 없습니다.")

# UI 탭 배치 및 렌더링
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
    if prompt := st.chat_input("상담 내용을 입력하세요"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            u_str = ", ".join([f"{v:.1f}%" for v in st.session_state.get('utils', [])])
            cost_val = st.session_state['res'].cost() if st.session_state['res'] else "N/A"
            res = get_ai_consultant(prompt, f"가동률:[{u_str}], 비용:{cost_val}")
            st.markdown(res); st.session_state.messages.append({"role": "assistant", "content": res})
