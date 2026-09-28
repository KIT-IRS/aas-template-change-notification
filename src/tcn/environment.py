"""The AAS of the asset maintainer in the validation environment: seed and reset.

Only identifiers below NAMESPACE are created or deleted; other content of the environment is
never touched.
"""

from __future__ import annotations

from tcn import instantiate
from tcn.aas import tcn_submodel
from tcn.infra.gateway import Gateway

NAMESPACE = "https://example.com/ids/"
AAS_ID = NAMESPACE + "aas/example-device"
TCN_ID = NAMESPACE + "sm/example-device/TCN"
FIXTURES = {"TechnicalData": "fixtures/technicaldata_1.2.yaml", "DigitalNameplate": "fixtures/nameplate_2.0.yaml"}


def _ref(sm_id: str) -> dict:
    return {"type": "ModelReference", "keys": [{"type": "Submodel", "value": sm_id}]}


def reset(gw: Gateway) -> None:
    for x in gw.shells():
        if x["id"].startswith(NAMESPACE):
            gw.delete_shell(x["id"])
    for x in gw.submodels():
        if x["id"].startswith(NAMESPACE):
            gw.delete_submodel(x["id"])


def seed(gw: Gateway, fixtures: dict[str, str | dict] = FIXTURES) -> None:
    """The AAS of the example device with one submodel per fixture and a TCN submodel with one
    group per submodel, observing the template the submodel conforms to."""
    reset(gw)
    tcn = tcn_submodel.empty(TCN_ID)
    for fixture in fixtures.values():  # a fixture file, or a fixture specification
        sm = instantiate.load(fixture) if isinstance(fixture, str) else instantiate.instantiate(fixture)
        gw.post_submodel(sm)
        tcn["submodelElements"][0].setdefault("value", []).append(
            tcn_submodel.group(sm["administration"]["templateId"], sm["id"]))
    gw.post_submodel(tcn)
    gw.post_shell({
        "modelType": "AssetAdministrationShell", "id": AAS_ID, "idShort": "ExampleDevice",
        "assetInformation": {"assetKind": "Instance", "globalAssetId": NAMESPACE + "asset/example-device"},
        "submodels": [_ref(x["id"]) for x in gw.submodels() if x["id"].startswith(NAMESPACE)]})
