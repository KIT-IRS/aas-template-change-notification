"""V8 (Demonstration): the TCN states the revision of its own Submodel Template, v0.3 -> v0.4.

The template chain is checked with V1/V2 (test_v1_v2_expressiveness.py), its application to a TCN
submodel v0.3 with V3-V5 (test_resolution.py, fixtures/expected/tcn_0.3_to_0.4.yaml). This test
closes the loop: after the asset maintainer has carried out the reported manual steps, the migrated
record is a TCN record v0.4 that states the same chain as the v0.3 record did.
"""

import json
import re

from tcn import chainfile, instantiate
from tcn.aas import bridge, tcn_submodel
from tcn.chainfile import item_to_dict
from tcn.core.addressing import Item
from tcn.core.guarded import ACC, apply_chain
from tcn.core.resolution import resolve
from tcn.core.transfer import Identity
from tcn.roles.template_owner import load_templates

STATED_BY_THE_V03_RECORD = [
    Item("UpdateIdShort", "GeneralInformation.ManufacturerLogo", new_id_short="CompanyLogo"),
    Item("UpdateAttr", "TechnicalPropertyAreas", attribute_key="typeValueListElement",
         attribute_value="SubmodelElementCollection"),
    Item("Sync", "", source_paths=["TechnicalProperties@Cardinality#value"],
         target_paths=["TechnicalPropertyAreas@SMT/Cardinality#value"], transfer=Identity()),
    Item("UpdateParent", "GeneralInformation.ProductImage", new_parent_path="GeneralInformation.ProductImages[0]"),
]


def _carry_out_manual_steps(element: dict) -> None:
    """What the instructions of T4 ask the asset maintainer to do."""
    for c in element.get("value", []) if isinstance(element.get("value"), list) else []:
        if not isinstance(c, dict) or "modelType" not in c:
            continue
        name = c.get("idShort", "")
        if c["modelType"] == "Property" and (name in ("ElementPath", "NewParentPath") or name == ""):
            c["value"] = re.sub(r"^.*::", "", c["value"])  # the prefix '<submodelId>::'
        if name == "AttributeValue":
            c["value"] = json.dumps(c["value"])
        _carry_out_manual_steps(c)


def test_migrated_record_states_the_same_chain():
    chain = chainfile.load("chains/tcn_0.3_to_0.4.yaml")
    instance = bridge.from_jsonable(instantiate.load("fixtures/tcn_0.3.yaml"))
    res = resolve(chain.items, load_templates(chain)[0], instance)
    assert res.status == ACC, res.reason
    migrated = bridge.to_jsonable(apply_chain(res.items, instance).template)

    group = next(e for e in migrated["submodelElements"] if e["idShort"] == "TCNGroups")["value"][0]
    record = next(e for e in group["value"] if e["idShort"] == "TCNRecords")["value"][0]
    _carry_out_manual_steps(record)
    stated = tcn_submodel.record_to_chain(record)
    assert [item_to_dict(i) for i in stated.items] == [item_to_dict(i) for i in STATED_BY_THE_V03_RECORD]
    assert bridge.verify(migrated) == []
