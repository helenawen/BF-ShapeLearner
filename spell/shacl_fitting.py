import time
from enum import Enum
from typing import NamedTuple, Union
from pysat.card import CardEnc, EncType
from pysat.solvers import Glucose4, pysolvers

from .structures import (
    RoleAtom,
    Signature,
    Structure,
    conceptname_ext,
    conceptnames,
    generate_all_trees,
    ind,
    restrict_to_neighborhood,
    rolenames,
    solution2sparql,
)

# TODO:
# Documentation! of final clauses and variables for Cardinality Restrictions
# add inverses r- (whenever I consider successors now, I also need to consider predecessors for inverse roles)
# add reachability r*
# add closed (SHACL constraint)
# output SHACL shape instead of SPARQL query)


mode = Enum("mode", "exact neg_approx full_approx")

# --- CREATE DATA STRUCTURES AND VARIABLES ---
HC = dict[str, list[int]]  # [cn][pInd]
Edge = list[dict[int, int]]  # [i][j] (pi, is_ex, is_num)
Pr = dict[RoleAtom, list[int]]  # [rn][pInd]
Defect = list[list[list[int]]]  # [i][j][a] (defect, ex_def, num_def)
Simul = list[list[int]]  # [pInd][a]
SimulNum = list[list[dict[RoleAtom, list[int]]]]  # [j][a][rn][n]
NumBound = list[list[int]]
Op = list[int]


class Variables(NamedTuple):
    # Structure
    pi: Edge  # HW: = variable yi,j in paper
    pr: Pr  # HW: variable xj,r in paper
    hc: HC  # HW: = variable ci,a in paper
    is_ex: Edge
    is_num: Edge
    # Simulation
    simul: Simul  # HW: = variable si,a in paper
    num_sim_geq: SimulNum
    num_sim_leq: SimulNum
    op_geq: Op
    op_leq: Op
    num_bound: NumBound
    # Defects
    defect: Defect
    ex_def: Defect
    num_def: Defect
    #bound for cardinality restrictions
    n_max: int


var_counter = 1


# --- HELPER FUNCTIONS ---
def complement_type(tp, sigma: Signature):
    return tuple(cn for cn in conceptnames(sigma) if cn not in tp)


def compute_types(A: Structure, sigma: Signature):
    types: list[list[str]] = [[] for a in ind(A)]
    for cn in conceptnames(sigma):
        for a in conceptname_ext(A, cn):
            types[a].append(cn)

    fixed_types = {tuple(tp) for tp in types}
    fixed_types = list(fixed_types)
    fixed_types.sort(key="{}".format)
    fixed_types = list(map(frozenset, fixed_types))

    tp_map = {tp: idx for idx, tp in enumerate(fixed_types)}
    anti_types = {idx: complement_type(tp, sigma) for tp, idx in tp_map.items()}

    ind_tp_idx = [tp_map[frozenset(types[a])] for a in ind(A)]

    return ind_tp_idx, anti_types


def compute_role_fillers(sigma: Signature, A: Structure):
    fillers: dict[RoleAtom, dict[int, set[int]]] = {}
    for rn in rolenames(sigma):
        fillers[rn] = {a: set() for a in ind(A)}

    for a in ind(A):
        for b, rn in A.rn_ext[a]:
            if rn in rolenames(sigma):
                fillers[rn][a].add(b)
    return fillers


def compute_all_successors_by_individuals(A: Structure):
    succs_of_ind: dict[int, set[int]] = {}
    for a in ind(A):
        succs_of_ind[a] = set()
        for b, rn in A.rn_ext[a]:
            succs_of_ind[a].add(b)
    return succs_of_ind

def compute_n_max(sigma: Signature, A: Structure):
    fillers = compute_role_fillers(sigma, A);
    max_count = 0
    for rn in rolenames(sigma):
        for a in ind(A):
            max_count = max(max_count, len(fillers[rn][a]))
    return max_count

# --- CREATE VARIABLES ---

def fresh_var():
    global var_counter
    r = var_counter
    var_counter = var_counter + 1
    return r


def create_variables(size: int, sigma: Signature, A: Structure) -> Variables:
    global var_counter
    var_counter = 1

    # number bound
    n_max = compute_n_max(sigma, A)
    print("N_MAX: ", n_max)

    # pi[i][j] is true if there is an edge between i and j
    pi = [
        {pInd2: fresh_var() for pInd2 in range(pInd1 + 1, size)}
        for pInd1 in range(size)
    ]

    # pr[rn][i] is true if product ind i has an incoming rn role
    pr = {rn: [fresh_var() for pInd in range(size)] for rn in rolenames(sigma)}

    # Conceptnames of product individuals
    hc = {cn: [fresh_var() for pInd in range(size)] for cn in conceptnames(sigma)}

    # EDGE TYPE HANDLING
    # each edge can either be interpreted as an existential restriction (original) or a number restriction
    # is_ex[i][j], is_num[i][j] is true if there is an edge between i and j which is interpreted as existential or number restriction respectively, false otherwise
    is_ex = [
        {pInd2: fresh_var() for pInd2 in range(pInd1 + 1, size)}
        for pInd1 in range(size)
    ]

    is_num = [
        {pInd2: fresh_var() for pInd2 in range(pInd1 + 1, size)}
        for pInd1 in range(size)
    ]

    # Simulation variables
    simul = [[fresh_var() for a in ind(A)] for i in range(size)]
    num_sim_geq = [[{rn: [fresh_var() for n in range(1, n_max + 1)] for rn in rolenames(sigma)} for _ in ind(A)] for j
                   in range(size)]
    num_sim_leq = [[{rn: [fresh_var() for n in range(1, n_max + 1)] for rn in rolenames(sigma)} for _ in ind(A)] for j
                   in range(size)]
    op_geq = [fresh_var() for j in range(size)]
    op_leq = [fresh_var() for j in range(size)]
    num_bound = [[fresh_var() for n in range(1, n_max + 1)] for j in range(size)]

    # Defect variables
    defect = [[[fresh_var() for a in ind(A)] for j in range(size)] for i in range(size)]
    ex_def = [[[fresh_var() for a in ind(A)] for j in range(size)] for i in range(size)]
    num_def = [[[fresh_var() for a in ind(A)] for j in range(size)] for i in range(size)]

    return Variables(pi, pr, hc, is_ex, is_num, simul, num_sim_geq, num_sim_leq, op_geq, op_leq,
                     num_bound, defect, ex_def, num_def, n_max)


# --- CREATE CLAUSES NEEDED FOR ENCODING ---
# creates the clauses needed to ensure correct structure of query
def query_structure_constraints(size: int, sigma: Signature, v: Variables):
    pi = v.pi
    pr = v.pr

    if size > 0 and size < 10:
        ktrees = list(generate_all_trees(size))

        treechoice = [fresh_var() for tree in ktrees]
        # At least one tree
        yield treechoice

        if size < 14:
            # At most one tree. Skip this if size gets too large, since it grows quadratically in the number of trees
            for j in range(0, len(ktrees)):
                for i in range(j):
                    yield (-treechoice[i], -treechoice[j])

        for t in range(len(ktrees)):
            tree = ktrees[t]
            for j in range(1, size):
                for i in range(j):
                    if tree[j - 1] == i:
                        yield (-treechoice[t], pi[i][j])
                    else:
                        yield (-treechoice[t], -pi[i][j])

            #yield from subtree_label_symmetry_breaking(t, tree, size, sigma, v, treechoice[t])


    # Every pInd has at least a predecessor HW: paper (1)
    for j in range(1, size):
        yield [pi[i][j] for i in range(j)]

    # Every pInd has at most one predecessor HW: paper (2)
    for j in range(1, size):
        for i1 in range(j):
            for i2 in range(i1):
                yield [-pi[i1][j], -pi[i2][j]]

    # Every pind has at least one incoming role HW:  paper (3)
    for i in range(1, size):
        yield [pr[rn][i] for rn in rolenames(sigma)]

    # Every pInd has at most one incoming role HW: paper (4)
    rns = list(rolenames(sigma))
    for i in range(1, size):
        for r1 in range(len(rns)):
            for r2 in range(r1):
                yield (-pr[rns[r1]][i], -pr[rns[r2]][i])


# creates clauses needed for handling of correct edge type (ex, num)
def edge_type_constraints(size: int, sigma: Signature, v: Variables):
    pi = v.pi
    is_ex = v.is_ex
    is_num = v.is_num

    for i in range(0, size):
        for j in range(i + 1, size):
            # edge types can only be existent, if edge exists
            yield (-is_ex[i][j], pi[i][j])
            yield (-is_num[i][j], pi[i][j])

            # if an edge is present, at least one edge type must be present
            yield (-pi[i][j], is_ex[i][j], is_num[i][j])

            # at most one edge type is true, mutual exclusion of different restrictions
            yield (-is_ex[i][j], -is_num[i][j])


# creates clauses needed for handling different types of defects (ex, num) and their interplay with generic defect
def defect_type_constraints(size: int, A: Structure, v: Variables):
    is_ex = v.is_ex
    is_num = v.is_num
    defect = v.defect
    ex_def = v.ex_def
    num_def = v.num_def

    for a in ind(A):
        for pInd2 in range(size):
            for pInd in range(pInd2):
                # link main defect to existential defect
                yield [-is_ex[pInd][pInd2], -defect[pInd][pInd2][a], ex_def[pInd][pInd2][a]]
                yield [-is_ex[pInd][pInd2], -ex_def[pInd][pInd2][a], defect[pInd][pInd2][a]]
                # link main defect to number defect
                yield [-is_num[pInd][pInd2], -defect[pInd][pInd2][a], num_def[pInd][pInd2][a]]
                yield [-is_num[pInd][pInd2], -num_def[pInd][pInd2][a], defect[pInd][pInd2][a]]


# creates the clauses needed for correct handling of concept names (Clauses 5,6,7, 8)
def conceptname_constraints(size: int, A: Structure, hc: HC, ind_tp_idx, anti_types, type_var: list[dict[int, int]],
                            simul: Simul, defect: Defect):
    for pInd in range(size):
        for a in ind(A):
            yield (-simul[pInd][a], type_var[pInd][ind_tp_idx[a]])  # HW: paper (7)

        for idx, tp in anti_types.items():
            for cn in tp:
                yield (-type_var[pInd][idx], -hc[cn][pInd])  # HW: paper (5)

            yield [type_var[pInd][idx]] + [hc[cn][pInd] for cn in tp]  # HW: paper (6)

    # positive Simulationsbedingung
    for pInd in range(size):
        for a in ind(A):
            # In some cases this can be a bottleneck, we could use the type-variables here
            cn_part = [-type_var[pInd][ind_tp_idx[a]]]
            rn_part = [defect[pInd][pInd2][a] for pInd2 in range(pInd + 1, size)]
            yield [simul[pInd][a]] + cn_part + rn_part  # HW: paper (8)


def leq_simulation_constraints(size: int, A: Structure, v: Variables, ind_tp_idx, type_var):
    op_leq = v.op_leq
    simul = v.simul

    for j in range(size):
        for a in ind(A):
            # if op_leq active at j and b's type matches j's concept → must simulate
            yield [-op_leq[j], -type_var[j][ind_tp_idx[a]], simul[j][a]]


def number_bound_constraints(size: int, sigma: Signature, v: Variables):
    is_num = v.is_num
    num_bound = v.num_bound
    op_geq = v.op_geq
    op_leq = v.op_leq
    n_max = v.n_max

    for j in range(1, size):
        # collect all parents of j
        parents_num = [is_num[i][j] for i in range(j)]

        # if is_num active for some parent, at least one operator (<=, =>) is selected
        # at most one clause not needed, bc both are allowed, realising =
        for i in range(j):
            yield [-is_num[i][j], op_geq[j], op_leq[j]]
            # do i also need, operator can only be selected if node is reached by a NUM edge?? like for bound
            #yield [-op_geq[j]] + parents_num
            #yield [-op_leq[j]] + parents_num

        # if at least on parent edge is NUM, at least one bound must be selected
        for i in range(j):
            yield [-is_num[i][j]] + [num_bound[j][n] for n in range(n_max)]

        # at most one bound must be selected
        for n1 in range(n_max):
            for n2 in range(n1):
                yield (-num_bound[j][n1], -num_bound[j][n2])

        # bound can only be set if node is reached by a NUM edge
        for n in range(n_max):
            yield [-num_bound[j][n]] + parents_num

    for j in range(1, size):
        for i in range(j):
            # Forbid NUM edge with bound n=1 and op_geq only (= existential)
            #yield [-is_num[i][j], -num_bound[j][0], -op_geq[j], op_leq[j]]
            pass


# creates clauses needed for handling correct behaviour of role fillers.
# If there exists an edge from i to j, then either (one of) the role fillers simulate or a defect must be present
def role_filler_constraints(size: int, A: Structure, sigma: Signature, v: Variables):
    pi = v.pi
    pr = v.pr
    is_ex = v.is_ex
    is_num = v.is_num
    simul = v.simul
    num_sim_geq = v.num_sim_geq
    num_sim_leq = v.num_sim_leq
    op_geq = v.op_geq
    op_leq = v.op_leq
    ex_def = v.ex_def
    num_def = v.num_def
    num_bound = v.num_bound
    n_max = v.n_max

    fillers = compute_role_fillers(sigma, A)

    # auxillary variables to link clauses
    link_ex = [[fresh_var() for a in ind(A)] for j in range(size)]
    link_num = [[fresh_var() for a in ind(A)] for j in range(size)]

    # Existential Restriction
    for a in ind(A):
        for pInd2 in range(size):
            for pInd in range(pInd2):
                yield [ex_def[pInd][pInd2][a], -pi[pInd][pInd2], -is_ex[pInd][pInd2], link_ex[pInd2][a]]  # 9-EX
    for a in ind(A):
        for pInd2 in range(size):
            for rn in rolenames(sigma):
                filler_sim = [simul[pInd2][b] for b in fillers[rn][a]]
                yield [-link_ex[pInd2][a], -pr[rn][pInd2]] + filler_sim  # 9-EX

    # Number Restriction
    for a in ind(A):
        for pInd2 in range(size):
            for pInd in range(pInd2):
                for n in range(1, n_max + 1):
                    yield [num_def[pInd][pInd2][a], -pi[pInd][pInd2], -is_num[pInd][pInd2], link_num[pInd2][a]]  # 9-NUM
    for a in ind(A):
        for pInd2 in range(size):
            for rn in rolenames(sigma):
                for n in range(1, n_max + 1):
                    yield [-link_num[pInd2][a], -pr[rn][pInd2], -num_bound[pInd2][n - 1], -op_geq[pInd2],
                           num_sim_geq[pInd2][a][rn][n - 1]]  # 9-NUM >=
                    yield [-link_num[pInd2][a], -pr[rn][pInd2], -num_bound[pInd2][n - 1], -op_leq[pInd2],
                           num_sim_leq[pInd2][a][rn][n - 1]]  # 9-NUM <=


# creates clauses needed to ensure that simulations and defects are mutually exclusive, whenever a simulation is present no defect can be present and the other way around
def simulation_mx_defect_constraints(size: int, sigma: Signature, A: Structure, v: Variables):
    pi = v.pi
    pr = v.pr
    is_ex = v.is_ex
    is_num = v.is_num
    simul = v.simul
    num_sim_geq = v.num_sim_geq
    num_sim_leq = v.num_sim_leq
    op_geq = v.op_geq
    op_leq = v.op_leq
    defect = v.defect
    ex_def = v.ex_def
    num_def = v.num_def
    num_bound = v.num_bound
    n_max = v.n_max

    # Ensure whenever a simulation (ex, num) holds, no corresponding defect(ex, num) can be present! (OG 10)
    # prevents introducing a defect when the situation actually is correct ex, num respectively
    for pInd in range(size):
        for pInd2 in range(pInd + 1, size):
            for a in ind(A):
                yield [-simul[pInd][a], -defect[pInd][pInd2][a]]  # HW: paper (10)
                yield [-is_ex[pInd][pInd2], -simul[pInd][a], -ex_def[pInd][pInd2][a]]  # 10-EX
                for b, rn in A.rn_ext[a]:
                    if rn in rolenames(sigma):
                        for n in range(1, n_max + 1):
                            yield [-is_num[pInd][pInd2], -op_geq[pInd2], -num_bound[pInd2][n - 1],
                                   -num_sim_geq[pInd2][a][rn][n - 1], -pr[rn][pInd2],
                                   -num_def[pInd][pInd2][a]]  # 10-NUM >=
                            yield [-is_num[pInd][pInd2], -op_leq[pInd2], -num_bound[pInd2][n - 1],
                                   -num_sim_leq[pInd2][a][rn][n - 1], -pr[rn][pInd2],
                                   -num_def[pInd][pInd2][a]]  # 10-NUM <=

    # Ensure whenever a defect (ex, num) is present, no corresponding simulation(ex, num) can be hold! (OG 12)
    # prevents introducing a simulation when situation does not simulate ex, num respectively
    for pInd in range(size):
        for pInd2 in range(pInd + 1, size):
            for a in ind(A):
                for rn in rolenames(sigma):
                    for b, rn_succ in A.rn_ext[a]:
                        if rn_succ == rn:
                            yield [-is_ex[pInd][pInd2], -defect[pInd][pInd2][a], -pr[rn][pInd2],
                                   -simul[pInd2][b]]  # 12-EX
                    for n in range(1, n_max + 1):
                        yield [-is_num[pInd][pInd2], -defect[pInd][pInd2][a], -pr[rn][pInd2], -num_bound[pInd2][n - 1],
                               -op_geq[pInd2], -num_sim_geq[pInd2][a][rn][n - 1]]  # 12-NUM >=
                        yield [-is_num[pInd][pInd2], -defect[pInd][pInd2][a], -pr[rn][pInd2], -num_bound[pInd2][n - 1],
                               -op_leq[pInd2], -num_sim_leq[pInd2][a][rn][n - 1]]  # 12-NUM <=

    # Ensure whenever a defect is present then an actual successor must be present (OG 11)
    for pInd in range(size):
        for pInd2 in range(pInd + 1, size):
            for a in ind(A):
                yield [-defect[pInd][pInd2][a], pi[pInd][pInd2]]  # (universal for EX, NUM)




# creates constraints needed for number simulation, cardinality restrictions
def cardinality_constraints(size: int, sigma: Signature, A: Structure, v: Variables):
    simul = v.simul
    num_sim_geq = v.num_sim_geq
    num_sim_leq = v.num_sim_leq
    n_max = v.n_max
    global var_counter

    fillers = compute_role_fillers(sigma, A)

    for pInd2 in range(size):
        for a in ind(A):
            for rn in rolenames(sigma):
                filler_lits = [simul[pInd2][b] for b in fillers[rn][a]]
                for n in range(1, n_max + 1):
                    idx = n - 1

                    # cardinalty encoding needed for >= (greater than or equal operator)
                    if not filler_lits or n > len(filler_lits):
                        yield [-num_sim_geq[pInd2][a][rn][idx]]
                    else:
                        # num_sim_geq ->  >=n role fillers simulate
                        num_enc_atleast = CardEnc.atleast(
                            filler_lits,
                            bound=n,
                            top_id=var_counter,
                            encoding=EncType.totalizer
                        )
                        var_counter = num_enc_atleast.nv + 1
                        for c in num_enc_atleast.clauses:
                            yield [-num_sim_geq[pInd2][a][rn][idx]] + list(c)
                        # >=n role fillers simulate -> num_sim_geq true (modeled through contraposition)
                        num_enc_atmost = CardEnc.atmost(
                            filler_lits,
                            bound=n - 1,
                            top_id=var_counter,
                            encoding=EncType.totalizer
                        )
                        var_counter = num_enc_atmost.nv + 1
                        for c in num_enc_atmost.clauses:
                            yield [num_sim_geq[pInd2][a][rn][idx]] + list(c)

                    # cardinalty encoding needed for <= (less than or equal operator)
                    if not filler_lits or len(filler_lits) <= n:
                        yield [num_sim_leq[pInd2][a][rn][idx]]
                        continue
                    else:
                        # <= n role fillers simulate -> num_sim_leq true (modeled through contrapostion)
                        num_enc_atleast = CardEnc.atleast(
                            filler_lits,
                            bound=n + 1,
                            top_id=var_counter,
                            encoding=EncType.totalizer
                        )
                        var_counter = num_enc_atleast.nv + 1
                        for c in num_enc_atleast.clauses:
                            yield [num_sim_leq[pInd2][a][rn][idx]] + list(c)

                        # num_sim_leq true -> <= n role fillers simulate
                        num_enc_atmost = CardEnc.atmost(
                            filler_lits,
                            bound=n,
                            top_id=var_counter,
                            encoding=EncType.totalizer
                        )
                        var_counter = num_enc_atmost.nv + 1
                        for c in num_enc_atmost.clauses:
                            yield [-num_sim_leq[pInd2][a][rn][idx]] + list(c)

def monotonicity_constraints(size, A, sigma, v):
    # Enforce monotonicity of numerical simulations
    for j in range(size):
        for a in ind(A):
            for rn in rolenames(sigma):
                for n in range(1, v.n_max):  # 1 up to n_max - 1
                    # geq(n+1) -> geq(n)
                    yield [-v.num_sim_geq[j][a][rn][n], v.num_sim_geq[j][a][rn][n - 1]]
                    # leq(n) -> leq(n+1)
                    yield [-v.num_sim_leq[j][a][rn][n - 1], v.num_sim_leq[j][a][rn][n]]

def sibling_role_ordering_constraints(size, sigma, v):
    """For same-parent, same-type siblings j1 < j2, force role(j1) <= role(j2) lexicographically."""
    pi = v.pi
    pr = v.pr
    is_ex = v.is_ex
    is_num = v.is_num

    rns = sorted(rolenames(sigma), key=lambda r: str(r))  # lexicographic order

    for parent in range(size):
        for j1 in range(parent + 1, size):
            for j2 in range(j1 + 1, size):
                # For each edge type, if parent->j1 and parent->j2 both use that type,
                # enforce role(j1) <= role(j2) lex
                for edge_type_j1, edge_type_j2 in [
                    (is_ex, is_ex), (is_num, is_num)
                ]:
                    for r2_idx, r2 in enumerate(rns):
                        for r1_idx, r1 in enumerate(rns):
                            if r1_idx > r2_idx:  # r1 > r2 lex: forbidden
                                # NOT (parent->j1 via edge_type, role=r1, parent->j2 via edge_type, role=r2)
                                yield [
                                    -pi[parent][j1],
                                    -pi[parent][j2],
                                    -edge_type_j1[parent][j1],
                                    -edge_type_j2[parent][j2],
                                    -pr[r1][j1],
                                    -pr[r2][j2],
                                ]
#For leaf siblings j1 < j2 with same parent, same role: CN-set(j1) <= CN-set(j2) lex
def concept_ordering_on_sibling_leaves(size, sigma, v):
    pi = v.pi
    pr = v.pr
    hc = v.hc
    is_ex = v.is_ex

    cns = sorted(conceptnames(sigma))

    for parent in range(size):
        for j1 in range(parent + 1, size):
            for j2 in range(j1 + 1, size):
                j1_has_child = [pi[j1][k] for k in range(j1 + 1, size)]
                j2_has_child = [pi[j2][k] for k in range(j2 + 1, size)]

                for rn in rolenames(sigma):
                    # Lex ordering: for first index k where they differ, cn[k] of j1 <= cn[k] of j2
                    # i.e., forbid j1[k]=False, j2[k]=True for smallest differing k
                    for k in range(len(cns)):
                        # Clause: NOT (j1,j2 are same-role EX leaves AND cn[0..k-1] equal AND cn[k](j1)=T, cn[k](j2)=F)
                        base = [-pi[parent][j1], -pi[parent][j2],
                                -is_ex[parent][j1], -is_ex[parent][j2],
                                -pr[rn][j1], -pr[rn][j2],
                                -hc[cns[k]][j1], hc[cns[k]][j2]]  # j1 has cn[k], j2 does not: forbidden

                        for k2 in range(k):
                             pass
                        yield base + j1_has_child + j2_has_child

# Calls all subfucntions which create clauses and returns list with all of them for SAT encoding
def sat_encoding_constraints(
        size: int, sigma: Signature, A: Structure, v: Variables
):
    simul = v.simul
    defect = v.defect
    hc = v.hc

    ind_tp_idx, anti_types = compute_types(A, sigma)
    type_var = [{idx: fresh_var() for idx in set(ind_tp_idx)} for i in range(size)]

    #print("DEBUG: All concepts found in A:", list(A.cn_ext.keys()))
    #print("DEBUG: All concepts filtered in Sigma:", list(conceptnames(sigma)))
    print("DEBUG: All roles filtered in Sigma:", list(rolenames(sigma)))
    print("DEBUG: All roles filtered in Sigma:", list(A.rn_ext.keys()))


    yield from query_structure_constraints(size, sigma, v)
    yield from edge_type_constraints(size, sigma, v)
    yield from defect_type_constraints(size, A, v)
    yield from conceptname_constraints(size, A, hc, ind_tp_idx, anti_types, type_var, simul, defect)
    yield from role_filler_constraints(size, A, sigma, v)
    yield from simulation_mx_defect_constraints(size, sigma, A, v)
    yield from cardinality_constraints(size, sigma, A, v)
    yield from number_bound_constraints(size, sigma, v)
    #ENCODING OPTIMIZATION
    yield from sibling_role_ordering_constraints(size, sigma, v)
    yield from concept_ordering_on_sibling_leaves(size, sigma, v)
    yield from monotonicity_constraints(size,A, sigma, v)

# --- OPTIMIZATION FUNCTIONS ---
def non_empty_symbols(A: Structure) -> Signature:
    cns = [cn for cn in A.cn_ext.keys() if A.cn_ext[cn]]
    rns: set[RoleAtom] = set()
    for a in ind(A):
        for _, rn in A.rn_ext[a]:
            rns.add(rn)
    rns2 = list(rns)

    cns.sort(key="{}".format)
    rns2.sort(key=lambda r: str(r))
    return (cns, rns2)


# Returns the (concept and role) symbols that are relevant given the positive
# examples
def determine_relevant_symbols(
        A: Structure, P: list[int], minP: int, dist: int
) -> Signature:
    #print("DEBUG SIMB: Sample individual from P:", P[0] if P else "P is empty")
    #print("DEBUG SIMB: Sample keys available in A.rn_ext:", list(A.rn_ext.keys())[:5])
    (cns, rns) = non_empty_symbols(A)

    count = {cn: 0 for cn in cns}
    countr = {rn: 0 for rn in rns}

    for p in P:
        cns2: set[str] = set()
        rns2: set[RoleAtom] = set()
        for cn in cns:
            if p in A.cn_ext[cn]:
                cns2.add(cn)

        dinds = {p}
        for r in range(dist):
            step: set[int] = set()
            for i1 in dinds:
                for i2, rn in A.rn_ext[i1]:
                    step.add(i2)
                    rns2.add(rn)
                    for cn in cns:
                        if i2 in A.cn_ext[cn]:
                            cns2.add(cn)
            dinds = step

        for cn in cns2:
            count[cn] += 1
        for rn in rns2:
            countr[rn] += 1

    cns = list(cn for (cn, c) in count.items() if c >= minP)

    rns = list(rn for (rn, c) in countr.items() if c >= minP)
    cns.sort(key="{}".format)
    rns.sort(key=lambda r: str(r))

    return (cns, rns)


def restrict_nb(
        k: int, A: Structure, P: list[int], N: list[int]
) -> tuple[Structure, list[int], list[int]]:
    (A2, mapping) = restrict_to_neighborhood(k + 1, A, P + N)
    P2 = [mapping[a] for a in P]
    N2 = [mapping[a] for a in N]
    return A2, P2, N2


# --- DECODING MODEL INTO SEPARATING QUERY ---
def real_coverage(model, P: list[int], N: list[int], mapping: Variables, A: Structure) -> int:
    simul = mapping.simul
    cov = 0

    for a in P:
        if simul[0][a] in model:
            cov += 1
        else:
            #print("P missing: ", simul[0][a])
            #print(A.indmap)
            uri = next((k for k, v in A.indmap.items() if v == a), None)
            print("P missing:", a, "->", uri)
    for b in N:
        if -simul[0][b] in model:
            cov += 1
        #else:
            #print("N missing")
    return cov


def is_model(size, sigma, model, mapping, solver):
    assums = []
    pi = mapping.pi
    pr = mapping.pr
    hc = mapping.hc
    is_ex = mapping.is_ex
    is_num = mapping.is_num
    num_bound = mapping.num_bound
    op_geq = mapping.op_geq
    op_leq = mapping.op_leq
    n_max  = mapping.n_max

    for pInd in range(size):
        for cn in conceptnames(sigma):
            assums.append(hc[cn][pInd] if hc[cn][pInd] in model else -hc[cn][pInd])
        for pInd2 in range(pInd + 1, size):
            # fix edge existence and type
            assums.append(pi[pInd][pInd2] if pi[pInd][pInd2] in model else -pi[pInd][pInd2])
            assums.append(is_ex[pInd][pInd2] if is_ex[pInd][pInd2] in model else -is_ex[pInd][pInd2])
            assums.append(is_num[pInd][pInd2] if is_num[pInd][pInd2] in model else -is_num[pInd][pInd2])
            for rn in rolenames(sigma):
                if pi[pInd][pInd2] in model and pr[rn][pInd2] in model:
                    assums.append(pr[rn][pInd2])

    # fix selected bound for NUM nodes
    for j in range(size):
        assums.append(op_geq[j] if op_geq[j] in model else -op_geq[j])
        assums.append(op_leq[j] if op_leq[j] in model else -op_leq[j])

        for n in range(n_max):
            assums.append(num_bound[j][n] if num_bound[j][n] in model else -num_bound[j][n])

    return solver.solve(assumptions=assums)


def minimize_concept_assertions(
        size: int, sigma: Signature, solver: Glucose4, mapping: Variables, model: set[int]
) -> set[int]:
    best_model = model

    # Greedily reduce number of concept assertions and abuse sat solver as a fast query engine
    for i in range(size):
        for cn in conceptnames(sigma):
            if mapping.hc[cn][i] in best_model:
                test_model = set(best_model)
                test_model.remove(mapping.hc[cn][i])
                test_model.add(-mapping.hc[cn][i])
                if is_model(size, sigma, test_model, mapping, solver):
                    best_model = test_model
    return best_model


def model2fitting_query(
        size: int, sigma: Signature, mapping: Variables, model: set[int]
) -> Structure:
    pi = mapping.pi
    pr = mapping.pr
    hc = mapping.hc
    is_ex = mapping.is_ex
    is_num = mapping.is_num
    num_bound = mapping.num_bound
    num_sim_geq = mapping.num_sim_geq
    num_sim_leq = mapping.num_sim_leq
    op_geq = mapping.op_geq
    op_leq = mapping.op_leq

    q = Structure(
        max_ind=size,
        cn_ext={cn: set() for cn in conceptnames(sigma)},
        rn_ext={a: set() for a in range(size)},
        indmap={},
        nsmap={},
    )

    for pInd in range(size):
        for cn in conceptnames(sigma):
            if hc[cn][pInd] in model:
                q.cn_ext[cn].add(pInd)
        for pInd2 in range(pInd + 1, size):
            for rn in rolenames(sigma):
                if pi[pInd][pInd2] in model and pr[rn][pInd2] in model:
                    if is_num[pInd][pInd2] in model:
                        n = None
                        for idx, var in enumerate(num_bound[pInd2]):
                            if var in model:
                                n = idx + 1
                                break
                        if (op_geq[pInd2] in model and op_leq[pInd2] in model):
                            q.rn_ext[pInd].add((pInd2, f"  = {n} {rn}"))
                        elif (op_geq[pInd2] in model):
                            if (n == 1):  # >=1 is the same as existential restriction
                                q.rn_ext[pInd].add((pInd2, rn))
                            else:
                                q.rn_ext[pInd].add((pInd2, f" >= {n} {rn}"))
                        elif (op_leq[pInd2] in model):
                            q.rn_ext[pInd].add((pInd2, f" <= {n} {rn}"))
                    else:  # corresponds to is_ex
                        q.rn_ext[pInd].add((pInd2, rn))

    return q


def create_coverage_formula(
        P: list[int], N: list[int], coverage: int, mapping: Variables, all_pos: bool
) -> list[list[int]]:
    simul = mapping.simul

    global var_counter
    #EXACT MODE
    if coverage == len(P) + len(N):
        return [[simul[0][a]] for a in P] + [[-simul[0][b]] for b in N]
    #NEGATIVE APPROXIMATION
    elif all_pos:
        lits = [-simul[0][b] for b in N]

        bound = max(coverage - len(P), 1)
        enc = CardEnc.atleast(
            lits, bound=bound, top_id=var_counter, encoding=EncType.kmtotalizer
        )

        var_counter = enc.nv + 1

        return [[simul[0][a]] for a in P] + enc.clauses
    #FULL APPROXIMATION
    else:
        lits = [simul[0][a] for a in P] + [-simul[0][b] for b in N]

        enc = CardEnc.atleast(
            lits, bound=coverage, top_id=var_counter, encoding=EncType.kmtotalizer
        )

        var_counter = enc.nv + 1

        return enc.clauses

# --- SOLVING PROCESS ---
# called by solve_incr, represents one iteration of bounded fitting.
# Constructs a formula to find a separating query of size and solves it
# Guaranted that we can reach min_coverage
def solve(
        size: int,
        A: Structure,
        P: list[int],
        N: list[int],
        coverage_lb: int,
        all_pos: bool,
        target_accuracy: float,
        timeout: float = -1,
) -> Union[tuple[int, Structure, bool], None]:
    time_start = time.process_time()
    A, P, N = restrict_nb(size, A, P, N)
    #print(f"DEBUG after restrict_nb: |ind(A)|={len(list(ind(A)))}, |P|={len(P)}, |N|={len(N)}")

    if all_pos:
        min_pos = len(P)
    else:
        # If we want to cover at least min_coverage examples, we have to cover at least min_pos positive examples
        min_pos = max(coverage_lb - len(N), 1)
    # Use symbols that occur in distance k - 1 of at least min_pos positive example
    sigma = determine_relevant_symbols(A, P, min_pos, size - 1)

    mapping = create_variables(size, sigma, A)

    g = Glucose4()

    for c in sat_encoding_constraints(size, sigma, A, mapping):
        pysolvers.glucose41_add_cl(g.glucose, c)

    dt = time.process_time() - time_start
    best_sol = None
    coverage_ub = len(P) + len(N)
    while coverage_lb <= coverage_ub and (dt < timeout or timeout < 0):

        for c in create_coverage_formula(P, N, coverage_lb, mapping, all_pos):
            pysolvers.glucose41_add_cl(g.glucose, c)

        # orginal solver call, replaced with imcremental SAT solver calls with assumptions
        solver_start = time.process_time()
        satisfiable = g.solve()
        #print(f"-> Solver completed execution in {time.process_time() - solver_start:.4f} seconds.")

        if not satisfiable:
            #print(f"-> Size {size} returned UNSATISFIABLE.")
            #print(f"-> Solver found UNSAT in {time.process_time() - solver_start:.4f} seconds.")

            g.delete()
            return best_sol

        # print(g.accum_stats())
        model: set[int] = set(g.get_model())  # type: ignore

        if model is None:
            g.delete()
            return best_sol

        # Once we needed level k, subsequent iterations won't need anything
        # stricter than k (coverage only increases), so skip levels 0..k-1

        # DEBUG: print edge type flags for all edges
        for pInd in range(size):
            for pInd2 in range(pInd + 1, size):
                ex_val = mapping.is_ex[pInd][pInd2] in model
                num_val = mapping.is_num[pInd][pInd2] in model
                pi_val = mapping.pi[pInd][pInd2] in model
                #print(f"Edge ({pInd},{pInd2}): pi={pi_val}, is_ex={ex_val}, is_num={num_val}")

        coverage_lb = real_coverage(model, P, N, mapping, A)

        if True:
            # Required for minimization
            for c in create_coverage_formula(P, N, coverage_lb, mapping, all_pos):
                pysolvers.glucose41_add_cl(g.glucose, c)

            model = minimize_concept_assertions(size, sigma, g, mapping, model)

        best_q = model2fitting_query(size, sigma, mapping, model)
        best_sol = (coverage_lb, best_q, False)
        print(solution2sparql(best_q))

        print(
            "== Coverage: {}/{} == Accuracy: {}".format(
                coverage_lb, coverage_ub, coverage_lb / coverage_ub
            )
        )
        # APPROXIMATION; PERFOMANCE GAIN, ONCE A TARGET ACCURACY IS REACHED, SOLVER STOPS
        '''current_accuracy = coverage_lb / (len(P) + len(N))
        if target_accuracy < 1:
            if current_accuracy >= target_accuracy:
                print(f"Approximation: Target accuracy of {target_accuracy} reached. Stopping search.")
                g.delete()
                return (coverage_lb, best_q, True)'''

        coverage_lb = coverage_lb + 1
        dt = time.process_time() - time_start

    g.delete()
    # original end of loop, so no threashold reached or UNSAT
    if best_sol is not None:
        return best_sol
    return None


# MOST OUTER LOOP
# Search for a small separating query by incrementally increasing the size
def solve_incr(
        A: Structure,
        P: list[int],
        N: list[int],
        m: mode,
        timeout: float = -1,
        max_size: int = 19,
) -> tuple[int, Structure]:
    time_start = time.process_time()
    i = 1
    best_coverage = len(P)
    best_q = Structure(max_ind=1, cn_ext={}, rn_ext={0: set()}, indmap={}, nsmap={})
    dt = time.process_time() - time_start
    while (
            best_coverage < len(P) + len(N)
            and i <= max_size
            and (dt < timeout or timeout == -1)
    ):
        print("== Searching for a fitting query of size {}".format(i))
        if m == mode.exact:
            sol = solve(i, A, P, N, len(P) + len(N), True, 1, timeout - dt)
        elif m == mode.neg_approx:
            sol = solve(i, A, P, N, best_coverage + 1, True, 0.75, timeout - dt)
        else:
            sol = solve(i, A, P, N, best_coverage + 1, False, 0.75, timeout - dt)
        if sol is not None:
            best_coverage, best_q,  target_reached = sol

            if target_reached:
                break

        i += 1
        dt = time.process_time() - time_start

    print(
        "== Best query found with coverage {}/{}".format(best_coverage, len(P) + len(N))
    )
    print(solution2sparql(best_q))
    return (best_coverage, best_q)