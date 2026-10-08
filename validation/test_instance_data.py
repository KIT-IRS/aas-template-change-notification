"""Instance data beyond value (rules T2 and V1 of tcn.core.resolution): the attributes that hold the
value of an element of its type, e.g. the contentType of a File or the globalAssetId of an Entity, are
never overwritten by the template and are reported when the chain removes them."""

from tcn.aas import bridge
from tcn.core.addressing import Item, element
from tcn.core.guarded import ACC, apply_chain
from tcn.core.resolution import resolve


def _sm(kind, *elements):
    return bridge.from_jsonable({"modelType": "Submodel", "id": f"urn:test:{kind}", "kind": kind,
                                 "submodelElements": list(elements)})


def _resolve_and_apply(items, T, I):
    res = resolve(items, T, I)
    assert res.status == ACC, res.reason
    out = apply_chain(res.items, I)
    assert out.status == ACC, out.reason
    return res, out.template


def test_the_content_type_of_a_file_is_not_overwritten_by_the_template():
    T = _sm("Template", {"modelType": "File", "idShort": "Manual", "contentType": "application/pdf"})
    I = _sm("Instance", {"modelType": "File", "idShort": "Manual", "contentType": "text/html", "value": "/manual.html"})
    item = Item("UpdateAttr", "Manual", attribute_key="contentType", attribute_value="application/x-pdf")
    _, result = _resolve_and_apply([item], T, I)
    attrs = {result.A[a].name: result.A[a].value for a in result.attributes(element(result, "Manual"))}
    assert attrs == {"contentType": "text/html", "value": "/manual.html"}


def test_the_asset_of_a_removed_entity_is_reported():
    T = _sm("Template", {"modelType": "Entity", "idShort": "Part", "entityType": "CoManagedEntity"})
    I = _sm("Instance", {"modelType": "Entity", "idShort": "Part", "entityType": "CoManagedEntity",
                         "globalAssetId": "urn:example:asset:pump-17"})
    res, _ = _resolve_and_apply([Item("RemoveSME", "Part")], T, I)
    assert [(n.path, n.detail) for n in res.notes if n.kind == "removed"] == \
        [("Part", "globalAssetId: urn:example:asset:pump-17")]
