"""Guarded application of operators and operation chains  (paper §3.4, Fig. 1c).

    guarded(op, T) = (op(T), ACC)   if pre(op) holds in T
                   = (T,     REJ)   otherwise

The operator is applied to a copy, so a rejected operator writes no position of T. A chain is
applied item by item, each item evaluated against the state produced by its predecessors
(paper §3.5). If any item is rejected, the chain is rejected and the input T is returned
unchanged: there is no partially applied chain. For speed, a chain is applied to a single working
copy of T (apply_in_place): pre is evaluated before every operator, as in guarded, and the working
copy is discarded if an item is rejected, so the result is the same.

At the chain boundary the completion obligation is checked: every component touched by the
chain must carry all its mandatory attributes with a populated value.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from tcn.core.metamodel import mand
from tcn.core.model import LAMBDA, Template
from tcn.core.operators import Operator, Position

ACC, REJ = "ACC", "REJ"


class Unbound(Exception):
    """An item of a chain cannot be bound to components of the current state."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail = code, detail


class Item(Protocol):
    def bind(self, T: Template) -> Operator: ...


@dataclass
class Outcome:
    status: str
    op: Operator | None = None
    reason: str | None = None


@dataclass
class ChainResult:
    status: str
    template: Template
    outcomes: list[Outcome] = field(default_factory=list)
    reason: str | None = None
    mod: set[Position] = field(default_factory=set)


def guarded(op: Operator, T: Template) -> tuple[Template, Outcome]:
    if (reason := op.pre(T)) is not None:
        return T, Outcome(REJ, op, reason)
    T2 = T.copy()
    op.apply(T2)
    return T2, Outcome(ACC, op)


def apply_in_place(op: Operator, T: Template) -> Outcome:
    """guarded without the copy: T itself becomes op(T) if pre(op) holds and is left unchanged
    otherwise. Only for a state the caller owns and does not need in its earlier form."""
    if (reason := op.pre(T)) is not None:
        return Outcome(REJ, op, reason)
    op.apply(T)
    return Outcome(ACC, op)


def apply_chain(items: list[Item], T: Template) -> ChainResult:
    current, outcomes, mod, touched = T.copy(), [], set(), set()
    for i, item in enumerate(items, start=1):
        try:
            op = item.bind(current)
        except Unbound as u:
            outcomes.append(Outcome(REJ, None, u.code))
            return ChainResult(REJ, T, outcomes, f"item {i}: {u}")
        m = op.mod(current)
        touched |= _touched(m, current)  # owners before the operator
        outcome = apply_in_place(op, current)
        outcomes.append(outcome)
        if outcome.status == REJ:
            return ChainResult(REJ, T, outcomes, f"item {i}: {outcome.reason} ({op})")
        mod |= m
        touched |= _touched(m, current)  # owners after the operator
    if missing := obligations(current, touched):
        return ChainResult(REJ, T, outcomes, f"MANDATORY_ATTR_MISSING: {sorted(missing)}")
    return ChainResult(ACC, current, outcomes, mod=mod)


def _touched(m: set[Position], T: Template) -> set[int]:
    """Components in mod, plus the owners in T of the attributes in mod."""
    xs = {x for _, x in m}
    return xs | {T.A[x].owner for x in xs if x in T.A}


def obligations(T: Template, touched: set[int]) -> set[tuple[str, str]]:
    """Ob(Δ): (owner, attribute) pairs of touched components lacking a populated mandatory value."""
    missing = set()
    for x in touched & (T.E.keys() | T.Q.keys()):
        for n in mand(T.tau(x)):
            a = T.attr(x, n)
            if a is None or T.A[a].value is LAMBDA:
                owner = T.path(x) if x in T.E else f"{T.path(T.Q[x].elem)}@{T.Q[x].qtype}"
                missing.add((owner, n))
    return missing
