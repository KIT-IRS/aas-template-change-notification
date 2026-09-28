"""SMT drop-ins: the effective template, with the content of the drop-ins it uses.

A published template may leave the content of an element to an SMT drop-in: the element carries
the supplementalSemanticId DROPIN_USE and no children. The effective template inserts the content
of every drop-in found in the catalogue (ressources/DropIns/catalogue.yaml). Chains, resolution and
conformance all work on effective templates. A drop-in not in the catalogue stays unresolved; the
asset maintainer is asked for it (see tcn.roles.coevolution).
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from tcn.aas import bridge
from tcn.core.metamodel import CONTAINMENT_KEY

DROPIN_USE = "https://admin-shell.io/smt-dropin/smt-dropin-use/1/0"
CATALOGUE = Path("ressources/DropIns/catalogue.yaml")


def _key(reference: dict[str, Any] | None) -> str | None:
    return reference["keys"][0]["value"] if reference else None


def uses_dropin(element: dict[str, Any]) -> bool:
    return DROPIN_USE in [_key(r) for r in element.get("supplementalSemanticIds", [])]


def catalogue() -> dict[str, dict[str, Any]]:
    entries = yaml.safe_load(CATALOGUE.read_text(encoding="utf-8")) if CATALOGUE.exists() else []
    return {e["semanticId"]: e for e in entries}


def content(entry: dict[str, Any]) -> list[dict[str, Any]]:
    """The children the drop-in contributes, with the mandatory ones declared One."""
    source = bridge.load_submodel(entry["source"])
    holder = next(e for e in source["submodelElements"] if e.get("idShort") == entry["element"])
    children = copy.deepcopy(holder.get("value", []))
    for c in children:
        if c.get("idShort") in entry.get("mandatory", []):
            for q in c.get("qualifiers", []):
                if q["type"] in ("SMT/Cardinality", "Multiplicity", "Cardinality"):
                    q["value"] = "One"
    return children


def effective(submodel: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """The effective template, and the paths of drop-in uses that could not be resolved."""
    sm, known, unresolved = copy.deepcopy(submodel), catalogue(), []

    def walk(d: dict[str, Any], path: str) -> None:
        key = CONTAINMENT_KEY.get(d["modelType"])
        if uses_dropin(d) and not d.get(key):
            entry = known.get(_key(d.get("semanticId")))
            if entry:
                d[key] = content(entry)
            else:
                unresolved.append(path)
        for c in d.get(key, []) if key else []:
            walk(c, f"{path}.{c.get('idShort', '[]')}".lstrip("."))

    walk(sm, "")
    return bridge.normalise(sm), unresolved


def load(path: str | Path) -> dict[str, Any]:
    """A template file as effective template."""
    return effective(bridge.load_submodel(path))[0]
