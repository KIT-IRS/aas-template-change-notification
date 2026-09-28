"""The Template Change Notification submodel  (paper §3.2, Fig. 3, Table 2).

The structure is stated once, in SPEC, and used for both the Submodel Template (written to
ressources/Templates/Template_TemplateChangeNotification.v0_4.json) and its instances:

    TCNGroups[i]                     one group per observed template
        ObservedSMT, SMInstance
        TCNRecords[j]                one record per version transition
            NotificationId, ChangeURI, DateOfRecord, AffectedSMT,
            TemplateOwner (TemplateOwnerName, AddressInformation: SMT drop-in as in the Nameplate v3.0),
            PreVersion, PostVersion
            ItemsOfChange[k]         the operation chain, in order
                ChangeOperation
                OperationArguments   the arguments of Table 2

AttributeValue is a string holding the JSON encoding of the value (e.g. "\"xs:string\"", "false", or a
semanticId object), so that every attribute value of the AAS serialisation is carried unambiguously.
"""

from __future__ import annotations

import json
from typing import Any

from tcn.chainfile import Chain, Section, transfer_from_dict, transfer_to_dict
from tcn.core.addressing import Item

SUBMODEL_ID = "https://www.irs.kit.edu/SubmodelTemplate/TemplateChangeNotification/0/4"
_SEM = "https://www.irs.kit.edu/idta/tcn/0/4/"
_CARDINALITY_SEM = "https://admin-shell.io/SubmodelTemplates/Cardinality/1/0"
OPERATIONS = ["CreateSME", "CreateQual", "CreateAttr", "UpdateIdShort", "UpdateParent", "UpdateAttr",
              "RemoveSME", "RemoveQual", "RemoveAttr", "Sync"]

# (idShort, modelType, cardinality, valueType or list entry type, description, children)
# A list's single child is its entry template; its idShort is used only for its semanticId.
_ARGUMENTS = [
    ("ElementPath", "Property", "ZeroToOne", "xs:string", "idShort path of the element, or of the owner of the qualifier or attribute", []),
    ("SMEType", "Property", "ZeroToOne", "xs:string", "CreateSME: model type of the created element", []),
    ("QualifierType", "Property", "ZeroToOne", "xs:string", "type of the qualifier, or of the qualifier owning the attribute", []),
    ("AttributeKey", "Property", "ZeroToOne", "xs:string", "name of the attribute (key of the AAS JSON serialisation)", []),
    ("AttributeValue", "Property", "ZeroToOne", "xs:string", "UpdateAttr: new value, JSON-encoded", []),
    ("NewIdShort", "Property", "ZeroToOne", "xs:string", "UpdateIdShort: new idShort", []),
    ("NewParentPath", "Property", "ZeroToOne", "xs:string", "UpdateParent: idShort path of the new parent", []),
    ("SourceElementPaths", "SubmodelElementList", "ZeroToOne", "Property", "Sync: source attributes <path>[@<qualifierType>]#<attribute>", [
        ("SourceElementPath", "Property", "OneToMany", "xs:string", "", [])]),
    ("TargetElementPaths", "SubmodelElementList", "ZeroToOne", "Property", "Sync: target attributes, paired positionally with the sources", [
        ("TargetElementPath", "Property", "OneToMany", "xs:string", "", [])]),
    ("TransferFunction", "SubmodelElementCollection", "ZeroToOne", None, "Sync: transfer function f", [
        ("Kind", "Property", "One", "xs:string", "Identity | ValueMap | Expression | Instruction", []),
        ("ValueMap", "SubmodelElementList", "ZeroToOne", "SubmodelElementCollection", "pairs of source and target values", [
            ("ValuePair", "SubmodelElementCollection", "OneToMany", None, "", [
                ("SourceValue", "Property", "One", "xs:string", "", []),
                ("TargetValue", "Property", "One", "xs:string", "", [])])]),
        ("ExpressionLanguage", "Property", "ZeroToOne", "xs:anyURI",
         "URI of a side-effect-free expression language, e.g. https://github.com/google/cel-spec (CEL); "
         "a receiver evaluates only languages it supports, never code", []),
        ("Expression", "Property", "ZeroToOne", "xs:string",
         "expression over the source values `src`, yielding the target value(s)", []),
        ("Instruction", "MultiLanguageProperty", "ZeroToOne", None,
         "instruction for the asset maintainer; with an Expression, for receivers that do not evaluate "
         "its language", [])]),
]
_ITEM = ("ItemOfChange", "SubmodelElementCollection", "OneToMany", None, "one atomic operation", [
    ("ChangeOperation", "Property", "One", "xs:string", " | ".join(OPERATIONS), []),
    ("OperationArguments", "SubmodelElementCollection", "One", None, "arguments of the operation (paper, Table 2)", _ARGUMENTS)])
_RECORD = ("TCNRecord", "SubmodelElementCollection", "OneToMany", None, "one version transition of the observed template", [
    ("NotificationId", "Property", "One", "xs:string", "identifier of the notification", []),
    ("ChangeURI", "Property", "One", "xs:anyURI", "publication of the change", []),
    ("DateOfRecord", "Property", "One", "xs:dateTime", "date of the record", []),
    ("TemplateOwner", "SubmodelElementCollection", "One", None, "issuing template owner", [
        ("TemplateOwnerName", "MultiLanguageProperty", "One", None, "name of the template owner", []),
        ("AddressInformation", "SubmodelElementCollection", "ZeroToOne", None,
         'Note: this set of information is defined by SMT drop-in "Address Information"', [])]),
    ("AffectedSMT", "ReferenceElement", "ZeroToOne", None, "template the record applies to", []),
    ("PreVersion", "Property", "One", "xs:anyURI", "identifier of the template version before the change", []),
    ("PostVersion", "Property", "One", "xs:anyURI", "identifier of the template version after the change", []),
    ("ItemsOfChange", "SubmodelElementList", "One", "SubmodelElementCollection", "the operation chain, in order", [_ITEM])])
_GROUP = ("TCNGroup", "SubmodelElementCollection", "ZeroToMany", None, "notifications of one observed template", [
    ("ObservedSMT", "ReferenceElement", "One", None, "the observed Submodel Template", []),
    ("SMInstance", "ReferenceElement", "ZeroToOne", None, "the submodel conforming to it", []),
    ("TCNRecords", "SubmodelElementList", "One", "SubmodelElementCollection", "one record per version transition", [_RECORD])])
SPEC = [("TCNGroups", "SubmodelElementList", "One", "SubmodelElementCollection", "one group per observed template", [_GROUP])]


def _ref(value: str, model: bool = False) -> dict[str, Any]:
    kind = "Submodel" if model else "GlobalReference"
    return {"type": "ModelReference" if model else "ExternalReference", "keys": [{"type": kind, "value": value}]}


# Elements reused from other templates keep their semantics: the drop-in Address Information is
# referenced exactly as in the Digital Nameplate v3.0.
_REUSED = {
    "AddressInformation": {
        "semanticId": _ref("https://admin-shell.io/zvei/nameplate/1/0/ContactInformations/AddressInformation"),
        "supplementalSemanticIds": [_ref("https://admin-shell.io/smt-dropin/smt-dropin-use/1/0")],
    },
}


# Content of the drop-in used in records: the properties of the ZVEI contact information concept the
# drop-in refers to, with their semanticIds as in the Digital Nameplate v2.0.
_ADDRESS = {"Company": "0173-1#02-AAW001#001", "Street": "0173-1#02-AAO128#002",
            "Zipcode": "0173-1#02-AAO129#002", "CityTown": "0173-1#02-AAO132#002",
            "NationalCode": "0173-1#02-AAO134#002"}


def _sem(id_short: str) -> dict[str, Any]:
    return _REUSED.get(id_short, {}).get("semanticId") or _ref(_SEM + id_short)


# --- the Submodel Template ---------------------------------------------------------------


def _template_element(spec, in_list: bool = False) -> dict[str, Any]:
    id_short, model_type, cardinality, extra, description, children = spec
    d: dict[str, Any] = {"modelType": model_type}
    if not in_list:
        d["idShort"] = id_short
    if description:
        d["description"] = [{"language": "en", "text": description}]
    d["semanticId"] = _sem(id_short)
    if sup := _REUSED.get(id_short, {}).get("supplementalSemanticIds"):
        d["supplementalSemanticIds"] = sup
    d["qualifiers"] = [{"kind": "TemplateQualifier", "semanticId": _ref(_CARDINALITY_SEM),
                        "type": "SMT/Cardinality", "valueType": "xs:string", "value": cardinality}]
    if model_type == "Property":
        d["valueType"] = extra
    if model_type == "SubmodelElementList":
        d["orderRelevant"] = id_short == "ItemsOfChange"
        d["semanticIdListElement"] = _sem(children[0][0])
        d["typeValueListElement"] = extra
        if extra == "Property":
            d["valueTypeListElement"] = children[0][3]
        d["value"] = [_template_element(children[0], in_list=True)]
    elif children:
        d["value"] = [_template_element(c) for c in children]
    return d


def template() -> dict[str, Any]:
    """The TCN Submodel Template as an AAS environment."""
    return {"submodels": [{
        "modelType": "Submodel", "kind": "Template", "id": SUBMODEL_ID, "idShort": "TemplateChangeNotifications",
        "administration": {"version": "0", "revision": "4"}, "semanticId": _ref(SUBMODEL_ID),
        "description": [{"language": "en", "text": "Template Change Notifications: the operation chains of the "
                         "version transitions of observed Submodel Templates."}],
        "submodelElements": [_template_element(s) for s in SPEC]}]}


# --- instances ----------------------------------------------------------------------------


def _prop(id_short: str, value: str, value_type: str = "xs:string", entry: bool = False) -> dict[str, Any]:
    """A Property; a list entry (entry=True) carries no idShort, only the semanticId of its name."""
    d = {"modelType": "Property", "semanticId": _sem(id_short), "valueType": value_type, "value": value}
    return d if entry else {"idShort": id_short} | d


def _list(id_short: str, entry: str, entries: list[dict], entry_type="SubmodelElementCollection", vt=None):
    d = {"modelType": "SubmodelElementList", "idShort": id_short, "semanticId": _sem(id_short),
         "orderRelevant": id_short == "ItemsOfChange", "semanticIdListElement": _sem(entry),
         "typeValueListElement": entry_type}
    if vt:
        d["valueTypeListElement"] = vt
    return d | ({"value": entries} if entries else {})


def _smc(id_short: str | None, sem: str, value: list[dict]) -> dict[str, Any]:
    return ({"idShort": id_short} if id_short else {}) | {
        "modelType": "SubmodelElementCollection", "semanticId": _sem(sem), "value": value}


def empty(submodel_id: str) -> dict[str, Any]:
    return {"modelType": "Submodel", "kind": "Instance", "id": submodel_id, "idShort": "TemplateChangeNotifications",
            "semanticId": _ref(SUBMODEL_ID), "submodelElements": [_list("TCNGroups", "TCNGroup", [])]}


def item_to_element(item: Item) -> dict[str, Any]:
    args: list[dict] = []
    for key, field_ in [("ElementPath", "element_path"), ("SMEType", "sme_type"), ("QualifierType", "qualifier_type"),
                        ("AttributeKey", "attribute_key"), ("NewIdShort", "new_id_short"),
                        ("NewParentPath", "new_parent_path")]:
        if (v := getattr(item, field_)) is not None and not (key == "ElementPath" and item.operation == "Sync"):
            args.append(_prop(key, v))
    if item.operation == "UpdateAttr":
        args.append(_prop("AttributeValue", json.dumps(item.attribute_value, ensure_ascii=False)))
    for key, entry, paths in [("SourceElementPaths", "SourceElementPath", item.source_paths),
                              ("TargetElementPaths", "TargetElementPath", item.target_paths)]:
        if paths:
            args.append(_list(key, entry, [_prop(entry, p, entry=True) for p in paths], "Property", "xs:string"))
    if item.transfer is not None:
        f = transfer_to_dict(item.transfer)
        tf = [_prop("Kind", f["Kind"])]
        if "Pairs" in f:
            tf.append(_list("ValueMap", "ValuePair", [_smc(None, "ValuePair", [_prop("SourceValue", s), _prop("TargetValue", t)])
                                                      for s, t in f["Pairs"].items()]))
        if "Expression" in f:
            tf += [_prop("ExpressionLanguage", f["ExpressionLanguage"], "xs:anyURI"), _prop("Expression", f["Expression"])]
        if "Text" in f:
            tf.append({"modelType": "MultiLanguageProperty", "idShort": "Instruction", "semanticId": _sem("Instruction"),
                       "value": [{"language": k, "text": t} for k, t in f["Text"].items()]})
        args.append(_smc("TransferFunction", "TransferFunction", tf))
    return _smc(None, "ItemOfChange", [_prop("ChangeOperation", item.operation),
                                       _smc("OperationArguments", "OperationArguments", args)])


def record(chain: Chain, notification_id: str, date: str) -> dict[str, Any]:
    """A TCNRecord for the chain (header fields from the chain document)."""
    h = chain.header
    return _smc(None, "TCNRecord", [
        _prop("NotificationId", notification_id),
        _prop("ChangeURI", h["ChangeURI"], "xs:anyURI"),
        _prop("DateOfRecord", date, "xs:dateTime"),
        _smc("TemplateOwner", "TemplateOwner", [
            {"modelType": "MultiLanguageProperty", "idShort": "TemplateOwnerName",
             "semanticId": _sem("TemplateOwnerName"), "value": [{"language": "en", "text": h["TemplateOwner"]}]},
            *([_address(h["TemplateOwnerAddress"])] if "TemplateOwnerAddress" in h else [])]),
        {"modelType": "ReferenceElement", "idShort": "AffectedSMT", "semanticId": _sem("AffectedSMT"),
         "value": _ref(h["PreVersion"])},
        _prop("PreVersion", h["PreVersion"], "xs:anyURI"),
        _prop("PostVersion", h["PostVersion"], "xs:anyURI"),
        _list("ItemsOfChange", "ItemOfChange", [item_to_element(i) for i in chain.items])])


def _address(address: dict[str, str]) -> dict[str, Any]:
    return {"modelType": "SubmodelElementCollection", "idShort": "AddressInformation", **_REUSED["AddressInformation"],
            "value": [{"modelType": "MultiLanguageProperty", "idShort": k, "semanticId": _ref(_ADDRESS[k]),
                       "value": [{"language": "en", "text": v}]} for k, v in address.items()]}


def group(observed_smt: str, sm_instance: str) -> dict[str, Any]:
    return _smc(None, "TCNGroup", [
        {"modelType": "ReferenceElement", "idShort": "ObservedSMT", "semanticId": _sem("ObservedSMT"),
         "value": _ref(observed_smt)},
        {"modelType": "ReferenceElement", "idShort": "SMInstance", "semanticId": _sem("SMInstance"),
         "value": _ref(sm_instance, model=True)},
        _list("TCNRecords", "TCNRecord", [])])


# --- reading ------------------------------------------------------------------------------


def _children(d: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {c["idShort"]: c for c in d.get("value", []) if "idShort" in c}


def element_to_item(entry: dict[str, Any]) -> Item:
    c = _children(entry)
    args = _children(c["OperationArguments"])
    val = lambda k: args[k]["value"] if k in args else None  # noqa: E731
    item = Item(c["ChangeOperation"]["value"], val("ElementPath") or "", val("SMEType"), val("QualifierType"),
                val("AttributeKey"), None, val("NewIdShort"), val("NewParentPath"),
                [p["value"] for p in args.get("SourceElementPaths", {}).get("value", [])],
                [p["value"] for p in args.get("TargetElementPaths", {}).get("value", [])])
    if "AttributeValue" in args:
        item.attribute_value = json.loads(args["AttributeValue"]["value"])
    if "TransferFunction" in args:
        tf = _children(args["TransferFunction"])
        f: dict[str, Any] = {"Kind": tf["Kind"]["value"]}
        if "ValueMap" in tf:
            f["Pairs"] = {p["SourceValue"]["value"]: p["TargetValue"]["value"]
                          for p in map(_children, tf["ValueMap"].get("value", []))}
        if "Expression" in tf:
            f |= {"ExpressionLanguage": tf["ExpressionLanguage"]["value"], "Expression": tf["Expression"]["value"]}
        if "Instruction" in tf:
            f["Text"] = {s["language"]: s["text"] for s in tf["Instruction"]["value"]}
        item.transfer = transfer_from_dict(f)
    return item


def record_to_chain(rec: dict[str, Any]) -> Chain:
    c = _children(rec)
    owner = _children(c["TemplateOwner"])
    header = {"NotificationId": c["NotificationId"]["value"], "PreVersion": c["PreVersion"]["value"],
              "PostVersion": c["PostVersion"]["value"], "ChangeURI": c["ChangeURI"]["value"],
              "DateOfRecord": c["DateOfRecord"]["value"],
              "TemplateOwner": owner["TemplateOwnerName"]["value"][0]["text"]}
    if "AddressInformation" in owner:
        header["TemplateOwnerAddress"] = {k: e["value"][0]["text"]
                                          for k, e in _children(owner["AddressInformation"]).items()}
    items = [element_to_item(e) for e in c["ItemsOfChange"].get("value", [])]
    return Chain(header, [Section("ItemsOfChange", "record", items)])
