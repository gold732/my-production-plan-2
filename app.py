import streamlit as st
from pyomo.environ import TerminationCondition, NonNegativeIntegers, NonNegativeReals

from ai_consultant import get_ai_consultant, get_ai_analysis
from optimization_engine import solve_production_plan
from ui_components import render_sidebar, render_metrics_and_charts, render_risk_analysis

st.set_page_config(page_title="AI S&OP Control Tower", layout="wide")
st.title("원예장비 제조업체 총괄생산계획 수립")

param_keys = ['opt_mode', 'enable_sub', 'std_time', 'working_days', 'ot_limit', 'max_util', 'min_inv', 'max_cost',
              'v_c_reg', 'v_c_ot', 'v_c_h', 'v_c_l', 'v_c_inv', 'v_c_back', 'v_c_mat', 'v_c_sub',
              'v_w_init', 'v_i_init', 'v_i_final']

if 'pending_updates' not in st.session_state: 
    st.session_state['pending_updates'] = {}

if st.session_state['pending_updates']:
    for pk, pval in st.session_state['pending_updates'].items():
        st.session_state[pk] = pval
    st.session_state['pending_updates'] = {}
    st.session_state['trigger_reoptimize'] = True

if 'opt_mode' not in st.session_state: st.session_state['opt_mode'] = "정수계획법(IP)"
if 'enable_sub' not in st.session_state: st.session_state['enable_sub'] = True
if 'std_time' not in st.session_state: st.session_state['std_time'] = 4.0
if 'working_days' not in st.session_state: st.session_state['working_days'] = 20
if 'ot_limit' not in st.session_state: st.session_state['ot_limit'] = 10
if 'max_util' not in st.session_state: st.session_state['max_util'] = 100.0
if 'min_inv' not in st.session_state: st.session_state['min_inv'] = 0.0
if 'max_cost' not in st.session_state: st.session_state['max_cost'] = 99999999.0
if 'v_c_reg' not in st.session_state: st.session_state['v_c_reg'] = 640
if 'v_c_ot' not in st.session_state: st.session_state['v_c_ot'] = 6
if 'v_c_h' not in st.session_state: st.session_state['v_c_h'] = 300
if 'v_c_l' not in st.session_state: st.session_state['v_c_l'] = 500
if 'v_c_inv' not in st.session_state: st.session_state['v_c_inv'] = 2
if 'v_c_back' not in st.session_state: st.session_state['v_c_back'] = 5
if 'v_c_mat' not in st.session_state: st.session_state['v_c_mat'] = 10
if 'v_c_sub' not in st.session_state: st.session_state['v_c_sub'] = 30
if 'demand_raw' not in st.session_state: st.session_state['demand_raw'] = "1600, 3000, 3200, 3800, 2200, 2200"
if 'v_w_init' not in st.session_state: st.session_state['v_w_init'] = 80
if 'v_i_init' not in st.session_state: st.session_state['v_i_init'] = 1000
if 'v_i_final' not in st.session_state: st.session_state['v_i_final'] = 500

# [🚨 변경] 사용자의 요구사항에 따라 지정된 변수들을 초기 잠금 명부에 추가 주입 완료
initial_locked_keys = {
    'v_w_init', 'v_i_init', 'v_c_sub', 'v_c_inv', 
    'v_c_mat', 'v_c_back', 'std_time', 'opt_mode', 'enable_sub',
    'v_i_final', 'max_util', 'min_inv', 'max_cost'
}

for pk in param_keys:
    if f"lock_{pk}" not in st.session_state: 
        st.session_state[f"lock_{pk}"] = (pk in initial_locked_keys)
        
# [🚨 변경] 수요 예측 텍스트 인풋 필드도 초기 구동 시 강제 고정(True) 상태로 설정
if "lock_demand_raw" not in st.session_state:
    st.session_state["lock_demand_raw"] = True

if 'messages' not in st.session_state: st.session_state.messages = []
if 'success' not in st.session_state: st.session_state['success'] = False
if 'utils' not in st.session_state: st.session_state['utils'] = []
if 'ai_analysis' not in st.session_state: st.session_state['ai_analysis'] = None
if 'param_updated_by_ai' not in st.session_state: st.session_state['param_updated_by_ai'] = False
if 'trigger_reoptimize' not in st.session_state: st.session_state['trigger_reoptimize'] = False

demand, enable_sub, std_time, working_days, ot_limit = render_sidebar()

def run_optimization_process():
    st.session_state['success'] = False
    st.session_state['ai_analysis'] = None
    try:
        current_demand = [float(d.strip()) for d in st.session_state['demand_raw'].split(",")]
        current_domain = NonNegativeIntegers if "IP" in st.session_state['opt_mode'] else NonNegativeReals
        
        model, sol = solve_production_plan(
            current_demand, current_domain, 
            st.session_state['v_c_reg'], st.session_state['v_c_ot'], 
            st.session_state['v_c_h'], st.session_state['v_c_l'], 
            st.session_state['v_c_inv'], st.session_state['v_c_back'], 
            st.session_state['v_c_mat'], st.session_state['v_c_sub'], 
            st.session_state['std_time'], st.session_state['working_days'], 
            st.session_state['ot_limit'], st.session_state['v_w_init'], 
            st.session_state['v_i_init'], st.session_state['v_i_final'], 
            st.session_state['enable_sub'], st.session_state['max_util'], st.session_state['min_inv'], st.session_state['max_cost']
        )
        if sol.solver.termination_condition == TerminationCondition.optimal:
            st.session_state['res'] = model
            st.session_state['success'] = True
            
            temp_utils = []
            for t in range(1, len(current_demand) + 1):
                denom = 8 * st.session_state['working_days'] * model.W[t]()
                temp_utils.append((model.P[t]() * st.session_state['std_time'] / denom * 100) if denom > 0 else 0)
            st.session_state['utils'] = temp_utils
            
            u_str = ", ".join([f"{i+1}월:{val:.1f}%" for i, val in enumerate(temp_utils)])
            ctx_summary = f"총비용:{model.cost():,.0f}, 가동률:[{u_str}], 외주허용:{st.session_state['enable_sub']}"
            st.session_state['ai_analysis'] = get_ai_analysis(ctx_summary)
            st.toast("✅ 최적화 성공 및 AI 분석 완료!")
        else:
            st.error("❌ 최적해를 찾지 못했습니다. 비용 한도(max_cost) 및 안전 가드 제약이 너무 엄격한지 검토하십시오.")
    except Exception as e:
        st.error(f"⚠️ 오류: {str(e)}")

if st.session_state['trigger_reoptimize']:
    st.session_state['trigger_reoptimize'] = False
    run_optimization_process()

tab1, tab2, tab3 = st.tabs(["📊 운영 대시보드", "📉 리스크/효율 분석", "💬 AI 전략 상담방"])

with tab1:
    if st.button("🚀 최적 생산계획 수립 실행"):
        run_optimization_process()

    if st.session_state.get('success') and st.session_state.get('ai_analysis'):
        st.markdown("### 🤖 AI 전문 컨설턴트 종합 진단 보고서")
        analysis = st.session_state['ai_analysis']
        c_light, c_desc = st.columns([1, 4])
        with c_light:
            st.metric("운영 리스크 등급", analysis.get("risk_level", "🟡 주의"))
            st.metric("최대 병목 월", analysis.get("bottleneck_month", "없음"))
        with c_desc:
            st.info(f"**📋 핵심 종합 브리핑**\n\n{analysis.get('summary', '')}")
            st.warning(f"**💡 자원 최적화 권고사항**\n\n{analysis.get('recommendation', '')}")
        st.markdown("---")

    if st.session_state.get('success'):
        render_metrics_and_charts(st.session_state['res'], st.session_state['utils'], demand)

with tab2:
    if st.session_state.get('success'):
        render_risk_analysis(st.session_state['utils'], demand)

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
            base_ctx = f"총비용:{m.cost():,.0f}, 가동률:[{u_str}]"
        else:
            base_ctx = "데이터 없음"

        p_status = []
        for pk in param_keys:
            val = st.session_state.get(pk)
            is_locked = st.session_state.get(f"lock_{pk}", False)
            p_status.append(f"'{pk}': 현재값={val}(상태={'고정됨-변경불가' if is_locked else '변경가능'})")
        
        ctx = f"{base_ctx} | 실시간 파라미터 락 명세서: [{', '.join(p_status)}]"

        with st.chat_message("assistant"):
            ai_res = get_ai_consultant(prompt, ctx)
            st.markdown(ai_res)
            st.session_state.messages.append({"role": "assistant", "content": ai_res})
            
        if st.session_state.get('param_updated_by_ai', False):
            st.session_state['param_updated_by_ai'] = False
            st.rerun()
