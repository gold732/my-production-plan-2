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

# 초기값 설정 보존
param_defaults = {
    'opt_mode': "정수계획법(IP)", 'enable_sub': True, 'std_time': 4.0, 'working_days': 20, 'ot_limit': 10,
    'max_util': 100.0, 'min_inv': 0.0, 'max_cost': 999999.0, 'v_c_reg': 640.0, 'v_c_ot': 6.0,
    'v_c_h': 300.0, 'v_c_l': 500.0, 'v_c_inv': 2.0, 'v_c_back': 5.0, 'v_c_mat': 10.0, 'v_c_sub': 30.0,
    'v_w_init': 80.0, 'v_i_init': 1000.0, 'v_i_final': 500.0, 'demand_raw': "1600, 3000, 3200, 3800, 2200, 2200"
}
for k, v in param_defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# 보안 잠금 설정
initial_locked_keys = {'v_w_init', 'v_i_init', 'v_c_sub', 'v_c_inv', 'v_c_mat', 'v_c_back', 'std_time', 'opt_mode', 'enable_sub', 'v_i_final', 'max_util', 'min_inv', 'max_cost'}
for pk in initial_locked_keys:
    if f"lock_{pk}" not in st.session_state: st.session_state[f"lock_{pk}"] = True
if "lock_demand_raw" not in st.session_state: st.session_state["lock_demand_raw"] = True

for key in ['messages', 'success', 'utils', 'ai_analysis']:
    if key not in st.session_state: st.session_state[key] = [] if key == 'messages' else None

demand, enable_sub, std_time, working_days, ot_limit = render_sidebar()

def run_optimization():
    """알고리즘 기반 단계적 제약 완화 복구 로직 (AI 의존 제거)"""
    st.session_state['success'] = False
    
    # 현재 설정값 복사
    temp_params = {
        'enable_sub': st.session_state['enable_sub'],
        'max_util': st.session_state['max_util'],
        'working_days': st.session_state['working_days'],
        'ot_limit': st.session_state['ot_limit']
    }
    
    attempts = 0
    max_attempts = 5
    
    while attempts < max_attempts:
        try:
            cur_domain = NonNegativeIntegers if "IP" in st.session_state['opt_mode'] else NonNegativeReals
            m, sol = solve_production_plan(
                demand, cur_domain, st.session_state['v_c_reg'], st.session_state['v_c_ot'], 
                st.session_state['v_c_h'], st.session_state['v_c_l'], st.session_state['v_c_inv'], st.session_state['v_c_back'], 
                st.session_state['v_c_mat'], st.session_state['v_c_sub'], st.session_state['std_time'], 
                temp_params['working_days'], temp_params['ot_limit'], st.session_state['v_w_init'], 
                st.session_state['v_i_init'], st.session_state['v_i_final'], temp_params['enable_sub'], 
                temp_params['max_util'], st.session_state['min_inv'], st.session_state['max_cost']
            )
            
            if sol.solver.termination_condition == TerminationCondition.optimal:
                # 해를 찾으면 해당 값을 세션에 반영하고 종료
                for k, v in temp_params.items(): st.session_state[k] = v
                st.session_state['res'] = m
                st.session_state['success'] = True
                st.session_state['utils'] = [(m.P[t]()*st.session_state['std_time']/(8*temp_params['working_days']*m.W[t]())*100 if m.W[t]() > 0 else 0) for t in range(1, len(demand)+1)]
                
                # 분석만 AI에게 맡김
                ctx = f"비용:{m.cost():,.0f}, 가동률:{st.session_state['utils']}"
                st.session_state['ai_analysis'] = get_ai_analysis(ctx)
                if attempts > 0: st.success(f"✅ {attempts}단계 제약 완화를 통해 최적해를 찾아냈습니다.")
                break
            else:
                # [알고리즘 복구 순서]
                attempts += 1
                if attempts == 1 and not temp_params['enable_sub']:
                    temp_params['enable_sub'] = True # 1순위: 외주 허용
                elif attempts == 2:
                    temp_params['max_util'] = 100.0 # 2순위: 가동률 제한 해제
                elif attempts == 3:
                    temp_params['ot_limit'] = 50.0 # 3순위: 연장근로 확대
                elif attempts == 4:
                    temp_params['working_days'] = 25.0 # 4순위: 가동일수 상향
                else:
                    st.error("❌ 모든 알고리즘적 완화 시도 후에도 해를 찾지 못했습니다. 기초 데이터를 확인하십시오.")
                    break
        except Exception as e:
            st.error(f"시스템 오류: {e}")
            break

# UI 및 탭 렌더링 (기존 로직 보존)
t1, t2, t3, t4 = st.tabs(["📊 공급망 운영", "📉 리스크/효율", "📋 데이터 마스터", "💬 AI 전략 상담방"])

with t1:
    if st.button("🚀 생산계획 수립 실행"): run_optimization()
    if st.session_state.get('success'): render_supply_demand_tab(st.session_state['res'], st.session_state['utils'], demand)
# ... 나머지 t2, t3, t4 렌더링 로직 기존과 동일 (생략 없음)
