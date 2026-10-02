import itertools, random
from solver import solve, neighbors
from math import isclose

def brute(grid, M):
    R,C=len(grid),len(grid[0])
    closed=[(r,c) for r in range(R) for c in range(C) if grid[r][c]=='#']
    cnt=0; tot={v:0 for v in closed}
    for combo in itertools.combinations(closed,M):
        s=set(combo); ok=True
        for r in range(R):
            for c in range(C):
                ch=grid[r][c]
                if ch.isdigit() and ch!='0':
                    if sum(1 for p in neighbors(r,c,R,C) if p in s)!=int(ch): ok=False;break
            if not ok:break
        if ok:
            cnt+=1
            for v in s: tot[v]+=1
    return {v:t/cnt for v,t in tot.items()} if cnt else None

random.seed(1)
for t in range(60):
    R,C=4,5
    mines=set(random.sample([(r,c) for r in range(R) for c in range(C)],random.randint(2,6)))
    opened=set(random.sample([(r,c) for r in range(R) for c in range(C) if (r,c) not in mines],random.randint(2,8)))
    g=[['#']*C for _ in range(R)]
    for (r,c) in opened:
        n=sum(1 for p in neighbors(r,c,R,C) if p in mines); g[r][c]=str(n) if n else '.'
    M=len(mines)
    b=brute(g,M); s=solve(g,M)['prob']
    assert b is not None
    for v in b: assert isclose(b[v],s[v],abs_tol=1e-9),(g,v,b[v],s[v])
print('ok vs brute force')
import reader, cv2
res=reader.read_board(cv2.imread('assets/ref.png'))
s=solve(res['grid'],int(res['remaining']))
print('safe',s['safe'],'mines',s['mines'],'best',s['best'],s['prob'][s['best']] if s['best'] else None)
