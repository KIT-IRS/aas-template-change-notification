"""Correspondence between a Submodel Template and a submodel conforming to it  (paper §3.5).

    M1  The roots correspond. Below corresponding containers, a template element is realised by the
        instance children with the same type and semanticId (else the same idShort); every entry of
        a SubmodelElementList realises the list's template entry.
    M2  A placeholder (idShort contains 'arbitrary') is realised by all children of the same type
        that no other template element claims. Its realisations carry instance-defined metadata.

Used by resolution (which realisations an item concerns) and by the conformance check.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tcn.core.model import Id, Template

CARDINALITY_TYPES = {"Cardinality", "Multiplicity", "SMT/Cardinality"}


def card(T: Template, e: Id) -> str | None:
    """The cardinality the template states for e, if any."""
    for q in T.qualifiers(e):
        if T.Q[q].qtype in CARDINALITY_TYPES and (a := T.attr(q, "value")) is not None:
            return T.A[a].value
    return None


def placeholder(T: Template, e: Id) -> bool:
    return "arbitrary" in (T.E[e].id_short or "").lower()


@dataclass
class Matching:
    R: dict[Id, list[Id]] = field(default_factory=dict)  # template element -> realisations
    named: set[Id] = field(default_factory=set)  # realisations named as in the template
    wild: set[Id] = field(default_factory=set)  # realisations of placeholders


def match(T: Template, I: Template) -> Matching:
    m = Matching()
    _match(T, I, T.root, I.root, m)
    return m


def _semantic_id(T: Template, x: Id):
    a = T.attr(x, "semanticId")
    return T.A[a].value if a is not None else None


def _match(T: Template, I: Template, t: Id, i: Id, m: Matching) -> None:
    m.R.setdefault(t, []).append(i)
    if T.E[t].id_short == I.E[i].id_short:
        m.named.add(i)
    free, kids = I.children(i), T.children(t)
    if T.E[t].type == "SubmodelElementList":
        for x in free if kids else []:
            _match(T, I, kids[0], x, m)
        return
    for c in [c for c in kids if not placeholder(T, c)]:
        sem = _semantic_id(T, c)
        hits = [x for x in free if I.E[x].type == T.E[c].type and sem is not None and _semantic_id(I, x) == sem]
        hits = hits or [x for x in free if I.E[x].id_short == T.E[c].id_short]
        for x in hits:
            free.remove(x)
            _match(T, I, c, x, m)
    for c in [c for c in kids if placeholder(T, c)]:
        for x in [x for x in free if I.E[x].type == T.E[c].type]:
            free.remove(x)
            m.R.setdefault(c, []).append(x)
            m.wild.add(x)
    for c in kids:
        m.R.setdefault(c, [])
