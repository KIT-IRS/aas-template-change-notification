"""Identification of components by native AAS means  (paper §3.5, Table 2).

    element    ElementPath                         e.g.  GeneralInformation.ManufacturerName
    qualifier  ElementPath + QualifierType               TechnicalPropertyAreas  +  SMT/Cardinality
    attribute  ElementPath [+ QualifierType] + AttributeKey

ElementPath follows the idShort path of the AAS API: '.'-separated idShorts, list entries by
position '[i]'; the root (the submodel) has the empty path. Sync addresses attributes with a
single string  <ElementPath>[@<QualifierType>]#<AttributeKey>  (split on first '@', last '#').

An Item is one ItemOfChange. It is bound to components of the *current* state, i.e. the state
resulting from all preceding items of the chain.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from tcn.core import operators as ops
from tcn.core.guarded import Unbound
from tcn.core.model import Id, Template
from tcn.core.transfer import TransferFunction

_TOKEN = re.compile(r"\[\d+\]|[^.\[\]]+")


def tokens(path: str) -> list[str]:
    return _TOKEN.findall(path)


def element(T: Template, path: str | list[str], code: str = "TARGET_EXISTS") -> Id:
    e = T.root
    for tok in tokens(path) if isinstance(path, str) else path:
        children = T.children(e)
        if tok.startswith("["):
            i = int(tok[1:-1])
            e = children[i] if i < len(children) else None
        else:
            e = next((c for c in children if T.E[c].id_short == tok), None)
        if e is None:
            raise Unbound(code, path)
    return e


def qualifier(T: Template, path: str, qtype: str) -> Id:
    e = element(T, path)
    q = next((q for q in T.qualifiers(e) if T.Q[q].qtype == qtype), None)
    if q is None:
        raise Unbound("QUAL_ABSENT", f"{path}@{qtype}")
    return q


def owner(T: Template, path: str, qtype: str | None) -> Id:
    return qualifier(T, path, qtype) if qtype else element(T, path)


def attribute(T: Template, path: str, qtype: str | None, key: str) -> Id:
    a = T.attr(owner(T, path, qtype), key)
    if a is None:
        raise Unbound("ATTR_ABSENT", f"{path}{'@' + qtype if qtype else ''}#{key}")
    return a


def split_attribute_ref(ref: str) -> tuple[str, str | None, str]:
    """'A.B@SMT/Cardinality#value' -> ('A.B', 'SMT/Cardinality', 'value')"""
    head, key = ref.rsplit("#", 1)
    path, _, qtype = head.partition("@")
    return path, qtype or None, key


@dataclass
class Item:
    """One ItemOfChange: ChangeOperation plus OperationArguments (Table 2)."""

    operation: str
    element_path: str = ""
    sme_type: str | None = None
    qualifier_type: str | None = None
    attribute_key: str | None = None
    attribute_value: Any = None
    new_id_short: str | None = None
    new_parent_path: str | None = None
    source_paths: list[str] = field(default_factory=list)
    target_paths: list[str] = field(default_factory=list)
    transfer: TransferFunction | None = None

    def bind(self, T: Template) -> ops.Operator:
        path, q, key = self.element_path, self.qualifier_type, self.attribute_key
        match self.operation:
            case "CreateSME":
                *parent, last = tokens(path)
                p = element(T, parent, code="PARENT_EXISTS")
                if last.startswith("["):
                    if int(last[1:-1]) != len(T.children(p)):
                        raise Unbound("INDEX_POSITION", f"{path}: list entries are appended")
                    return ops.CreateSME(p, self.sme_type, None)
                return ops.CreateSME(p, self.sme_type, last)
            case "CreateQual":
                return ops.CreateQual(element(T, path), q)
            case "CreateAttr":
                return ops.CreateAttr(owner(T, path, q), key)
            case "UpdateIdShort":
                return ops.UpdateIdShort(element(T, path), self.new_id_short)
            case "UpdateParent":
                return ops.UpdateParent(element(T, path),
                                        element(T, self.new_parent_path, code="PARENT_EXISTS"))
            case "UpdateAttr":
                return ops.UpdateAttr(attribute(T, path, q, key), self.attribute_value)
            case "RemoveSME":
                return ops.RemoveSME(element(T, path))
            case "RemoveQual":
                return ops.RemoveQual(qualifier(T, path, q))
            case "RemoveAttr":
                return ops.RemoveAttr(attribute(T, path, q, key))
            case "Sync":
                return ops.Sync([attribute(T, *split_attribute_ref(r)) for r in self.source_paths],
                                [attribute(T, *split_attribute_ref(r)) for r in self.target_paths],
                                self.transfer)
        raise Unbound("UNKNOWN_OPERATION", self.operation)
