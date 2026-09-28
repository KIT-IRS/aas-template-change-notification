"""End-to-end validation over the AAS environment (BaSyx) and the MQTT broker  (paper §5, Table 4).

Observations are made only at the boundary a stakeholder could observe: the AAS API and the
roles' functions the command-line interface calls. Requires `docker compose up -d`.

    V3  Technical Data v1.2 -> v2.0, end to end
    V4  Digital Nameplate v2.0 -> v3.0, end to end, with the same code as V3
    V5  a version gap is bridged by two records in order; out of order, a record is refused
    V6  a chain that cannot be resolved against the local submodel is refused before application
    V7  nothing changes between reception and consent, while unrelated interactions continue
"""

import threading
from pathlib import Path

import pytest
import requests
import yaml

from tcn import chainfile, environment
from tcn.aas import bridge
from tcn.core.addressing import element
from tcn.core.conformance import VIOLATIONS
from tcn.infra.gateway import Gateway
from tcn.roles import coevolution, reception, template_owner

pytestmark = pytest.mark.infra
EXPECTED = {"V3": "fixtures/expected/technicaldata_1.2_to_2.0.yaml",
            "V4": "fixtures/expected/nameplate_2.0_to_3.0.yaml"}


@pytest.fixture
def gw():
    try:
        requests.get(Gateway().url + "/shells", timeout=2)
    except requests.ConnectionError:
        pytest.skip("AAS environment not running (docker compose up -d)")
    gateway = Gateway()
    environment.seed(gateway)
    yield gateway
    environment.reset(gateway)


def deliver(gw, chain_path: str) -> str:
    """Template owner publishes, reception files; returns the NotificationId."""
    log, subscribed = [], threading.Event()
    t = threading.Thread(target=lambda: log.extend(
        reception.run(gw, environment.TCN_ID, list(environment.FIXTURES), seconds=5, subscribed=subscribed)))
    t.start()
    assert subscribed.wait(timeout=10), "reception did not subscribe"
    nid = template_owner.publish(chainfile.load(chain_path))
    t.join()
    assert f"filed: {nid}" in log
    return nid


def attrs(sm, path):
    T = bridge.from_jsonable(sm)
    e = element(T, path)
    return {T.A[a].name: T.A[a].value for a in T.attributes(e)}


@pytest.mark.parametrize("case", ["V3", "V4"])
def test_end_to_end(gw, case):
    exp = yaml.safe_load(Path(EXPECTED[case]).read_text(encoding="utf-8"))
    chain = chainfile.load(exp["chain"])
    nid = deliver(gw, exp["chain"])
    baseline_id = next(e.submodel_id for e in coevolution.records(gw, environment.TCN_ID)
                       if e.chain.header["NotificationId"] == nid)
    baseline = gw.get_submodel(baseline_id)

    report = coevolution.apply(gw, environment.TCN_ID, environment.AAS_ID, nid, consent=True)
    assert report.status == "ACC", report.reason

    assert gw.get_submodel(baseline_id) == baseline, "the baseline revision was changed"
    new = gw.get_submodel(report.new_revision)
    assert new["administration"]["templateId"] == chain.header["PostVersion"]
    refs = [r["keys"][0]["value"] for r in gw.get_shell(environment.AAS_ID)["submodels"]]
    assert report.new_revision in refs and baseline_id not in refs
    for path, value in exp["retained"].items():
        assert attrs(new, path).get("value") == value, path
    for old, new_path in exp["control"].items():
        assert attrs(new, new_path) == attrs(baseline, old), f"control element {old} changed"
    manual = {n.path for n in report.resolution.notes if n.kind == "manual"}
    assert manual == set(exp["manual"])
    violations = sorted([f.kind, f.path] for f in report.conformance if f.kind in VIOLATIONS)
    assert violations == sorted(exp["violations"])  # reported to the asset maintainer before consent


def test_v5_version_gap_is_bridged_by_two_records(gw):
    exp = yaml.safe_load(Path("fixtures/expected/nameplate_1.0_to_3.0.yaml").read_text(encoding="utf-8"))
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


def test_v6_unresolvable_chain_is_refused(gw):
    spec = yaml.safe_load(Path(environment.FIXTURES["TechnicalData"]).read_text(encoding="utf-8"))
    spec["omit"].append("GeneralInformation.ManufacturerName")  # mandatory (One)
    spec["values"].pop("GeneralInformation.ManufacturerName")
    environment.seed(gw, {"TechnicalData": spec})
    nid = deliver(gw, "chains/technicaldata_1.2_to_2.0.yaml")
    before = gw.snapshot()
    report = coevolution.apply(gw, environment.TCN_ID, environment.AAS_ID, nid, consent=True)
    assert report.status == "REJ" and "SEMANTIC_MATCH_NONE" in report.reason
    assert gw.snapshot() == before, "the environment changed although the chain was refused"
    assert (coevolution.QUARANTINE / f"{nid.replace(':', '_')}.json").exists()
    assert any(e.chain.header["NotificationId"] == nid for e in coevolution.records(gw, environment.TCN_ID))


def test_v7_no_change_before_consent(gw):
    nid = deliver(gw, "chains/technicaldata_1.2_to_2.0.yaml")
    sm_id = next(e.submodel_id for e in coevolution.records(gw, environment.TCN_ID)
                 if e.chain.header["NotificationId"] == nid)
    state = (gw.get_shell(environment.AAS_ID), gw.get_submodel(sm_id))
    interactions = [
        lambda: coevolution.records(gw, environment.TCN_ID),
        lambda: coevolution.preview(gw, environment.TCN_ID, nid),
        lambda: gw.get_submodel(sm_id),
        lambda: pytest.raises(PermissionError, coevolution.apply, gw, environment.TCN_ID,
                              environment.AAS_ID, nid, consent=False),
    ]
    for interact in interactions:
        interact()
        assert (gw.get_shell(environment.AAS_ID), gw.get_submodel(sm_id)) == state
