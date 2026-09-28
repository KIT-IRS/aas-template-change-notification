"""Role of the asset maintainer: co-evolution  (paper §4.1).

    records   the filed TCN records and whether each is applicable now
    preview   resolution against the current submodel: what would happen, whether the result
              conforms to the new template, and what remains to do; nothing is written
    apply     only upon explicit consent: guarded application of the resolved chain

A record is applicable iff the submodel declares the record's PreVersion as its template
(administration.templateId). An accepted chain is published as a new revision of the submodel;
the reference of the AAS and the SMInstance of the group are redirected to it, while the previous
revision remains unchanged as baseline. A refused chain writes nothing to the environment: it is
set aside with its reason (quarantine/), and the record remains waiting.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tcn import dropins
from tcn.aas import bridge, tcn_submodel
from tcn.chainfile import Chain
from tcn.core.addressing import Item
from tcn.core.conformance import VIOLATIONS, Finding, check
from tcn.core.guarded import ACC, REJ, apply_chain
from tcn.core.model import Template
from tcn.core.resolution import Resolution, resolve
from tcn.infra.gateway import Gateway

TEMPLATES = Path("ressources/Templates")
QUARANTINE = Path("quarantine")


@dataclass
class Entry:
    group: dict[str, Any]
    record: dict[str, Any]
    chain: Chain
    submodel_id: str
    applicable: bool


@dataclass
class Report:
    status: str
    notification_id: str
    reason: str | None = None
    resolution: Resolution | None = None
    new_revision: str | None = None
    conformance: list[Finding] | None = None  # the result against the template after the change
    unresolved_dropins: list[str] | None = None  # drop-ins of the new template not in the catalogue

    @property
    def removed(self) -> list[tuple[str, object]]:
        """Values of the submodel the change removes without carrying them over: (path, value)."""
        notes = self.resolution.notes if self.resolution else []
        return [(n.path, n.detail) for n in notes if n.kind == "removed"]

    @property
    def todo(self) -> list[str]:
        """What the asset maintainer has to do after the application: every violation of the new
        template, and every transformation stated as an instruction."""
        items = [f"DROPIN_UNRESOLVED: {p}: request the SMT drop-in this element uses; the template does "
                 f"not describe its content" for p in self.unresolved_dropins or []]
        items += [f"{f.kind}: {f.path} ({f.detail})" for f in self.conformance or [] if f.kind in VIOLATIONS]
        manual = [n for n in (self.resolution.notes if self.resolution else []) if n.kind == "manual"]
        # mandatory elements without value are already reported as VALUE_MISSING
        return items + [f"INSTRUCTION: {n.path}: {n.detail}" for n in manual if not n.detail.startswith("Mandatory")]


def template(template_id: str) -> tuple[Template, list[str]]:
    """The effective Submodel Template with this identifier, from the local template catalogue,
    and the paths of the drop-ins it uses that are not in the drop-in catalogue."""
    for path in sorted(TEMPLATES.glob("*.json")):
        sm = bridge.load_submodel(path)
        if sm["id"] == template_id:
            effective, unresolved = dropins.effective(sm)
            return bridge.from_jsonable(effective), unresolved
    raise LookupError(f"template {template_id} is not in the catalogue {TEMPLATES}")


def declared_template(sm: dict[str, Any]) -> str | None:
    return sm.get("administration", {}).get("templateId")


def _value(element: dict[str, Any], id_short: str) -> Any:
    return next(c for c in element["value"] if c.get("idShort") == id_short)["value"]


def records(gw: Gateway, tcn_id: str) -> list[Entry]:
    entries = []
    for group in gw.get_submodel(tcn_id)["submodelElements"][0].get("value", []):
        sm_id = _value(group, "SMInstance")["keys"][0]["value"]
        current = declared_template(gw.get_submodel(sm_id))
        for rec in next(c for c in group["value"] if c["idShort"] == "TCNRecords").get("value", []):
            chain = tcn_submodel.record_to_chain(rec)
            entries.append(Entry(group, rec, chain, sm_id, chain.header["PreVersion"] == current))
    return entries


def _find(gw: Gateway, tcn_id: str, notification_id: str) -> Entry:
    return next(e for e in records(gw, tcn_id) if e.chain.header["NotificationId"] == notification_id)


def _declare(post_version: str) -> Item:
    """Appended to every resolved chain: the submodel declares the template it now conforms to."""
    return Item("UpdateAttr", "", attribute_key="administration", attribute_value={"templateId": post_version})


def preview(gw: Gateway, tcn_id: str, notification_id: str) -> Report:
    """Resolve the record against the current submodel. Reads only."""
    e = _find(gw, tcn_id, notification_id)
    sm = gw.get_submodel(e.submodel_id)
    if not e.applicable:
        return Report(REJ, notification_id, f"VERSION_MISMATCH: submodel declares {declared_template(sm)}, "
                                            f"record requires {e.chain.header['PreVersion']}")
    res = resolve(e.chain.items, template(e.chain.header["PreVersion"])[0], bridge.from_jsonable(sm))
    report = Report(res.status, notification_id, res.reason, res)
    if res.status == ACC:  # the result, computed on a copy, against the template after the change
        result = apply_chain(res.items + [_declare(e.chain.header["PostVersion"])], bridge.from_jsonable(sm))
        if result.status == ACC:
            post, report.unresolved_dropins = template(e.chain.header["PostVersion"])
            report.conformance = check(post, result.template)
    return report


def apply(gw: Gateway, tcn_id: str, aas_id: str, notification_id: str, consent: bool) -> Report:
    if not consent:
        raise PermissionError("a TCN is applied only upon explicit consent of the asset maintainer")
    report = preview(gw, tcn_id, notification_id)
    if report.status == ACC:
        e = _find(gw, tcn_id, notification_id)
        baseline = gw.get_submodel(e.submodel_id)
        items = report.resolution.items + [_declare(e.chain.header["PostVersion"])]
        result = apply_chain(items, bridge.from_jsonable(baseline))
        if result.status == ACC:
            report.new_revision = _publish_revision(gw, tcn_id, aas_id, e, bridge.to_jsonable(result.template))
            return report
        report.status, report.reason = REJ, result.reason
    _set_aside(report)
    return report


def _revision_id(sm_id: str) -> str:
    """.../TechnicalData -> .../TechnicalData/rev/2 -> .../TechnicalData/rev/3"""
    m = re.fullmatch(r"(.*)/rev/(\d+)", sm_id)
    return f"{m[1]}/rev/{int(m[2]) + 1}" if m else f"{sm_id}/rev/2"


def _publish_revision(gw: Gateway, tcn_id: str, aas_id: str, e: Entry, sm: dict[str, Any]) -> str:
    """Write order: new revision, then AAS reference, then group. The baseline is never written."""
    sm["id"] = _revision_id(e.submodel_id)
    gw.post_submodel(sm)
    shell = gw.get_shell(aas_id)
    for ref in shell.get("submodels", []):
        if ref["keys"][0]["value"] == e.submodel_id:
            ref["keys"][0]["value"] = sm["id"]
    gw.put_shell(shell)
    tcn = gw.get_submodel(tcn_id)
    for group in tcn["submodelElements"][0]["value"]:
        ref = next(c for c in group["value"] if c["idShort"] == "SMInstance")["value"]
        if ref["keys"][0]["value"] == e.submodel_id:
            ref["keys"][0]["value"] = sm["id"]
    gw.put_submodel(tcn)
    return sm["id"]


def _set_aside(report: Report) -> None:
    QUARANTINE.mkdir(exist_ok=True)
    name = report.notification_id.replace(":", "_")
    (QUARANTINE / f"{name}.json").write_text(json.dumps(
        {"NotificationId": report.notification_id, "Reason": report.reason,
         "Notes": [n.__dict__ for n in (report.resolution.notes if report.resolution else [])]},
        indent=2, ensure_ascii=False), encoding="utf-8")
