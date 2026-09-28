"""Resolution and guarded application of a chain to a conforming submodel (paper §3.5, §4.1).

Offline part of V3 (Technical Data), V4 (Digital Nameplate) and V5 (two records in order): the same
code for all, which differ in their chain and fixture documents only. The expectations were derived by hand
(fixtures/expected). The end-to-end run over BaSyx and MQTT checks the same expectations.
"""

from collections import Counter
from pathlib import Path

import pytest
import yaml

from tcn import chainfile, instantiate
from tcn.aas import bridge
from tcn.core.addressing import element
from tcn.core.conformance import VIOLATIONS, check, conforms
from tcn.core.guarded import ACC, REJ, apply_chain
from tcn.core.metamodel import CONTAINMENT_KEY
from tcn.core.model import LAMBDA
from tcn.core.model import positions
from tcn.core.resolution import resolve
from tcn.roles.template_owner import load_templates

CONTAINERS = set(CONTAINMENT_KEY)
EXPECTED = sorted(Path("fixtures/expected").glob("*.yaml"))


def _run(expected_path):
    """Resolve and apply the chains in order. Returns the expectation, the instance before, the
    result, and the notes of all resolutions."""
    exp = yaml.safe_load(expected_path.read_text(encoding="utf-8"))
    instance = current = bridge.from_jsonable(instantiate.load(exp["instance"]))
    notes = []
    for path in exp.get("chains") or [exp["chain"]]:
        chain = chainfile.load(path)
        res = resolve(chain.items, load_templates(chain)[0], current)
        assert res.status == ACC, res.reason
        notes += res.notes
        out = apply_chain(res.items, current)
        assert out.status == ACC, out.reason
        current = out.template
    return exp, chain, instance, current, notes


def _attrs(T, path):
    e = element(T, path)
    return {T.A[a].name: T.A[a].value for a in T.attributes(e)}


def _causes(sm) -> Counter:
    return Counter(v.split(": ", 1)[1] for v in bridge.verify(sm))


@pytest.mark.parametrize("path", EXPECTED, ids=lambda p: p.stem)
def test_chain_applies_and_retains_instance_data(path):
    exp, _, instance, T, _ = _run(path)
    for p, value in exp["retained"].items():
        assert _attrs(T, p).get("value") == value, p
    for old, new in exp["control"].items():
        assert _attrs(T, new) == _attrs(instance, old), f"control element {old} changed"


@pytest.mark.parametrize("path", EXPECTED, ids=lambda p: p.stem)
def test_manual_steps_are_reported(path):
    exp, *_, notes = _run(path)
    assert {n.path for n in notes if n.kind == "manual"} == set(exp["manual"])


@pytest.mark.parametrize("path", EXPECTED, ids=lambda p: p.stem)
def test_result_is_serialisable_without_new_violations(path):
    exp, chain, instance, T, _ = _run(path)
    published = bridge.load_submodel(chain.header["PostTemplate"])
    allowed = set(_causes(bridge.to_jsonable(instance))) | set(_causes(published))
    assert set(_causes(bridge.to_jsonable(T))) <= allowed


@pytest.mark.parametrize("path", EXPECTED, ids=lambda p: p.stem)
def test_conformance_to_the_new_template(path):
    exp, chain, instance, T, _ = _run(path)
    first = chainfile.load((exp.get("chains") or [exp["chain"]])[0])
    assert conforms(check(load_templates(first)[0], instance)), "the fixture does not conform to v_i"
    findings = check(load_templates(chain)[1], T)
    assert conforms(findings) == exp["conforms"]
    assert sorted([f.kind, f.path] for f in findings if f.kind in VIOLATIONS) == sorted(exp["violations"])


@pytest.mark.parametrize("path", EXPECTED, ids=lambda p: p.stem)
def test_no_value_is_lost_silently(path):
    """Every value of the instance is, after the change, still at its element, or it is reported
    before consent: as transferred by an executable Sync, as to be carried over by an instruction,
    or as removed. The removed ones are as expected."""
    exp, _, instance, T, notes = _run(path)
    removed = {n.path for n in notes if n.kind == "removed"}
    assert removed == set(exp["removed"])
    for e in instance.E:
        a = instance.attr(e, "value")
        if a is None or instance.A[a].value in (LAMBDA, "", []) or instance.E[e].type in CONTAINERS:
            continue
        kept = e in T.E and T.attr(e, "value") is not None and T.A[T.attr(e, "value")].value == instance.A[a].value
        value = instance.A[a].value  # an instruction to carry the value over, naming it, was reported
        converted = e not in T.E and any(n.kind == "manual" and str(value) in n.detail for n in notes)
        synced = instance.path(e) in {n.path for n in notes if n.kind == "transferred"}
        assert kept or synced or converted or instance.path(e) in removed, f"{instance.path(e)} lost silently"


def test_baseline_is_not_changed():
    exp, chain, instance, _, _ = _run(EXPECTED[0])
    before = positions(instance)
    apply_chain(resolve(chain.items, load_templates(chain)[0], instance).items, instance)
    assert positions(instance) == before


def test_missing_mandatory_element_is_refused():
    """The instance lacks GeneralInformation.ManufacturerName (cardinality One)."""
    spec = yaml.safe_load(Path("fixtures/technicaldata_1.2.yaml").read_text(encoding="utf-8"))
    spec["omit"].append("GeneralInformation.ManufacturerName")
    spec["values"].pop("GeneralInformation.ManufacturerName")
    chain = chainfile.load("chains/technicaldata_1.2_to_2.0.yaml")
    pre, _ = load_templates(chain)
    res = resolve(chain.items, pre, bridge.from_jsonable(instantiate.instantiate(spec)))
    assert res.status == REJ and "SEMANTIC_MATCH_NONE" in res.reason and "ManufacturerName" in res.reason
