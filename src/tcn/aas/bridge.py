"""Boundary between the AAS serialisation (aas-core3.1) and the formal model T = (T_E, T_Q, T_A).

aas-core3.1 is the gatekeeper: every submodel entering or leaving the formal model is parsed by
it, so only metamodel-shaped JSON crosses the boundary. The decomposition itself is a direct
reading of the JSON tree:

    JSON object with modelType     ->  element (idShort, type, parent)
    entry of "qualifiers"          ->  qualifier (qtype = "type", elem)
    any other key                  ->  attribute (name = key, value = JSON value, owner)
    containment key (see CONTAINMENT_KEY)  ->  parent of the contained elements
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aas_core3_1 import jsonization, types as aas_types, verification

from tcn.core.metamodel import CONTAINMENT_KEY
from tcn.core.model import LAMBDA, Attribute, Element, Id, Qualifier, Template

_STRUCTURAL = {"modelType", "idShort", "qualifiers"}


# --- files ------------------------------------------------------------------------------


def load_submodel(path: str | Path, index: int = 0) -> dict[str, Any]:
    """Read a submodel from an AAS environment JSON file, normalised by aas-core."""
    env = jsonization.environment_from_jsonable(json.loads(Path(path).read_text(encoding="utf-8")))
    return jsonization.to_jsonable(env.submodels[index])


def normalise(submodel: dict[str, Any]) -> dict[str, Any]:
    """Parse with aas-core (raises on malformed input) and serialise back."""
    return jsonization.to_jsonable(jsonization.submodel_from_jsonable(submodel))


def verify(submodel: dict[str, Any]) -> list[str]:
    """Violations of metamodel constraints, as reported by aas-core."""
    obj: aas_types.Submodel = jsonization.submodel_from_jsonable(submodel)
    return [f"{e.path}: {e.cause}" for e in verification.verify(obj)]


# --- JSON -> T --------------------------------------------------------------------------


def from_jsonable(submodel: dict[str, Any]) -> Template:
    t = Template()
    t.root = _add_element(t, normalise(submodel), parent=None)
    return t


def _add_element(t: Template, d: dict[str, Any], parent: Id | None) -> Id:
    typ = d["modelType"]
    if typ == "Operation":
        raise NotImplementedError("Operation variables are outside the scope of the demonstrator")
    e = t.new_id()
    t.E[e] = Element(d.get("idShort"), typ, parent)
    container_key = CONTAINMENT_KEY.get(typ)
    for key, value in d.items():
        if key not in _STRUCTURAL and key != container_key:
            t.A[t.new_id()] = Attribute(key, value, e)
    for qd in d.get("qualifiers", []):
        q = t.new_id()
        t.Q[q] = Qualifier(qd["type"], e)
        for key, value in qd.items():
            if key != "type":
                t.A[t.new_id()] = Attribute(key, value, q)
    for child in d.get(container_key, []) if container_key else []:
        _add_element(t, child, parent=e)
    return e


# --- T -> JSON --------------------------------------------------------------------------


def to_jsonable(t: Template) -> dict[str, Any]:
    """Serialise T. Unpopulated attributes (λ) are omitted; aas-core then rejects the result
    if a mandatory one is missing, which is the intended behaviour."""
    return normalise(_build(t, t.root))


def _build(t: Template, e: Id) -> dict[str, Any]:
    el = t.E[e]
    d: dict[str, Any] = {"modelType": el.type}
    if el.id_short is not None:
        d["idShort"] = el.id_short
    d |= _populated(t, e)
    if quals := t.qualifiers(e):
        d["qualifiers"] = [{"type": t.Q[q].qtype} | _populated(t, q) for q in quals]
    if (key := CONTAINMENT_KEY.get(el.type)) and (children := t.children(e)):
        d[key] = [_build(t, c) for c in children]
    return d


def _populated(t: Template, x: Id) -> dict[str, Any]:
    return {t.A[a].name: t.A[a].value for a in t.attributes(x) if t.A[a].value is not LAMBDA}
