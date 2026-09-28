"""Decomposition of a Submodel Template into T = (T_E, T_Q, T_A)  (paper §3.1, Fig. 2a).

Every component has an abstract identity (an integer id) that is never serialised. All relations
between components are explicit assignment functions stored on the component:

    element    e:  idShort(e), type(e), parent(e)
    qualifier  q:  qtype(q), elem(q)
    attribute  a:  name(a), value(a), owner(a)

The submodel itself is the distinguished root element r_T with type(r_T) = "Submodel" and
parent(r_T) = None. Everything else (children, paths, ...) is derived and never stored.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from typing import Any


class _Unpopulated:
    """The unpopulated value λ of an attribute created as an empty slot."""

    def __repr__(self) -> str:
        return "λ"


LAMBDA = _Unpopulated()

Id = int


@dataclass
class Element:
    id_short: str | None  # None for entries of a SubmodelElementList
    type: str
    parent: Id | None  # None only for the root r_T


@dataclass
class Qualifier:
    qtype: str
    elem: Id


@dataclass
class Attribute:
    name: str
    value: Any  # JSON value as in the AAS JSON serialisation, or LAMBDA
    owner: Id


@dataclass
class Template:
    E: dict[Id, Element] = field(default_factory=dict)
    Q: dict[Id, Qualifier] = field(default_factory=dict)
    A: dict[Id, Attribute] = field(default_factory=dict)
    root: Id = 0
    _next: Id = 0

    # --- identity -------------------------------------------------------------------------

    def new_id(self) -> Id:
        """A fresh identity, disjoint across all three component sets."""
        self._next += 1
        return self._next

    def next_ids(self, k: int) -> list[Id]:
        """The ids the next k calls of new_id() will return, without allocating them.
        This makes the modified set of a creating operator computable before application."""
        return list(range(self._next + 1, self._next + 1 + k))

    def copy(self) -> Template:
        # Components are copied; attribute values are shared, as no operator mutates a value in place.
        return Template({k: replace(x) for k, x in self.E.items()}, {k: replace(x) for k, x in self.Q.items()},
                        {k: replace(x) for k, x in self.A.items()}, self.root, self._next)

    # --- derived views (never stored) -----------------------------------------------------

    def children(self, e: Id) -> list[Id]:
        # Dict order is the document order; UpdateParent re-inserts, i.e. appends.
        return [k for k, x in self.E.items() if x.parent == e]

    def desc(self, e: Id) -> set[Id]:
        result: set[Id] = set()
        for c in self.children(e):
            result |= {c} | self.desc(c)
        return result

    def qualifiers(self, e: Id) -> list[Id]:
        return [k for k, q in self.Q.items() if q.elem == e]

    def attributes(self, x: Id) -> list[Id]:
        return [k for k, a in self.A.items() if a.owner == x]

    def attr(self, x: Id, name: str) -> Id | None:
        return next((a for a in self.attributes(x) if self.A[a].name == name), None)

    def tau(self, x: Id) -> str:
        """Type projection τ: element type, or the constant 'Qualifier'."""
        return self.E[x].type if x in self.E else "Qualifier"

    def segment(self, e: Id) -> str:
        p = self.E[e].parent
        if p is not None and self.E[p].type == "SubmodelElementList":
            return f"[{self.children(p).index(e)}]"
        return self.E[e].id_short or ""

    def path(self, e: Id) -> str:
        """idShort path as used by the AAS API, excluding the root (e.g. 'A.B[0].C')."""
        if e == self.root:
            return ""
        parent = self.path(self.E[e].parent)
        seg = self.segment(e)
        if not parent or seg.startswith("["):
            return parent + seg
        return f"{parent}.{seg}"


# --- positions: the basis of post-condition and modified-set checks ----------------------


def positions(t: Template) -> dict[tuple[str, Id], Any]:
    """All positions <f, x> of T with their values. Membership is the position <T_*, x>."""
    pos: dict[tuple[str, Id], Any] = {}
    for x, e in t.E.items():
        pos |= {("T_E", x): True, ("idShort", x): e.id_short, ("type", x): e.type, ("parent", x): e.parent}
    for x, q in t.Q.items():
        pos |= {("T_Q", x): True, ("qtype", x): q.qtype, ("elem", x): q.elem}
    for x, a in t.A.items():
        pos |= {("T_A", x): True, ("name", x): a.name, ("value", x): a.value, ("owner", x): a.owner}
    return pos


def changed_positions(before: Template, after: Template) -> set[tuple[str, Id]]:
    b, a = positions(before), positions(after)
    return {k for k in b.keys() | a.keys() if b.get(k, None) != a.get(k, None)}


def canonical(t: Template) -> set[str]:
    """Identity-free view of T, used to decide whether two templates coincide at every position.

    Components are named by their path, qualifier type and attribute name (paper §3.2),
    so two templates with different abstract identities can be compared.
    """

    def owner_name(x: Id) -> str:
        if x in t.Q:
            return f"{t.path(t.Q[x].elem)}@{t.Q[x].qtype}"
        return t.path(x)

    # idShort is listed separately: the root's and a list entry's idShort are not part of a path.
    facts = {f"E {t.path(e)} : {t.E[e].type} idShort={t.E[e].id_short}" for e in t.E}
    facts |= {f"Q {owner_name(q)}" for q in t.Q}
    facts |= {
        f"A {owner_name(a.owner)}#{a.name} = {json.dumps(a.value, sort_keys=True, default=repr)}"
        for a in t.A.values()
    }
    return facts
