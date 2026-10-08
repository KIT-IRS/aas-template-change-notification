"""The TCN submodel (paper §3.5): template, and records that carry a chain without loss."""

import re

import pytest

from tcn import chainfile
from tcn.aas import bridge, tcn_submodel
from tcn.chainfile import item_to_dict

CHAINS = ["chains/technicaldata_1.2_to_2.0.yaml", "chains/nameplate_2.0_to_3.0.yaml"]


def test_template_is_metamodel_conformant():
    assert bridge.verify(tcn_submodel.template()["submodels"][0]) == []


def test_committed_template_is_current():
    committed = bridge.load_submodel("ressources/Templates/Template_TemplateChangeNotification.v0_4.json")
    assert committed == bridge.normalise(tcn_submodel.template()["submodels"][0])


@pytest.mark.parametrize("path", CHAINS)
def test_record_round_trip(path):
    chain = chainfile.load(path)
    rec = tcn_submodel.record(chain, "urn:uuid:test", "2026-09-28T00:00:00Z")
    back = tcn_submodel.record_to_chain(rec)
    assert [item_to_dict(i) for i in back.items] == [item_to_dict(i) for i in chain.items]
    assert back.header["TemplateOwnerAddress"] == chain.header["TemplateOwnerAddress"]


def _shape(submodel) -> set[tuple[str, str]]:
    """(path with list positions normalised, type); the content of a drop-in is governed by the
    drop-in, not by this template, and is left out."""
    T = bridge.from_jsonable(submodel)
    shape = {(re.sub(r"\[\d+\]", "[0]", T.path(e)), T.E[e].type) for e in T.E}
    return {(p, t) for p, t in shape if ".AddressInformation." not in p}


def test_instance_conforms_to_template_and_metamodel():
    sm = tcn_submodel.empty("urn:test:tcn")
    grp = tcn_submodel.group("https://admin-shell.io/idta/SubmodelTemplate/DigitalNameplate/2/0", "urn:test:dnp")
    grp["value"][2]["value"] = [tcn_submodel.record(chainfile.load(CHAINS[1]), "urn:uuid:test", "2026-09-28T00:00:00Z")]
    sm["submodelElements"][0]["value"] = [grp]
    assert bridge.verify(sm) == []
    assert _shape(sm) <= _shape(tcn_submodel.template()["submodels"][0])
