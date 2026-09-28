"""Generic checks of the guarantees of guarded application  (paper §3.1).

For every operator application, independent of the operator:
  ACC  ⇒  post(T, T+) holds,  changed positions ⊆ mod(T),  T+ is structurally valid
  REJ  ⇒  T is returned and no position has changed
In both cases the input T itself is never mutated.
"""

from __future__ import annotations

from collections import Counter

from tcn.core.guarded import ACC, Outcome, guarded
from tcn.core.metamodel import M_CONT
from tcn.core.model import Template, changed_positions, positions
from tcn.core.operators import Operator


def check_guarded(op: Operator, T: Template) -> tuple[Template, Outcome]:
    snapshot = T.copy()
    mod = op.mod(T)
    T2, outcome = guarded(op, T)

    assert positions(T) == positions(snapshot), "input template was mutated"
    if outcome.status == ACC:
        assert op.post(T, T2), f"post-condition violated by {op}"
        extra = changed_positions(T, T2) - mod
        assert not extra, f"{op} changed positions outside mod: {extra}"
        assert not structural_violations(T2), structural_violations(T2)
    else:
        assert T2 is T and not changed_positions(T, T2), "rejected operator changed T"
    return T2, outcome


def structural_violations(T: Template) -> list[str]:
    """Structural validity (paper §3.1): must hold in every state along a chain."""
    v = []
    roots = [e for e, x in T.E.items() if x.parent is None]
    if roots != [T.root]:
        v.append(f"root is not the only parentless element: {roots}")
    for e, x in T.E.items():
        if x.parent is not None and (x.parent not in T.E or T.E[x.parent].type not in M_CONT):
            v.append(f"orphan or non-container parent: {e}")
        seen, p = {e}, x.parent
        while p is not None and p in T.E:
            if p in seen:
                v.append(f"cycle at {e}")
                break
            seen.add(p)
            p = T.E[p].parent
    for p in T.E:
        names = Counter(T.E[c].id_short for c in T.children(p) if T.E[c].id_short is not None)
        v += [f"duplicate idShort {n} below {p}" for n, k in names.items() if k > 1]
        qtypes = Counter(T.Q[q].qtype for q in T.qualifiers(p))
        v += [f"duplicate qualifier {k} at {p}" for k, n in qtypes.items() if n > 1]
    v += [f"qualifier {q} bound to missing element" for q, x in T.Q.items() if x.elem not in T.E]
    for x in T.E.keys() | T.Q.keys():
        names = Counter(T.A[a].name for a in T.attributes(x))
        v += [f"duplicate attribute {n} at {x}" for n, k in names.items() if k > 1]
    v += [f"attribute {a} has missing owner" for a, x in T.A.items()
          if x.owner not in T.E and x.owner not in T.Q]
    return v
