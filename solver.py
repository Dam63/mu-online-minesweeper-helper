"""Solveur de demineur par enumeration exacte (composantes connexes + contrainte du nombre total de bombes)."""
from math import comb

CLOSED, FLAG = "#", "F"
FLAGS = (FLAG, "B")  # drapeau ou bombe revelee: compte comme bombe connue


def neighbors(r, c, R, C):
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if (dr or dc) and 0 <= r + dr < R and 0 <= c + dc < C:
                yield r + dr, c + dc


def _enumerate(vars_, cons):
    """Enumere les affectations d'une composante. Retourne {k: (nb_solutions, [mines_par_var])}."""
    idx = {v: i for i, v in enumerate(vars_)}
    cons = [([idx[v] for v in vs], need) for vs, need in cons]
    by_var = [[] for _ in vars_]
    for ci, (vs, _) in enumerate(cons):
        for v in vs:
            by_var[v].append(ci)
    mines = [0] * len(cons)
    left = [len(vs) for vs, _ in cons]
    # variables les plus contraintes d'abord
    order = sorted(range(len(vars_)), key=lambda i: -len(by_var[i]))
    assign = [0] * len(vars_)
    out = {}

    def rec(pos, k):
        if pos == len(order):
            n, cnt = out.setdefault(k, [0, [0] * len(vars_)])
            out[k][0] += 1
            for i, a in enumerate(assign):
                if a:
                    cnt[i] += 1
            return
        v = order[pos]
        for val in (0, 1):
            ok = True
            for ci in by_var[v]:
                mines[ci] += val
                left[ci] -= 1
            for ci in by_var[v]:
                need = cons[ci][1]
                if mines[ci] > need or mines[ci] + left[ci] < need:
                    ok = False
                    break
            if ok:
                assign[v] = val
                rec(pos + 1, k + val)
            assign[v] = 0
            for ci in by_var[v]:
                mines[ci] -= val
                left[ci] += 1

    rec(0, 0)
    return out


def _convolve(a, b):
    res = {}
    for ka, wa in a.items():
        for kb, wb in b.items():
            res[ka + kb] = res.get(ka + kb, 0) + wa * wb
    return res


def solve(grid, mines_left=None, ignore=()):
    """grid: liste de listes de str ('#' fermee, 'F' drapeau, '.' vide, '1'..'8').
    ignore: cases a ne jamais proposer comme pari.
    mines_left: bombes restantes parmi les cases fermees non marquees (None = inconnu).
    Retourne dict(prob, safe, mines, best, warning)."""
    R, C = len(grid), len(grid[0])
    closed = [(r, c) for r in range(R) for c in range(C) if grid[r][c] == CLOSED]
    warning = None
    cons_map = {}
    for r in range(R):
        for c in range(C):
            ch = grid[r][c]
            if not ch.isdigit() or ch == "0":
                continue
            vs = tuple(p for p in neighbors(r, c, R, C) if grid[p[0]][p[1]] == CLOSED)
            flags = sum(1 for p in neighbors(r, c, R, C) if grid[p[0]][p[1]] in FLAGS)
            need = int(ch) - flags
            if not vs:
                continue
            if need < 0 or need > len(vs):
                return {"prob": {}, "safe": [], "mines": [], "best": None, "warning": "plateau incoherent en (%d,%d)" % (r, c)}
            cons_map[vs] = need
    cons = list(cons_map.items())

    # composantes connexes
    parent = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for vs, _ in cons:
        for v in vs[1:]:
            parent[find(v)] = find(vs[0])
    comps = {}
    for vs, need in cons:
        comps.setdefault(find(vs[0]), []).append((vs, need))

    comp_data = []  # (vars, {k: (n, cnt)})
    for group in comps.values():
        vars_ = sorted({v for vs, _ in group for v in vs})
        res = _enumerate(vars_, group)
        if not res:
            return {"prob": {}, "safe": [], "mines": [], "best": None, "warning": "aucune solution (lecture erronee ?)"}
        comp_data.append((vars_, res))

    frontier = {v for vars_, _ in comp_data for v in vars_}
    n_other = len(closed) - len(frontier)
    other = [p for p in closed if p not in frontier]

    def total_ways(excl=None):
        dist = {0: 1}
        for j, (_, res) in enumerate(comp_data):
            if j != excl:
                dist = _convolve(dist, {k: v[0] for k, v in res.items()})
        return dist

    def weight(K):
        if mines_left is None:
            return 1
        m = mines_left - K
        return comb(n_other, m) if 0 <= m <= n_other else 0

    full = total_ways()
    Z = sum(w * weight(K) for K, w in full.items())
    if Z == 0 and mines_left is not None:
        warning = "nombre de bombes restantes incoherent, ignore"
        mines_left = None
        Z = sum(full.values())

    prob = {}
    for j, (vars_, res) in enumerate(comp_data):
        rest = total_ways(j)
        num = [0] * len(vars_)
        for kj, (_, cnt) in res.items():
            w = sum(wr * weight(kj + kr) for kr, wr in rest.items())
            for i in range(len(vars_)):
                num[i] += cnt[i] * w
        for i, v in enumerate(vars_):
            prob[v] = num[i] / Z
    if other:
        if mines_left is not None:
            exp = sum(w * weight(K) * (mines_left - K) for K, w in full.items()) / Z
            p = exp / n_other
        else:
            p = None
        for v in other:
            prob[v] = p

    safe = sorted(v for v, p in prob.items() if p == 0)
    mines = sorted(v for v, p in prob.items() if p == 1)
    best = None
    if not safe:
        cand = [(p, len(list(neighbors(v[0], v[1], R, C))), v) for v, p in prob.items() if p is not None and p < 1 and v not in ignore]
        if cand:
            # proba minimale; a egalite, moins de voisins (coins) = plus de chances d'ouvrir une zone vide
            best = min(cand)[2]
    return {"prob": prob, "safe": safe, "mines": mines, "best": best, "warning": warning}

