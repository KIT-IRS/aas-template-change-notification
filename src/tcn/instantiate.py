"""Instantiate a Submodel Template into a submodel, as specified by a fixture document (YAML).

    template:  the Submodel Template to instantiate
    id:        identifier of the submodel instance
    omit:      template elements the instance does not realise (optional branches)
    repeat:    template element -> idShorts of its realisations (one copy each, in order); for an
               entry of a SubmodelElementList ('List[0]'), the number of entries
    values:    instance path -> value (Property, File: string; MultiLanguageProperty: {lang: text};
               ReferenceElement: the identifier referenced)
    add:       instance path -> elements (AAS JSON) the instance adds, e.g. concrete technical properties
    drop_empty: remove data elements without value, then empty collections and lists

The instance declares its template in administration.templateId. Steps, in this order: all
qualifiers are dropped (template constructs), placeholders named 'arbitrary' are dropped, example
values of the template are cleared, then omit, repeat, values and add are applied. The result is
parsed by aas-core.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from tcn.aas import bridge
from tcn.core.addressing import tokens
from tcn.core.metamodel import CONTAINMENT_KEY

VALUE_KEYS = {"value", "valueId", "min", "max"}


def _children(d: dict[str, Any]) -> list[dict[str, Any]]:
    key = CONTAINMENT_KEY.get(d["modelType"])
    return d.setdefault(key, []) if key else []


def _strip(d: dict[str, Any]) -> None:
    d.pop("qualifiers", None)
    if d["modelType"] not in CONTAINMENT_KEY:  # for containers, "value" holds the children
        for k in VALUE_KEYS:
            d.pop(k, None)
    kids = _children(d)
    kids[:] = [c for c in kids if "arbitrary" not in c.get("idShort", "").lower()]
    for c in kids:
        _strip(c)


def _find(root: dict[str, Any], path: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """(parent, element) for an idShort path."""
    parent, el = None, root
    for tok in tokens(path):
        kids = _children(el)
        parent, el = el, kids[int(tok[1:-1])] if tok.startswith("[") else next(
            c for c in kids if c.get("idShort") == tok)
    return parent, el


def instantiate(spec: dict[str, Any]) -> dict[str, Any]:
    sm = bridge.load_submodel(spec["template"])
    # the instance declares the template it conforms to (AdministrativeInformation/templateId)
    sm |= {"id": spec["id"], "kind": "Instance", "administration": {"templateId": sm["id"]}}
    _strip(sm)
    for path in spec.get("omit", []):
        parent, el = _find(sm, path)
        _children(parent).remove(el)
    for path, names in spec.get("repeat", {}).items():
        parent, el = _find(sm, path)
        siblings = _children(parent)
        i = siblings.index(el)
        if isinstance(names, int):  # entries of a list carry no idShort
            siblings[i:i + 1] = [copy.deepcopy(el) for _ in range(names)]
        else:
            siblings[i:i + 1] = [copy.deepcopy(el) | {"idShort": n} for n in names]
    for path, value in spec.get("values", {}).items():
        _, el = _find(sm, path)
        if el["modelType"] == "ReferenceElement":
            el["value"] = {"type": "ExternalReference", "keys": [{"type": "GlobalReference", "value": value}]}
        elif isinstance(value, dict):
            el["value"] = [{"language": k, "text": v} for k, v in value.items()]
        else:
            el["value"] = str(value)
    for path, elements in spec.get("add", {}).items():
        _, el = _find(sm, path)
        _children(el).extend(copy.deepcopy(elements))
    if spec.get("drop_empty"):
        _drop_empty(sm)
    _prune(sm)
    return bridge.normalise(sm)


def _drop_empty(d: dict[str, Any]) -> bool:
    """True if d is empty after dropping its empty descendants."""
    kids = _children(d)
    kids[:] = [c for c in kids if not _drop_empty(c)]
    if d["modelType"] in CONTAINMENT_KEY:
        return not kids
    return "value" not in d


def _prune(d: dict[str, Any]) -> None:
    """Empty containment lists are not serialisable; they are dropped."""
    key = CONTAINMENT_KEY.get(d["modelType"])
    if key and key in d:
        for c in d[key]:
            _prune(c)
        if not d[key]:
            del d[key]


def load(path: str | Path) -> dict[str, Any]:
    return instantiate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))
