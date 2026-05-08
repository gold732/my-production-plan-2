import streamlit as st
from pyomo.environ import TerminationCondition, NonNegativeIntegers, NonNegativeReals
import copy

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

# AI 자동 수정을 위한 버퍼 처리
if st.session_state.get('pending_updates'):
    for pk, pval in st.session_state['pending_updates'].items(): st.session_state[pk] = pval
    st.session_state['pending_updates'] = {}; st.session_state['trigger_reoptimize'] = True

# 2. 보안 잠금(Lock) 초기 설정
initial_locked_keys = {
    'v_w_init', 'v_i_init', 'v_c_sub', 'v_c_inv', 'v_c_mat', 'v_c_back', 
    'std_time', 'opt_mode', 'enable_sub', 'v_i_final', 'max_util', 'min_inv', 'max_cost'
}
for pk in initial_locked_keys:
    if f"lock_{pk}" not in st.session_state: st.session_state[f"lock_{pk}"] = True
if "lock_demand_raw" not in st.session_state: st.session_state["lock_demand_raw"] = True

# 상태값 초기화
for key in ['messages', 'success', 'utils', 'trigger_reoptimize', 'ai_analysis']:
    if key not in st.session_state: st.session_state[key] = [] if key == 'messages' else None

# 3. 사이드바 렌더링
demand, enable_sub, std_time, working_days, ot_limit = render_sidebar()

def run_optimization():
    """제약 완화 메커니즘이 포함된 고성능 최적화 실행 엔진"""
    st.session_state['success'] = False
    
    # [계층적 제약 완화 시나리오 정의]
    relaxation_steps = [
        {"name": "사용자 지정 조건", "changes": {}},
        {"name": "가동률 제한 해제 (100%)", "changes": {"max_util": 100.0}},
        {"name": "예산 제약 해제", "changes": {"max_cost": 99999999.0}},
        {"name": "최소 유지 재고 제약 해제", "changes": {"min_inv": 0.0}},
        {"name": "외주 하청 강제 허용", "changes": {"enable_sub": True}},
        {"name": "연장 근로 한도 확장 (+20Hr)", "changes": {"ot_limit": st.session_state['ot_limit'] + 20}}
    ]

    found_solution = False
    current_params = {
        "max_util": st.session_state['max_util'],
        "max_cost": st.session_state['max_cost'],
        "min_inv": st.session_state['min_inv'],
        "enable_sub": st.session_state['enable_sub'],
        "ot_limit": st.session_state['ot_limit']
    }

    for step in relaxation_steps:
        # 시도할 파라미터 업데이트
        for k, v in step["changes"].items():
            current_params[k] = v

        try:
            cur_domain = NonNegativeIntegers if "IP" in st.session_state['opt_mode'] else NonNegativeReals
            m, sol = solve_production_plan(
                demand, cur_domain, st.session_state['v_c_reg'], st.session_state['v_c_ot'], 
                st.session_state['v_c_h'], st.session_state['v_c_l'], st.session_state['v_c_inv'], st.session_state['v_c_back'], 
                st.session_state['v_c_mat'], st.session_state['v_c_sub'], st.session_state['std_time'], st.session_state['working_days'], 
                current_params['ot_limit'], st.session_state['v_w_init'], st.session_state['v_i_init'], st.session_state['v_i_final'], 
                current_params['enable_sub'], current_params['max_util'], current_params['min_inv'], current_params['max_cost']
            )

            if sol.solver.termination_condition == TerminationCondition.optimal:
                # 최적해 발견 시 상태 업데이트 및 루프 종료
                st.session_state['res'] = m
                st.session_state['success'] = True
                st.session_state['utils'] = [(m.P[t]()*st.session_state['std_time']/(8*st.session_state['working_days']*m.W[t]())*100 if m.W[t]() > 0 else 0) for t in range(1, len(demand)+1)]
                
                # 만약 완화가 일어났다면 세션 상태 반영 및 알림
                if step["name"] != "사용자 지정 조건":
                    st.warning(f"🚨 [시스템 복구] {step['name']} 단계를 통해 해를 찾았습니다.")
                    for k, v in step["changes"].items():
                        st.session_state[k] = v
                
                # 비현실적 가동률 체크
                if any(u >= 99.9 for u in st.session_state['utils']):
                    st.warning("⚠️ 주의: 가동률이 한계치에 도달했습니다. 생산 지연 리스크가 높습니다.")

                ctx_summary = f"비용:{m.cost():,.0f}, 가동률:{st.session_state['utils']}, 부재고:{sum(m.S[t]() for t in range(1,len(demand)+1))}"
                st.session_state['ai_analysis'] = get_ai_analysis(ctx_summary)
                st.toast(f"✅ {step['name']}으로 수립 완료")
                found_solution = True
                break

        except Exception as e:
            st.error(f"⚠️ 연산 엔진 오류 ({step['name']}): {str(e)}")
            break

    if not found_solution:
        st.error("❌ 복구 실패: 모든 제약 완화 시도에도 불구하고 해를 찾을 수 없습니다. 기초 데이터(수요, 초기재고 등)를 확인하십시오.")

if st.session_state.get('trigger_reoptimize'):
    st.session_state['trigger_reoptimize'] = False; run_optimization()

# 4. 4단 전문 탭 UI 배치
t1, t2, t3, t4 = st.tabs(["📊 공급망 운영", "📉 리스크/효율", "📋 데이터 마스터", "💬 AI 전략 상담방"])

with t1:
    if st.button("🚀 생산계획 수립 실행"): run_optimization()
    if st.session_state.get('success'):
        render_supply_demand_tab(st.session_state['res'], st.session_state['utils'], demand)

with t2:
    if st.session_state.get('success'):
        render_risk_efficiency_tab(st.session_state['res'], st.session_state['utils'], demand)

with t3:
    if st.session_state.get('success'):
        render_data_master_tab(st.session_state['res'], st.session_state['utils'], demand)

with t4:
    st.subheader("💬 AI 전략 상담방")
    if st.button("🧹 초기화"): st.session_state.messages = []; st.rerun()
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])
    if prompt := st.chat_input("의사결정에 필요한 조언을 구하세요"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            u_str = ", ".join([f"{v:.1f}%" for v in st.session_state['utils']]) if st.session_state['utils'] else "N/A"
            res_cost = st.session_state['res'].cost() if st.session_state['res'] else 'N/A'
            ctx = f"가동률:[{u_str}] | 비용:{res_cost}"
            res = get_ai_consultant(prompt, ctx)
            st.markdown(res); st.session_state.messages.append({"role": "assistant", "content": res})
        if st.session_state.get('param_updated_by_ai'):
            st.session_state['param_updated_by_ai'] = False; st.rerun()
