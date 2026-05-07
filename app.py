import streamlit as st
import pandas as pd
from pyomo.environ import NonNegativeIntegers, NonNegativeReals, TerminationCondition
import plotly.graph_objects as go
import plotly.express as px

# 모듈화된 비즈니스 로직 함수 로드
from ai_consultant import get_ai_consultant, get_ai_analysis
from optimization_engine import solve_production_plan

# 1. 페이지 설정 및 디자인
st.set_page_config(page_title="AI S&OP Control Tower", layout="wide")
st.title("원예장비 제조업체 총괄생산계획 수립")

# 2. 파라미터 제어를 위한 세션 상태 양방향 초기화 구조 설계
param_keys = ['opt_mode', 'enable_sub', 'std_time', 'working_days', 'ot_limit', 
              'v_c_reg', 'v_c_ot', 'v_c_h', 'v_c_l', 'v_c_inv', 'v_c_back', 'v_c_mat', 'v_c_sub',
              'v_w_init', 'v_i_init', 'v_i_final']

if 'opt_mode' not in st.session_state: st.session_state['opt_mode'] = "정수계획법(IP)"
if 'enable_sub' not in st.session_state: st.session_state['enable_sub'] = True
if 'std_time' not in st.session_state: st.session_state['std_time'] = 4.0
if 'working_days' not in st.session_state: st.session_state['working_days'] = 20
if 'ot_limit' not in st.session_state: st.session_state['ot_limit'] = 10
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

# 각 파라미터별 고정(Lock) 제어 상태 초기화 등록
for pk in param_keys:
    if f"lock_{pk}" not in st.session_state:
        st.session_state[f"lock_{pk}"] = False
if "lock_demand_raw" not in st.session_state:
    st.session_state["lock_demand_raw"] = False

# 기존 공통 세션 상태 유지
if 'messages' not in st.session_state: st.session_state.messages = []
if 'success' not in st.session_state: st.session_state['success'] = False
if 'utils' not in st.session_state: st.session_state['utils'] = []
if 'ai_analysis' not in st.session_state: st.session_state['ai_analysis'] = None
if 'param_updated_by_ai' not in st.session_state: st.session_state['param_updated_by_ai'] = False
if 'trigger_reoptimize' not in st.session_state: st.session_state['trigger_reoptimize'] = False

# 3. 사이드바 - [고정] 체크박스를 유기적으로 결합한 멀티 컬럼 레이아웃 개편
with st.sidebar:
    st.header("🎮 시스템 제어판")
    
    c1, c2 = st.columns([3, 1])
    with c1: opt_mode = st.radio("알고리즘 선택", ["정수계획법(IP)", "선형계획법(LP)"], key="opt_mode")
    with c2: st.checkbox("고정", key="lock_opt_mode")
    domain_type = NonNegativeIntegers if "IP" in opt_mode else NonNegativeReals

    st.markdown("---")
    st.subheader("🏭 공급망 전략")
    c1, c2 = st.columns([3, 1])
    with c1: enable_sub = st.toggle("외주 하청 허용", key="enable_sub")
    with c2: st.checkbox("고정", key="lock_enable_sub")

    st.markdown("---")
    st.subheader("⏱️ 공정 효율 및 제약")
    c1, c2 = st.columns([3, 1])
    with c1: std_time = st.slider("제품당 표준 작업 시간 (Hr)", 1.0, 10.0, key="std_time")
    with c2: st.checkbox("고정", key="lock_std_time")
    
    c1, c2 = st.columns([3, 1])
    with c1: working_days = st.slider("월간 가동 일수", 1, 30, key="working_days")
    with c2: st.checkbox("고정", key="lock_working_days")
    
    c1, c2 = st.columns([3, 1])
    with c1: ot_limit = st.slider("인당 월간 초과근무 제한 (Hr)", 0, 30, key="ot_limit")
    with c2: st.checkbox("고정", key="lock_ot_limit")

    st.markdown("---")
    st.subheader("💰 운영 비용 설정 (천원)")
    cost_fields = [
        ("v_c_reg", "정규 임금 (인/월)"), ("v_c_ot", "초과 근무 수당 (Hr)"),
        ("v_c_h", "신규 고용 비용 (인)"), ("v_c_l", "해고 비용 (인)"),
        ("v_c_inv", "재고 유지비 (개/월)"), ("v_c_back", "부재고 비용 (개/월)"),
        ("v_c_mat", "재료비 (개당)"), ("v_c_sub", "외주 하청 비용 (개당)")
    ]
    for k, label in cost_fields:
        c1, c2 = st.columns([3, 1])
        with c1: st.number_input(label, key=k)
        with c2: st.checkbox("고정", key=f"lock_{k}")

    st.markdown("---")
    st.subheader("📈 초기값 및 수요")
    c1, c2 = st.columns([3, 1])
    with c1: demand_raw = st.text_input("6개월 수요 예측 (쉼표 구분)", key="demand_raw")
    with c2: st.checkbox("고정", key="lock_demand_raw")
    demand = [float(d.strip()) for d in demand_raw.split(",")]
    
    init_fields = [
        ("v_w_init", "현재 근로자 수"), ("v_i_init", "현재고 수준"), ("v_i_final", "기말 목표 재고")
    ]
    for k, label in init_fields:
        c1, c2 = st.columns([3, 1])
        with c1: st.number_input(label, key=k)
        with c2: st.checkbox("고정", key=f"lock_{k}")

# 공통 최적화 수행 함수
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
            st.session_state['enable_sub']
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
            st.error("❌ 최적해를 찾지 못했습니다.")
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
        m = st.session_state['res']
        utils = st.session_state['utils']
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("총 운영 비용", f"{m.cost():,.0f}k")
        k2.metric("평균 가동률", f"{sum(utils)/len(utils):.1f}%")
        k3.metric("인력 변동 수", f"{sum(m.H[t]() + m.L[t]() for t in range(1,len(demand)+1)):.0f}명")
        k4.metric("기말 재고량", f"{m.I[len(demand)]():,.0f}ea")

        st.subheader("📈 월별 생산/수요/재고 흐름")
        fig = go.Figure()
        fig.add_trace(go.Bar(x=list(range(1,len(demand)+1)), y=[m.P[t]() for t in range(1,len(demand)+1)], name="자체 생산", marker_color='royalblue'))
        fig.add_trace(go.Bar(x=list(range(1,len(demand)+1)), y=[m.C[t]() for t in range(1,len(demand)+1)], name="외주 하청", marker_color='lightslategray'))
        fig.add_trace(go.Scatter(x=list(range(1,len(demand)+1)), y=demand, name="예상 수요", line=dict(color='crimson', dash='dash')))
        fig.add_trace(go.Scatter(x=list(range(1,len(demand)+1)), y=[m.I[t]() for t in range(1,len(demand)+1)], name="재고 수준", yaxis="y2", line=dict(color='orange')))
        fig.update_layout(yaxis2=dict(overlaying='y', side='right'), barmode='stack', hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

        col_l, col_r = st.columns([2, 1])
        with col_l:
            st.subheader("💰 비용 세부 구성")
            
            v_c_reg = st.session_state['v_c_reg']
            v_c_inv = st.session_state['v_c_inv']
            v_c_mat = st.session_state['v_c_mat']
            v_c_sub = st.session_state['v_c_sub']
            
            costs = {
                "노무비": sum(v_c_reg*m.W[t]() for t in range(1,len(demand)+1)), 
                "재고비": sum(v_c_inv*m.I[t]() for t in range(1,len(demand)+1)), 
                "재료비": sum(v_c_mat*m.P[t]() for t in range(1,len(demand)+1)), 
                "외주비": sum(v_c_sub*m.C[t]() for t in range(1,len(demand)+1)),
                "기타": m.cost() - sum((v_c_reg*m.W[t]() + v_c_inv*m.I[t]() + v_c_mat*m.P[t]() + v_c_sub*m.C[t]()) for t in range(1,len(demand)+1))
            }
            st.plotly_chart(px.pie(names=list(costs.keys()), values=list(costs.values()), hole=0.4), use_container_width=True)
        with col_r:
            pass

        st.markdown("---")
        st.subheader("👷 월별 인력 운영 현황")
        worker_counts = [int(m.W[t]()) for t in range(1, len(demand) + 1)]
        df_worker = pd.DataFrame({"월": [f"{t}월" for t in range(1, len(demand) + 1)], "배치 인원 (명)": worker_counts})
        
        fig_worker = px.line(df_worker, x="월", y="배치 인원 (명)", markers=True, text="배치 인원 (명)", title="월별 가동 인력 변동 추이 (정밀 스케일 격자 적용)")
        fig_worker.update_traces(textposition="top center", line=dict(width=3, color="#1ABC9C"), marker=dict(size=8, symbol="circle"))
        
        w_min, w_max = min(worker_counts), max(worker_counts)
        margin = max(2, int((w_max - w_min) * 0.5)) if w_max != w_min else 5
        
        fig_worker.update_layout(yaxis=dict(range=[w_min - margin, w_max + margin], dtick=1, title="인원 수 (명)"), xaxis=dict(title="분석 대상 월"), hovermode="x unified")
        st.plotly_chart(fig_worker, use_container_width=True)

with tab2:
    if st.session_state.get('success'):
        utils = st.session_state['utils']
        st.subheader("⚠️ 운영 리스크 분석 (가동률)")
        fig_risk = px.area(x=list(range(1,len(demand)+1)), y=utils, title="生産 가동률 추이 (%)", markers=True)
        fig_risk.add_hline(y=100, line_dash="dot", line_color="red", annotation_text="위험(100%)", annotation_position="bottom right")
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
            
            # [신설]: AI가 출력한 특수 텍스트 명령줄을 감지하여 가드레일을 체크하는 결정론적 파서 레이어
            cleaned_res = ai_res
            lines = ai_res.split('\n')
            for line in lines:
                if "[UPDATE_PARAM:" in line and "]" in line:
                    try:
                        # 태그 파싱: 예) [UPDATE_PARAM: v_c_reg=1000]
                        cmd = line.split("[UPDATE_PARAM:")[1].split("]")[0].strip()
                        if "=" in cmd:
                            k_name, v_val = cmd.split("=", 1)
                            k_name = k_name.strip()
                            v_val = v_val.strip()
                            
                            # 대시보드 고정 체크박스 상태 교차 검증 (보안벽)
                            if not st.session_state.get(f"lock_{k_name}", False):
                                if k_name == 'enable_sub':
                                    st.session_state[k_name] = v_val.lower() in ['true', '1', 'yes', 'on']
                                elif k_name in ['opt_mode', 'demand_raw']:
                                    st.session_state[k_name] = str(v_val)
                                else:
                                    st.session_state[k_name] = float(v_val)
                                st.session_state['param_updated_by_ai'] = True
                        
                        # 대화창 UI에 원형 원격 조작 명령어가 보이지 않도록 필터링 클렌징
                        cleaned_res = cleaned_res.replace(line, "")
                    except Exception:
                        pass
            
            st.markdown(cleaned_res.strip())
            st.session_state.messages.append({"role": "assistant", "content": cleaned_res.strip()})
            
        if st.session_state['param_updated_by_ai']:
            st.session_state['param_updated_by_ai'] = False
            st.session_state['trigger_reoptimize'] = True
            st.rerun()

