"""End-to-end runs over the AAS environment (BaSyx) and the MQTT broker  (paper §4.1, §5.1).

Observations are made only at the boundary a stakeholder could observe: the AAS API and the
roles' functions the command-line interface calls. Requires `docker compose up -d`; the fixture
`gw` (validation/conftest.py) seeds the AAS of the example device and removes it afterwards.
"""

import threading
from pathlib import Path

import yaml

from tcn import chainfile, environment
from tcn.aas import bridge
from tcn.core.addressing import element
from tcn.core.conformance import VIOLATIONS
from tcn.roles import coevolution, reception, template_owner


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


def check_end_to_end(gw, expected_path: str) -> None:
    """One record, published, filed, applied upon consent: the expectations of the offline run hold
    in the new revision, and the baseline revision is unchanged."""
    exp = yaml.safe_load(Path(expected_path).read_text(encoding="utf-8"))
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
