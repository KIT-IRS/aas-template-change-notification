"""V6: chain that cannot be resolved against the local submodel  (paper §5.4, Table 4).

Requirement R4. Method: test.
Pass criterion: the chain is refused with a named reason, and no submodel is changed.
The local submodel lacks the mandatory element GeneralInformation.ManufacturerName (cardinality One),
on which the chain of Technical Data v1.2 -> v2.0 relies.
"""

from pathlib import Path

import pytest
import yaml

from tcn import chainfile, environment, instantiate
from tcn.aas import bridge
from tcn.core.guarded import REJ
from tcn.core.resolution import resolve
from tcn.roles import coevolution
from tcn.roles.template_owner import load_templates
from validation.endtoend import deliver

CHAIN = "chains/technicaldata_1.2_to_2.0.yaml"


def _without_manufacturer_name(spec_path: str) -> dict:
    spec = yaml.safe_load(Path(spec_path).read_text(encoding="utf-8"))
    spec["omit"].append("GeneralInformation.ManufacturerName")
    spec["values"].pop("GeneralInformation.ManufacturerName")
    return spec


def test_missing_mandatory_element_is_refused():
    spec = _without_manufacturer_name("fixtures/technicaldata_1.2.yaml")
    chain = chainfile.load(CHAIN)
    pre, _ = load_templates(chain)
    res = resolve(chain.items, pre, bridge.from_jsonable(instantiate.instantiate(spec)))
    assert res.status == REJ and "SEMANTIC_MATCH_NONE" in res.reason and "ManufacturerName" in res.reason


@pytest.mark.infra
def test_unresolvable_chain_is_refused(gw):
    environment.seed(gw, {"TechnicalData": _without_manufacturer_name(environment.FIXTURES["TechnicalData"])})
    nid = deliver(gw, CHAIN)
    before = gw.snapshot()
    report = coevolution.apply(gw, environment.TCN_ID, environment.AAS_ID, nid, consent=True)
    assert report.status == "REJ" and "SEMANTIC_MATCH_NONE" in report.reason
    assert gw.snapshot() == before, "the environment changed although the chain was refused"
    assert (coevolution.QUARANTINE / f"{nid.replace(':', '_')}.json").exists()
    assert any(e.chain.header["NotificationId"] == nid for e in coevolution.records(gw, environment.TCN_ID))
