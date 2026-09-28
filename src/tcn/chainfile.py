"""Chain documents: the authoring format of a TCN record (YAML).

A chain document carries the record header (Fig. 3) and the operation chain, grouped into
sections. Each section states where its items come from:

    origin: hand       written by the template owner; carries the intent of the revision
    origin: rule       expanded in place from a rule the owner declared (see template_owner.RULES)
    origin: generated  mechanical completion of the remaining differences

Item keys are the argument names of Table 2, so a document can be read against the paper.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from tcn.core.addressing import Item
from tcn.core.transfer import Expression, Identity, Instruction, TransferFunction, ValueMap

# Table 2 argument name  <->  Item field
_KEYS = {
    "ElementPath": "element_path", "SMEType": "sme_type", "QualifierType": "qualifier_type",
    "AttributeKey": "attribute_key", "AttributeValue": "attribute_value",
    "NewIdShort": "new_id_short", "NewParentPath": "new_parent_path",
    "SourceElementPaths": "source_paths", "TargetElementPaths": "target_paths",
}


@dataclass
class Section:
    title: str
    origin: str
    items: list[Item] = field(default_factory=list)
    rule: dict[str, Any] | None = None  # only for origin: rule


@dataclass
class Chain:
    header: dict[str, Any]
    sections: list[Section] = field(default_factory=list)

    @property
    def items(self) -> list[Item]:
        return [i for s in self.sections for i in s.items]


# --- transfer functions ------------------------------------------------------------------


def transfer_from_dict(d: dict[str, Any]) -> TransferFunction:
    match d["Kind"]:
        case "Identity":
            return Identity()
        case "ValueMap":
            return ValueMap(dict(d["Pairs"]))
        case "Expression":
            return Expression(d["ExpressionLanguage"], d["Expression"], dict(d.get("Text", {})))
        case "Instruction":
            return Instruction(dict(d["Text"]))
    raise ValueError(f"unknown transfer function kind {d['Kind']}")


def transfer_to_dict(f: TransferFunction) -> dict[str, Any]:
    match f:
        case ValueMap(pairs):
            return {"Kind": "ValueMap", "Pairs": dict(pairs)}
        case Expression(language, expression, text):
            return {"Kind": "Expression", "ExpressionLanguage": language, "Expression": expression} | (
                {"Text": dict(text)} if text else {})
        case Instruction(text):
            return {"Kind": "Instruction", "Text": dict(text)}
    return {"Kind": f.kind}


# --- items ------------------------------------------------------------------------------


def item_from_dict(d: dict[str, Any]) -> Item:
    kwargs = {field_: d[key] for key, field_ in _KEYS.items() if key in d}
    if "TransferFunction" in d:
        kwargs["transfer"] = transfer_from_dict(d["TransferFunction"])
    return Item(d["ChangeOperation"], **kwargs)


def item_to_dict(item: Item) -> dict[str, Any]:
    d: dict[str, Any] = {"ChangeOperation": item.operation}
    for key, field_ in _KEYS.items():
        value = getattr(item, field_)
        if value is None or value == [] or (key == "ElementPath" and item.operation == "Sync"):
            continue  # "" is a valid path: the root
        d[key] = value
    if item.transfer is not None:
        d["TransferFunction"] = transfer_to_dict(item.transfer)
    return d


# --- files ------------------------------------------------------------------------------


def load(path: str | Path) -> Chain:
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    sections = [Section(s["title"], s["origin"], [item_from_dict(i) for i in s.get("items") or []],
                        s.get("rule"))
                for s in doc.get("sections", [])]
    return Chain(doc["header"], sections)


def dump(chain: Chain, path: str | Path) -> None:
    doc = {"header": chain.header, "sections": [
        {"title": s.title, "origin": s.origin} | ({"rule": s.rule} if s.rule else {})
        | {"items": [item_to_dict(i) for i in s.items]}
        for s in chain.sections]}
    Path(path).write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=120),
                          encoding="utf-8")
