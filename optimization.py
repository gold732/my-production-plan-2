from pyomo.environ import *

def solve_production_plan(D, domain, reg, ot, h, l, inv, back, mat, sub, stime, wdays, ot_lim, w0, i0, ifinal, use_sub):
    """
    기존의 모든 제약 조건을 유지하며 최적화 계산을 수행하는 엔진
    """
    m = ConcreteModel()
    T = range(1, len(D) + 1)
    TIME = range(0, len(D) + 1)
    
    # 변수 정의
    m.W = Var(TIME, domain=domain)
    m.H = Var(TIME, domain=domain)
    m.L = Var(TIME, domain=domain)
    m.P = Var(TIME, domain=domain)
    m.I = Var(TIME, domain=domain)
    m.S = Var(TIME, domain=domain)
    m.C = Var(TIME, domain=domain)
    m.O = Var(TIME, domain=domain)

    # 목적함수: 모든 비용의 합 최소화
    m.cost = Objective(expr=sum(
        reg*m.W[t] + ot*m.O[t] + h*m.H[t] + l*m.L[t] + 
        inv*m.I[t] + back*m.S[t] + mat*m.P[t] + sub*m.C[t] 
        for t in T), sense=minimize)
    
    m.c = ConstraintList()
    
    # 초기값 제약
    m.c.add(m.W[0] == w0)
    m.c.add(m.I[0] == i0)
    m.c.add(m.S[0] == 0)
    
    for t in T:
        # 인력 수급 밸런스
        m.c.add(m.W[t] == m.W[t-1] + m.H[t] - m.L[t])
        
        # 생산 가능 용량 (정규 + 초과근무)
        cap_reg = (1/stime) * 8 * wdays * m.W[t]
        m.c.add(m.P[t] <= cap_reg + (1/stime)*m.O[t]) 
        
        # 재고 및 물동량 밸런스
        m.c.add(m.I[t] == m.I[t-1] + m.P[t] + m.C[t] - D[t-1] - m.S[t-1] + m.S[t]) 
        
        # 초과근무 한도 제약
        m.c.add(m.O[t] <= ot_lim * m.W[t])
        
        # 외주 하청 On/Off 제약
        if not use_sub:
            m.c.add(m.C[t] == 0)

    # 기말 조건
    m.c.add(m.I[len(D)] >= ifinal)
    m.c.add(m.S[len(D)] == 0)
    
    # GLPK 솔버 호출
    try:
        solver = SolverFactory('glpk')
        result = solver.solve(m)
        return m, result
    except Exception as e:
        return None, str(e)
