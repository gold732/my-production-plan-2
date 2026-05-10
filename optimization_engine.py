from pyomo.environ import *

def solve_production_plan(D, domain, reg, ot, h, l, inv, back, mat, sub, stime, wdays, ot_lim, w0, i0, ifinal, use_sub, max_util=100.0, min_inv=0.0):
    """
    S&OP 수리 모델: 
    max_util은 '정규 시간'의 생산 가능 범위만 제한하며, 
    이를 초과하는 수요는 잔업(O) 또는 외주(C)를 통해 해결하도록 설계됨.
    """
    m = ConcreteModel()
    T = range(1, len(D) + 1); TIME = range(0, len(D) + 1)
    
    m.W = Var(TIME, domain=domain); m.H = Var(TIME, domain=domain); m.L = Var(TIME, domain=domain)
    m.P = Var(TIME, domain=domain); m.I = Var(TIME, domain=domain); m.S = Var(TIME, domain=domain)
    m.C = Var(TIME, domain=domain); m.O = Var(TIME, domain=domain)

    m.cost = Objective(expr=sum(reg*m.W[t] + ot*m.O[t] + h*m.H[t] + l*m.L[t] + 
                                inv*m.I[t] + back*m.S[t] + mat*m.P[t] + sub*m.C[t] for t in T), sense=minimize)
    
    m.c = ConstraintList()
    m.c.add(m.W[0] == w0); m.c.add(m.I[0] == i0); m.c.add(m.S[0] == 0)
    
    for t in T:
        m.c.add(m.W[t] == m.W[t-1] + m.H[t] - m.L[t])
        
        # 정규 생산 가용량 (사용자가 설정한 가동률 버퍼 반영)
        cap_reg_allowed = (max_util / 100.0) * (1/stime) * 8 * wdays * m.W[t]
        
        # 생산 제약: P = (정규 시간 생산) + (잔업 생산)
        # 가동률 제약(max_util)은 오직 정규 시간 생산분에만 영향을 줌
        m.c.add(m.P[t] <= cap_reg_allowed + (1/stime)*m.O[t]) 
        m.c.add(m.O[t] <= ot_lim * m.W[t])
        
        m.c.add(m.I[t] == m.I[t-1] + m.P[t] + m.C[t] - D[t-1] - m.S[t-1] + m.S[t]) 
        
        if not use_sub: m.c.add(m.C[t] == 0)
        m.c.add(m.I[t] >= min_inv)

    m.c.add(m.I[len(D)] >= ifinal); m.c.add(m.S[len(D)] == 0)
    
    result = SolverFactory('glpk').solve(m)
    return m, result
