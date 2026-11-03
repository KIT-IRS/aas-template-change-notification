"""The ten atomic operators over T = (T_E, T_Q, T_A)  (paper §3.3, §3.4, Table 1).

Every operator is specified by
    pre(T)          -> None if admissible, otherwise the rejection code,
    apply(T)        -> mutates T into T+ (only called by guarded application, on a copy),
    post(T, T+)     -> True iff the post-condition of Table 1 holds,
    mod(T)          -> the positions <f, x> the operator may write, computed on the pre-state.

Arguments are components (abstract identities); binding paths to components is the job of
tcn.core.addressing. A creating operator allocates the next free ids of T, so its modified set
is known before application (Template.next_ids).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tcn.core.metamodel import ELEMENT_TYPES, M_CONT, adm, admissible, mand
from tcn.core.model import LAMBDA, Attribute, Element, Id, Qualifier, Template
from tcn.core.transfer import TransferFunction

Position = tuple[str, Id]

E_FUNCS = ("T_E", "idShort", "type", "parent")
Q_FUNCS = ("T_Q", "qtype", "elem")
A_FUNCS = ("T_A", "name", "value", "owner")


def _all(funcs: tuple[str, ...], x: Id) -> set[Position]:
    """A membership change of a component includes all of its function values."""
    return {(f, x) for f in funcs}


def _sibling_names(t: Template, p: Id) -> set[str | None]:
    return {t.E[c].id_short for c in t.children(p)}


def _admissible(t: Template, a: Id, value: Any) -> bool:
    if value is LAMBDA:
        return True
    x = t.A[a].owner
    others = {t.A[b].name: t.A[b].value for b in t.attributes(x) if t.A[b].value is not LAMBDA}
    if x in t.Q:
        others["type"] = t.Q[x].qtype
    return admissible(t.tau(x), others, t.A[a].name, value)


def _slots_created(t: Template, t2: Template, owner: Id, names: set[str]) -> bool:
    """∀ n ∈ names ∃ a ∈ T_A+ : owner+(a) = owner ∧ name+(a) = n ∧ value+(a) = λ"""
    return all((a := t2.attr(owner, n)) is not None and t2.A[a].value is LAMBDA for n in names)


# ─────────────────────────────── CREATE ───────────────────────────────


@dataclass
class CreateSME:
    p: Id
    t: str
    s: str | None  # None only for an entry of a SubmodelElementList

    def pre(self, T: Template) -> str | None:
        if self.p not in T.E:
            return "PARENT_EXISTS"
        if T.E[self.p].type not in M_CONT:
            return "PARENT_IS_CONTAINER"
        if self.t not in ELEMENT_TYPES:  # includes t ≠ Submodel
            return "TYPE_ADMISSIBLE"
        if self.s is None and T.E[self.p].type != "SubmodelElementList":
            return "IDSHORT_REQUIRED"
        if self.s is not None and self.s in _sibling_names(T, self.p):
            return "IDSHORT_UNIQUE"
        return None

    def apply(self, T: Template) -> None:
        e = T.new_id()
        T.E[e] = Element(self.s, self.t, self.p)
        for n in sorted(mand(self.t)):
            T.A[T.new_id()] = Attribute(n, LAMBDA, e)

    def post(self, T: Template, T2: Template) -> bool:
        e = T.next_ids(1)[0]
        return e in T2.E and T2.E[e] == Element(self.s, self.t, self.p) and \
            _slots_created(T, T2, e, mand(self.t))

    def mod(self, T: Template) -> set[Position]:
        e, *attrs = T.next_ids(1 + len(mand(self.t)))
        return _all(E_FUNCS, e) | {pos for a in attrs for pos in _all(A_FUNCS, a)}


@dataclass
class CreateQual:
    e: Id
    k: str

    def pre(self, T: Template) -> str | None:
        if self.e not in T.E:
            return "TARGET_EXISTS"
        if self.k in {T.Q[q].qtype for q in T.qualifiers(self.e)}:
            return "QUAL_EXISTS"  # AASd-021
        return None

    def apply(self, T: Template) -> None:
        q = T.new_id()
        T.Q[q] = Qualifier(self.k, self.e)
        for n in sorted(mand("Qualifier")):
            T.A[T.new_id()] = Attribute(n, LAMBDA, q)

    def post(self, T: Template, T2: Template) -> bool:
        q = T.next_ids(1)[0]
        return T2.Q.get(q) == Qualifier(self.k, self.e) and \
            _slots_created(T, T2, q, mand("Qualifier"))

    def mod(self, T: Template) -> set[Position]:
        q, *attrs = T.next_ids(1 + len(mand("Qualifier")))
        return _all(Q_FUNCS, q) | {pos for a in attrs for pos in _all(A_FUNCS, a)}


@dataclass
class CreateAttr:
    x: Id
    n: str

    def pre(self, T: Template) -> str | None:
        if self.x not in T.E and self.x not in T.Q:
            return "TARGET_EXISTS"
        if self.n not in adm(T.tau(self.x)):
            return "ATTR_APPLICABLE"
        if T.attr(self.x, self.n) is not None:
            return "ATTR_EXISTS"
        return None

    def apply(self, T: Template) -> None:
        T.A[T.new_id()] = Attribute(self.n, LAMBDA, self.x)

    def post(self, T: Template, T2: Template) -> bool:
        return T2.A.get(T.next_ids(1)[0]) == Attribute(self.n, LAMBDA, self.x)

    def mod(self, T: Template) -> set[Position]:
        return _all(A_FUNCS, T.next_ids(1)[0])


# ─────────────────────────────── UPDATE ───────────────────────────────


@dataclass
class UpdateIdShort:
    e: Id
    s: str

    def pre(self, T: Template) -> str | None:
        if self.e == T.root:
            return None
        if self.e not in T.E:
            return "TARGET_EXISTS"
        if T.children(self.e):
            return "NO_CHILDREN"
        if self.s in _sibling_names(T, T.E[self.e].parent):
            return "IDSHORT_UNIQUE"
        return None

    def apply(self, T: Template) -> None:
        T.E[self.e].id_short = self.s

    def post(self, T: Template, T2: Template) -> bool:
        return T2.E[self.e].id_short == self.s

    def mod(self, T: Template) -> set[Position]:
        return {("idShort", self.e)}


@dataclass
class UpdateParent:
    e: Id
    p: Id

    def pre(self, T: Template) -> str | None:
        if self.e not in T.E or self.e == T.root:
            return "TARGET_EXISTS"
        if self.p not in T.E:
            return "PARENT_EXISTS"
        if T.children(self.e):
            return "NO_CHILDREN"
        if T.E[self.p].type not in M_CONT:
            return "PARENT_IS_CONTAINER"
        s = T.E[self.e].id_short
        if s is not None and s in _sibling_names(T, self.p):
            return "IDSHORT_UNIQUE"
        if self.p in T.desc(self.e) | {self.e}:
            return "CYCLIC_PARENT"
        return None

    def apply(self, T: Template) -> None:
        # Re-insert so that the moved element becomes the last child of its new parent.
        el = T.E.pop(self.e)
        el.parent = self.p
        T.E[self.e] = el

    def post(self, T: Template, T2: Template) -> bool:
        return T2.E[self.e].parent == self.p

    def mod(self, T: Template) -> set[Position]:
        return {("parent", self.e)}


@dataclass
class UpdateAttr:
    a: Id
    v: Any

    def pre(self, T: Template) -> str | None:
        return None if self.a in T.A else "ATTR_ABSENT"

    def apply(self, T: Template) -> None:
        T.A[self.a].value = self.v

    def post(self, T: Template, T2: Template) -> bool:
        return T2.A[self.a].value == self.v

    def mod(self, T: Template) -> set[Position]:
        return {("value", self.a)}


# ─────────────────────────────── REMOVE ───────────────────────────────


@dataclass
class RemoveSME:
    e: Id

    def pre(self, T: Template) -> str | None:
        if self.e not in T.E or self.e == T.root:
            return "TARGET_EXISTS"
        if T.children(self.e):
            return "NO_CHILDREN"
        if T.qualifiers(self.e):
            return "QUALIFIERS_PRESENT"
        return None

    def apply(self, T: Template) -> None:
        for a in T.attributes(self.e):
            del T.A[a]
        del T.E[self.e]

    def post(self, T: Template, T2: Template) -> bool:
        return self.e not in T2.E and not set(T.attributes(self.e)) & T2.A.keys()

    def mod(self, T: Template) -> set[Position]:
        return _all(E_FUNCS, self.e) | {pos for a in T.attributes(self.e) for pos in _all(A_FUNCS, a)}


@dataclass
class RemoveQual:
    q: Id

    def pre(self, T: Template) -> str | None:
        return None if self.q in T.Q else "QUAL_ABSENT"

    def apply(self, T: Template) -> None:
        for a in T.attributes(self.q):
            del T.A[a]
        del T.Q[self.q]

    def post(self, T: Template, T2: Template) -> bool:
        return self.q not in T2.Q and not set(T.attributes(self.q)) & T2.A.keys()

    def mod(self, T: Template) -> set[Position]:
        return _all(Q_FUNCS, self.q) | {pos for a in T.attributes(self.q) for pos in _all(A_FUNCS, a)}


@dataclass
class RemoveAttr:
    a: Id

    def pre(self, T: Template) -> str | None:
        return None if self.a in T.A else "ATTR_ABSENT"

    def apply(self, T: Template) -> None:
        del T.A[self.a]

    def post(self, T: Template, T2: Template) -> bool:
        return self.a not in T2.A

    def mod(self, T: Template) -> set[Position]:
        return _all(A_FUNCS, self.a)


# ──────────────────────────────── SYNC ────────────────────────────────


@dataclass
class Sync:
    src: list[Id]
    tgt: list[Id]
    f: TransferFunction

    def pre(self, T: Template) -> str | None:
        if not all(a in T.A for a in self.src + self.tgt):
            return "ATTR_ABSENT"
        if not self.tgt:
            return "TARGET_EMPTY"
        if not self.f.executable:
            return None  # recorded only; the asset maintainer carries the values over
        if not self.f.defined(self._source_values(T)):
            return "TRANSFER_UNDEFINED"
        values = self.f(self._source_values(T))
        if len(values) != len(self.tgt):
            return "ARITY_MISMATCH"
        if not all(_admissible(T, a, v) for a, v in zip(self.tgt, values)):
            return "TRANSFER_INADMISSIBLE"  # f yields a value of a form the target cannot hold
        return None

    def _source_values(self, T: Template) -> list[Any]:
        return [T.A[a].value for a in self.src]

    def apply(self, T: Template) -> None:
        if self.f.executable:
            for a, v in zip(self.tgt, self.f(self._source_values(T))):
                T.A[a].value = v

    def post(self, T: Template, T2: Template) -> bool:
        if not self.f.executable:
            return True
        return [T2.A[a].value for a in self.tgt] == self.f(self._source_values(T))

    def mod(self, T: Template) -> set[Position]:
        return {("value", a) for a in self.tgt}


Operator = (CreateSME | CreateQual | CreateAttr | UpdateIdShort | UpdateParent | UpdateAttr
            | RemoveSME | RemoveQual | RemoveAttr | Sync)
