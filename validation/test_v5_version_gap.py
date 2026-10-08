"""V5: Digital Nameplate ZVEI 1.0 -> IDTA 3.0 via two records  (paper §5.4, §5.5, Table 4, Table 6).

Requirements R3, R4. Method: demonstration.
Pass criterion: both records apply in order, and an application out of order is refused with the
submodel left unchanged. The expectations are in fixtures/expected/nameplate_1.0_to_3.0.yaml.
"""

from pathlib import Path

import pytest
import yaml

from tcn import chainfile, environment
from tcn.roles import coevolution
from validation import application
from validation.endtoend import attrs, deliver

EXPECTED = "fixtures/expected/nameplate_1.0_to_3.0.yaml"


def test_chain_applies_and_retains_instance_data():
    application.check_chain_applies_and_retains_instance_data(EXPECTED)


def test_manual_steps_are_reported():
    application.check_manual_steps_are_reported(EXPECTED)


def test_result_is_serialisable_without_new_violations():
    application.check_result_is_serialisable_without_new_violations(EXPECTED)


def test_conformance_to_the_new_template():
    application.check_conformance_to_the_new_template(EXPECTED)


def test_no_value_is_lost_silently():
    application.check_no_value_is_lost_silently(EXPECTED)


@pytest.mark.infra
def test_version_gap_is_bridged_by_two_records(gw):
    exp = yaml.safe_load(Path(EXPECTED).read_text(encoding="utf-8"))
    environment.seed(gw, {"DigitalNameplate": exp["instance"]})
    first, second = (deliver(gw, c) for c in exp["chains"])

    before = gw.snapshot()  # out of order: refused, nothing changes
    report = coevolution.apply(gw, environment.TCN_ID, environment.AAS_ID, second, consent=True)
    assert report.status == "REJ" and report.reason.startswith("VERSION_MISMATCH")
    assert gw.snapshot() == before

    baseline_id = next(e.submodel_id for e in coevolution.records(gw, environment.TCN_ID))
    baseline, manual = gw.get_submodel(baseline_id), set()
    for nid in (first, second):  # in order: each application declares the next template version
        report = coevolution.apply(gw, environment.TCN_ID, environment.AAS_ID, nid, consent=True)
        assert report.status == "ACC", report.reason
        manual |= {n.path for n in report.resolution.notes if n.kind == "manual"}
    new = gw.get_submodel(report.new_revision)
    assert new["administration"]["templateId"] == chainfile.load(exp["chains"][-1]).header["PostVersion"]
    assert gw.get_submodel(baseline_id) == baseline
    for path, value in exp["retained"].items():
        assert attrs(new, path).get("value") == value, path
    for old, new_path in exp["control"].items():
        assert attrs(new, new_path) == attrs(baseline, old)
    assert manual == set(exp["manual"])
