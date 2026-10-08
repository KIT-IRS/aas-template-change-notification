"""Resolution and guarded application of a chain to a conforming submodel, offline  (paper §3.6, §5.3).

Shared by V3, V4, V5 and V8: the same code for all, which differ in their chain and fixture
documents only. The expectations were derived by hand (fixtures/expected); the end-to-end run over
BaSyx and MQTT (validation.endtoend) checks the same expectations.
"""

from collections import Counter
from functools import cache
from pathlib import Path

import yaml

from tcn import chainfile, instantiate
from tcn.aas import bridge
from tcn.core.addressing import element
from tcn.core.conformance import VIOLATIONS, check, conforms
from tcn.core.guarded import ACC, apply_chain
from tcn.core.metamodel import instance_data
from tcn.core.model import LAMBDA, positions
from tcn.core.resolution import resolve
from tcn.roles.template_owner import load_templates


@cache
def run(expected_path: str):
    """Resolve and apply the chains in order. Returns the expectation, the last chain, the instance
    before, the result, and the notes of all resolutions. Computed once per expectation and shared by
    the checks, which only read it (check_baseline_is_not_changed checks that the instance before is
    left unchanged); a run that fails is not cached and fails again in every check."""
    exp = yaml.safe_load(Path(expected_path).read_text(encoding="utf-8"))
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


def check_chain_applies_and_retains_instance_data(expected_path: str) -> None:
    exp, _, instance, T, _ = run(expected_path)
    for p, value in exp["retained"].items():
        assert _attrs(T, p).get("value") == value, p
    for old, new in exp["control"].items():
        assert _attrs(T, new) == _attrs(instance, old), f"control element {old} changed"


def check_manual_steps_are_reported(expected_path: str) -> None:
    exp, *_, notes = run(expected_path)
    assert {n.path for n in notes if n.kind == "manual"} == set(exp["manual"])


def check_result_is_serialisable_without_new_violations(expected_path: str) -> None:
    exp, chain, instance, T, _ = run(expected_path)
    published = bridge.load_submodel(chain.header["PostTemplate"])
    allowed = set(_causes(bridge.to_jsonable(instance))) | set(_causes(published))
    assert set(_causes(bridge.to_jsonable(T))) <= allowed


def check_conformance_to_the_new_template(expected_path: str) -> None:
    exp, chain, instance, T, _ = run(expected_path)
    first = chainfile.load((exp.get("chains") or [exp["chain"]])[0])
    assert conforms(check(load_templates(first)[0], instance)), "the fixture does not conform to v_i"
    findings = check(load_templates(chain)[1], T)
    assert conforms(findings) == exp["conforms"]
    assert sorted([f.kind, f.path] for f in findings if f.kind in VIOLATIONS) == sorted(exp["violations"])


def check_no_value_is_lost_silently(expected_path: str) -> None:
    """Every value of the instance (its instance data, e.g. value, contentType, first and second) is,
    after the change, still at its element, or it is reported before consent: as transferred by an
    executable Sync, as to be carried over by an instruction, or as removed. The removed ones are as
    expected."""
    exp, _, instance, T, notes = run(expected_path)
    removed = {n.path for n in notes if n.kind == "removed"}
    assert removed == set(exp["removed"])
    transferred = {n.path for n in notes if n.kind == "transferred"}
    for e in instance.E:
        for key in instance_data(instance.E[e].type):
            a = instance.attr(e, key)
            if a is None or instance.A[a].value in (LAMBDA, "", []):
                continue
            value = instance.A[a].value
            kept = e in T.E and T.attr(e, key) is not None and T.A[T.attr(e, key)].value == value
            # an instruction to carry the value over, naming it, was reported
            converted = e not in T.E and any(n.kind == "manual" and str(value) in n.detail for n in notes)
            synced = instance.path(e) in transferred
            assert kept or synced or converted or instance.path(e) in removed, \
                f"{instance.path(e)}#{key} lost silently"


def check_baseline_is_not_changed(expected_path: str) -> None:
    """Resolution and application of an accepted chain leave the instance they start from (the
    baseline revision) unchanged."""
    exp, chain, instance, _, _ = run(expected_path)
    before = positions(instance)
    res = resolve(chain.items, load_templates(chain)[0], instance)
    assert res.status == ACC, res.reason
    assert apply_chain(res.items, instance).status == ACC
    assert positions(instance) == before
