"""The conformance check of a submodel against its Submodel Template, one case per finding."""

import copy
from pathlib import Path

import yaml

from tcn import instantiate
from tcn.aas import bridge
from tcn.core.conformance import check, conforms

SPEC = yaml.safe_load(Path("fixtures/technicaldata_1.2.yaml").read_text(encoding="utf-8"))
TEMPLATE = bridge.from_jsonable(bridge.load_submodel(SPEC["template"]))


def _findings(change) -> set[tuple[str, str]]:
    sm = instantiate.instantiate(SPEC)
    change({e["idShort"]: e for e in sm["submodelElements"]}["GeneralInformation"]["value"])
    return {(f.kind, f.path) for f in check(TEMPLATE, bridge.from_jsonable(sm))}


def _by_name(elements, name):
    return next(e for e in elements if e.get("idShort") == name)


def test_fixture_conforms():
    findings = check(TEMPLATE, bridge.from_jsonable(instantiate.instantiate(SPEC)))
    assert conforms(findings)
    # a local extension, and a property below SubSection, for which v1.2 describes no content
    assert {(f.kind, f.path) for f in findings} == {
        ("NOT_IN_TEMPLATE", "GeneralInformation.InternalInventoryNumber"),
        ("NOT_IN_TEMPLATE", "TechnicalProperties.MainSection01.SubSection01.RatedVoltage")}


def test_missing():
    assert ("MISSING", "GeneralInformation.ManufacturerName") in _findings(
        lambda els: els.remove(_by_name(els, "ManufacturerName")))


def test_too_many():
    def duplicate(els):
        els.append(copy.deepcopy(_by_name(els, "ManufacturerName")) | {"idShort": "ManufacturerName2"})
    assert ("TOO_MANY", "GeneralInformation.ManufacturerName") in _findings(duplicate)


def test_value_missing():
    assert ("VALUE_MISSING", "GeneralInformation.ManufacturerName") in _findings(
        lambda els: _by_name(els, "ManufacturerName").pop("value"))


def test_value_type():
    assert ("VALUE_TYPE", "GeneralInformation.ManufacturerName") in _findings(
        lambda els: _by_name(els, "ManufacturerName").update(valueType="xs:int"))


def test_unresolved_dropin_is_requested(monkeypatch, tmp_path):
    """A drop-in the catalogue does not hold is requested from the asset maintainer."""
    from tcn import dropins
    from tcn.roles import coevolution

    monkeypatch.setattr(dropins, "CATALOGUE", tmp_path / "empty.yaml")
    _, unresolved = coevolution.template("https://admin-shell.io/idta/SubmodelTemplate/DigitalNameplate/3/0")
    assert unresolved == ["AddressInformation"]
    report = coevolution.Report("ACC", "urn:test", unresolved_dropins=unresolved, conformance=[])
    assert report.todo and report.todo[0].startswith("DROPIN_UNRESOLVED: AddressInformation")


def test_dropin_is_resolved_from_the_catalogue():
    from tcn.roles import coevolution

    T, unresolved = coevolution.template("https://admin-shell.io/idta/SubmodelTemplate/DigitalNameplate/3/0")
    assert unresolved == []
    from tcn.core.addressing import element
    from tcn.core.matching import card
    for name in ("Street", "Zipcode", "CityTown", "NationalCode"):  # mandatory per IDTA 02006-3-0
        assert card(T, element(T, f"AddressInformation.{name}")) == "One"
