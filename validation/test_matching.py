"""Matching of template siblings that share type and semanticId (rule M1 of tcn.core.matching).

The semanticId does not tell such siblings apart: an instance child realises the one whose
supplementalSemanticIds it carries, if these differ among the siblings, and otherwise the one with its
idShort. An instance child that none of them claims is a local extension; nothing of it is lost.
"""

from tcn import chainfile, instantiate
from tcn.aas import bridge
from tcn.core.conformance import check
from tcn.core.addressing import element
from tcn.core.guarded import ACC, apply_chain
from tcn.core.matching import match
from tcn.core.resolution import resolve
from tcn.roles.template_owner import load_templates


def _ref(value):
    return {"type": "ExternalReference", "keys": [{"type": "GlobalReference", "value": value}]}


def _prop(id_short, semantic_id, value=None, supplemental=()):
    d = {"modelType": "Property", "idShort": id_short, "valueType": "xs:string", "semanticId": _ref(semantic_id)}
    if supplemental:
        d["supplementalSemanticIds"] = [_ref(s) for s in supplemental]
    return d | ({"value": value} if value is not None else {})


def _sm(kind, *elements):
    return bridge.from_jsonable({"modelType": "Submodel", "id": f"urn:test:{kind}", "kind": kind,
                                 "submodelElements": list(elements)})


def _realised_by(T, I):
    """template idShort -> idShorts of its realisations"""
    m = match(T, I)
    return {T.E[t].id_short: sorted(I.E[i].id_short for i in rs) for t, rs in m.R.items() if t != T.root}


def test_siblings_with_one_semantic_id_are_told_apart_by_idshort():
    T = _sm("Template", _prop("from", "urn:date"), _prop("until", "urn:date"))
    I = _sm("Instance", _prop("until", "urn:date", "2026-12-31"), _prop("from", "urn:date", "2026-01-01"))
    assert _realised_by(T, I) == {"from": ["from"], "until": ["until"]}


def test_siblings_with_one_semantic_id_are_told_apart_by_supplemental_semantic_ids():
    # as the interfaces of the Asset Interfaces Description: one semanticId, the protocol as
    # supplementalSemanticId, names chosen by the instance
    T = _sm("Template", _prop("InterfaceTemplateForHTTP", "urn:interface", supplemental=["urn:http", "urn:td"]),
            _prop("InterfaceTemplateForMQTT", "urn:interface", supplemental=["urn:mqtt", "urn:td"]))
    I = _sm("Instance", _prop("Broker", "urn:interface", "x", supplemental=["urn:mqtt", "urn:td"]),
            _prop("Api", "urn:interface", "y", supplemental=["urn:http", "urn:td"]))
    assert _realised_by(T, I) == {"InterfaceTemplateForHTTP": ["Api"], "InterfaceTemplateForMQTT": ["Broker"]}


def test_a_renamed_sibling_is_a_local_extension():
    T = _sm("Template", _prop("from", "urn:date"), _prop("until", "urn:date"))
    I = _sm("Instance", _prop("from", "urn:date", "2026-01-01"), _prop("validUntil", "urn:date", "2026-12-31"))
    assert _realised_by(T, I) == {"from": ["from"], "until": []}
    assert {(f.kind, f.path) for f in check(T, I)} >= {("NOT_IN_TEMPLATE", "validUntil")}


def test_a_renamed_sibling_is_not_lost_by_a_chain():
    """Energy Flexibility v1.0 -> v1.1 with flexibleLoadId (semanticId .../UUID, as flexibleLoadMeasureId)
    renamed in the instance: it is a local extension. The chain rebuilds the measure (RenameContainer);
    the local extension moves into the rebuilt measure with its value (H2), which is reported, and the
    missing flexibleLoadId is reported by the conformance check."""
    sm = instantiate.load("fixtures/energyflexibility_1.0.yaml")
    entry = sm["submodelElements"][0]["value"][1]["value"][0]  # flexibleLoadMeasuresPackage.flexibleLoadMeasures[0]
    next(c for c in entry["value"] if c["idShort"] == "flexibleLoadId")["idShort"] = "loadId"
    I = bridge.from_jsonable(sm)
    chain = chainfile.load("chains/energyflexibility_1.0_to_1.1.yaml")
    pre, post = load_templates(chain)
    findings = {(f.kind, f.path) for f in check(pre, I)}
    assert ("NOT_IN_TEMPLATE", "flexibleLoadMeasuresPackage.flexibleLoadMeasures[0].loadId") in findings
    assert ("TOO_MANY", "flexibleLoadMeasuresPackage.flexibleLoadMeasures[0].flexibleLoadMeasureId") not in findings
    res = resolve(chain.items, pre, I)
    assert res.status == ACC, res.reason
    assert any(n.kind == "inserted" and "loadId" in n.detail for n in res.notes)
    result = apply_chain(res.items, I).template
    measure = "flexibleLoadMeasuresPackage.flexibleLoadMeasures[0]"
    assert result.A[result.attr(element(result, f"{measure}.loadId"), "value")].value == "L-heater"
    assert ("MISSING", f"{measure}.flexibleLoadId") in {(f.kind, f.path) for f in check(post, result)}
