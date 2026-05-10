from pyomo.environ import *

def solve_production_plan(D, domain, reg, ot, h, l, inv, back, mat, sub, stime, wdays, ot_lim, w0, i0, ifinal, use_sub, max_util=100.0, min_inv=0.0):
    """S&OP 수리 모델: 잔업 생산이 실제 결과에 반영되도록 제약 조건 병목 해결"""
    m = ConcreteModel()
    T = range(1, len(D) + 1); TIME = range(0, len(D) + 1)
    
    # 결정변수 선언
    m.W = Var(TIME, domain=domain); m.H = Var(TIME, domain=domain); m.L = Var(TIME, domain=domain)
    m.P = Var(TIME, domain=domain); m.I = Var(TIME, domain=domain); m.S = Var(TIME, domain=domain)
    m.C = Var(TIME, domain=domain); m.O = Var(TIME, domain=domain)

    # 목적함수: 총 운영 비용 최소화
    m.cost = Objective(expr=sum(reg*m.W[t] + ot*m.O[t] + h*m.H[t] + l*m.L[t] + 
                                inv*m.I[t] + back*m.S[t] + mat*m.P[t] + sub*m.C[t] for t in T), sense=minimize)
    
    m.c = ConstraintList()
    m.c.add(m.W[0] == w0); m.c.add(m.I[0] == i0); m.c.add(m.S[0] == 0)
    
    for t in T:
        m.c.add(m.W[t] == m.W[t-1] + m.H[t] - m.L[t])
        
        # 정규 생산 가능량 계산 (가동률 제약 포함)
        cap_reg_allowed = (max_util / 100.0) * (1/stime) * 8 * wdays * m.W[t]
        
        # [수정] 전체 생산량(P)은 허용된 정규 캐파와 잔업 생산량의 합보다 작아야 함
        m.c.add(m.P[t] <= cap_reg_allowed + (1/stime)*m.O[t]) 
        m.c.add(m.O[t] <= ot_lim * m.W[t])
        
        m.c.add(m.I[t] == m.I[t-1] + m.P[t] + m.C[t] - D[t-1] - m.S[t-1] + m.S[t]) 
        
        if not use_sub: m.c.add(m.C[t] == 0)
        m.c.add(m.I[t] >= min_inv)

    m.c.add(m.I[len(D)] >= ifinal); m.c.add(m.S[len(D)] == 0)
    
    result = SolverFactory('glpk').solve(m)
    return m, result
