"""Conformance of a submodel to a Submodel Template.

The submodel is matched against the template (tcn.core.matching). For every realised container,
each template element below it is checked against the cardinality the template states:

    MISSING          fewer realisations than required (One, OneToMany)
    TOO_MANY         more realisations than allowed (One, ZeroToOne)
    VALUE_MISSING    a mandatory data element without value
    VALUE_TYPE       a valueType different from the template's
    NOT_IN_TEMPLATE  an element the template does not describe (local extension); not a violation

A submodel conforms iff there is no finding other than NOT_IN_TEMPLATE. Metamodel constraints are
checked separately by aas-core (tcn.aas.bridge.verify).
"""

from __future__ import annotations

from dataclasses import dataclass

from tcn.core.matching import card, match, placeholder
from tcn.core.model import LAMBDA, Id, Template

VIOLATIONS = ("MISSING", "TOO_MANY", "VALUE_MISSING", "VALUE_TYPE")
DATA_ELEMENTS = {"Property", "MultiLanguageProperty", "File", "Blob", "ReferenceElement"}
_BOUNDS = {"One": (1, 1), "ZeroToOne": (0, 1), "OneToMany": (1, None), "ZeroToMany": (0, None)}


@dataclass(frozen=True)
class Finding:
    kind: str
    path: str  # path in the submodel; for MISSING, the path the element is expected at
    detail: str = ""


def conforms(findings: list[Finding]) -> bool:
    return not any(f.kind in VIOLATIONS for f in findings)


def check(template: Template, submodel: Template) -> list[Finding]:
    T, I = template, submodel
    m = match(T, I)
    findings = []
    for t in T.E:
        if t == T.root:
            continue
        lo, hi = _BOUNDS.get(card(T, t), (0, None))
        name = T.E[t].id_short or "[]"
        for parent in m.R.get(T.E[t].parent, []):
            rs = [r for r in m.R.get(t, []) if I.E[r].parent == parent]
            where = f"{I.path(parent)}[*]" if name == "[]" else f"{I.path(parent)}.{name}".lstrip(".")
            if len(rs) < lo:
                findings.append(Finding("MISSING", where, f"{T.E[t].type}, cardinality {card(T, t)}"))
            if hi is not None and len(rs) > hi:
                findings.append(Finding("TOO_MANY", where, f"{len(rs)} realisations, cardinality {card(T, t)}"))
            for r in rs:
                findings += _check_values(T, I, t, r, lo, r in m.wild)
    realised = {r for rs in m.R.values() for r in rs}
    for x in I.E:
        if x not in realised and I.E[x].parent in realised - m.wild:
            findings.append(Finding("NOT_IN_TEMPLATE", I.path(x), I.E[x].type))
    return findings


def _value(T: Template, x: Id, name: str):
    a = T.attr(x, name)
    return None if a is None or T.A[a].value is LAMBDA else T.A[a].value


def _check_values(T: Template, I: Template, t: Id, r: Id, lo: int, wild: bool) -> list[Finding]:
    findings = []
    if lo and I.E[r].type in DATA_ELEMENTS and not placeholder(T, t) and _value(I, r, "value") in (None, "", []):
        findings.append(Finding("VALUE_MISSING", I.path(r), I.E[r].type))
    expected = _value(T, t, "valueType")
    if not wild and expected is not None and _value(I, r, "valueType") != expected:
        findings.append(Finding("VALUE_TYPE", I.path(r), f"{_value(I, r, 'valueType')}, template: {expected}"))
    return findings
